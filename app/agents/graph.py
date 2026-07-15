"""Orquestación multiagente con LangGraph (patrón Hub-and-Spoke).

Grafo:
                    ┌────────────┐
     mensaje ─────► │ supervisor │  (clasifica intención con salida estructurada)
                    └─────┬──────┘
        ┌─────────────────┼─────────────────────┬──────────────┐
        ▼                 ▼                     ▼              ▼
  agente_rag       agente_reservas       deep_agent        humano
 (RAG + Chroma)   (ReAct + tools BD)   (plan-and-execute)  (escalamiento)

Cada nodo emite trazas a LangSmith automáticamente vía variables de entorno.
"""
import os
from datetime import date
from typing import Literal, TypedDict, Annotated

from langchain_groq import ChatGroq
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from app.agents import prompts
from app.core.config import get_settings
from app.core.event_bus import publicar
from app.rag.retriever import consultar_politicas_clinica
from app.tools.citas_tools import TOOLS_TRANSACCIONALES


def _configure_langsmith() -> None:
    s = get_settings()
    if s.langsmith_tracing and s.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = s.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = s.langsmith_project


def _llm(model: str | None = None) -> ChatGroq:
    s = get_settings()
    # max_retries alto: el free tier de Groq limita tokens/minuto y el SDK
    # respeta el retry-after del 429, así el usuario no ve el error.
    return ChatGroq(model=model or s.llm_model, temperature=s.llm_temperature,
                    max_tokens=s.llm_max_tokens, api_key=s.groq_api_key,
                    max_retries=6)


# ---------- Estado del grafo ----------

class EstadoConversacion(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    ruta: str


class DecisionRuta(BaseModel):
    """Salida estructurada del supervisor."""
    ruta: Literal["informacion", "reservas", "planificacion", "humano"] = Field(
        description="Agente al que se enruta la solicitud del paciente")


# ---------- Nodos ----------

def nodo_supervisor(state: EstadoConversacion) -> dict:
    llm = _llm().with_structured_output(DecisionRuta)
    decision = llm.invoke(
        [SystemMessage(content=prompts.SUPERVISOR)] + state["messages"]
    )
    publicar("mensaje.enrutado", "supervisor", {"ruta": decision.ruta})
    return {"ruta": decision.ruta}


def _contexto_fecha() -> str:
    return f"\n\nFecha actual: {date.today().isoformat()}."


def nodo_agente_rag(state: EstadoConversacion) -> dict:
    agent = create_react_agent(
        _llm(), tools=[consultar_politicas_clinica],
        prompt=prompts.AGENTE_RAG,
    )
    result = agent.invoke({"messages": state["messages"]})
    return {"messages": [result["messages"][-1]]}


def nodo_agente_reservas(state: EstadoConversacion) -> dict:
    agent = create_react_agent(
        _llm(), tools=TOOLS_TRANSACCIONALES,
        prompt=prompts.AGENTE_RESERVAS + _contexto_fecha(),
    )
    result = agent.invoke({"messages": state["messages"]})
    return {"messages": [result["messages"][-1]]}


def nodo_deep_agent(state: EstadoConversacion) -> dict:
    """Deep Agent (plan-and-execute) para solicitudes complejas multi-paso.

    Usa la librería `deepagents` (planificación con TODO list, sistema de
    archivos virtual) con un catálogo de sub-agentes especializados, cada uno
    con tools acotadas a su rol (principio de mínimo privilegio).
    """
    from deepagents import create_deep_agent

    from app.tools.citas_tools import (
        cancelar_cita, confirmar_cita, consultar_disponibilidad,
        listar_citas_paciente, registrar_paciente, reservar_cita, verificar_seguro,
    )

    modelo = _llm(get_settings().deep_agent_model)
    subagentes = [
        {
            "name": "orquestador-reservas",
            "description": ("Gestiona el ciclo de vida de citas: disponibilidad, registro de "
                            "pacientes, reserva, confirmación, cancelación y listado."),
            "system_prompt": prompts.AGENTE_RESERVAS + _contexto_fecha(),
            "tools": [consultar_disponibilidad, registrar_paciente, reservar_cita,
                      confirmar_cita, cancelar_cita, listar_citas_paciente],
            "model": modelo,
        },
        {
            "name": "verificador-seguros",
            "description": "Verifica la cobertura del seguro del paciente con la aseguradora.",
            "system_prompt": prompts.VERIFICADOR_SEGUROS,
            "tools": [verificar_seguro],
            "model": modelo,
        },
        {
            "name": "consultor-politicas",
            "description": ("Responde preguntas sobre políticas, tarifas, horarios y FAQ de la "
                            "clínica usando la base de conocimiento (RAG)."),
            "system_prompt": prompts.AGENTE_RAG,
            "tools": [consultar_politicas_clinica],
            "model": modelo,
        },
    ]

    agent = create_deep_agent(
        system_prompt=prompts.DEEP_AGENT + _contexto_fecha(),
        model=modelo,
        subagents=subagentes,
    )
    result = agent.invoke({"messages": state["messages"]})
    return {"messages": [result["messages"][-1]]}


def nodo_humano(state: EstadoConversacion) -> dict:
    publicar("caso.escalado", "supervisor", {"motivo": "fuera_de_alcance_o_emergencia"})
    msg = ("Tu caso requiere atención personalizada. Un miembro del equipo de la "
           "clínica se comunicará contigo. Si se trata de una emergencia médica, "
           "acude de inmediato al servicio de emergencias o llama al 106 (SAMU).")
    from langchain_core.messages import AIMessage
    return {"messages": [AIMessage(content=msg)]}


# ---------- Construcción del grafo ----------

def _elegir_ruta(state: EstadoConversacion) -> str:
    return state["ruta"]


def build_graph():
    _configure_langsmith()
    g = StateGraph(EstadoConversacion)
    g.add_node("supervisor", nodo_supervisor)
    g.add_node("informacion", nodo_agente_rag)
    g.add_node("reservas", nodo_agente_reservas)
    g.add_node("planificacion", nodo_deep_agent)
    g.add_node("humano", nodo_humano)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _elegir_ruta, {
        "informacion": "informacion",
        "reservas": "reservas",
        "planificacion": "planificacion",
        "humano": "humano",
    })
    for nodo in ("informacion", "reservas", "planificacion", "humano"):
        g.add_edge(nodo, END)
    return g.compile()


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def responder(mensaje: str, historial: list[AnyMessage] | None = None) -> str:
    """Punto de entrada de alto nivel: recibe el mensaje del paciente y devuelve la respuesta."""
    mensajes = (historial or []) + [HumanMessage(content=mensaje)]
    result = get_graph().invoke({"messages": mensajes, "ruta": ""})
    return result["messages"][-1].content
