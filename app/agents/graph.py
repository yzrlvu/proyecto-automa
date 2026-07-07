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
from pathlib import Path
from typing import Literal, TypedDict, Annotated

from langchain_groq import ChatGroq
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.event_bus import publicar
from app.rag.retriever import consultar_politicas_clinica
from app.tools.citas_tools import TOOLS_TRANSACCIONALES

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"


def _load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def _configure_langsmith() -> None:
    s = get_settings()
    if s.langsmith_tracing and s.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = s.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = s.langsmith_project


def _llm(model: str | None = None) -> ChatGroq:
    s = get_settings()
    return ChatGroq(model=model or s.llm_model, temperature=s.llm_temperature,
                    max_tokens=s.llm_max_tokens, api_key=s.groq_api_key)


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
        [SystemMessage(content=_load_prompt("supervisor_v2.md"))] + state["messages"]
    )
    publicar("mensaje.enrutado", "supervisor", {"ruta": decision.ruta})
    return {"ruta": decision.ruta}


def _contexto_fecha() -> str:
    return f"\n\nFecha actual: {date.today().isoformat()}."


def nodo_agente_rag(state: EstadoConversacion) -> dict:
    agent = create_react_agent(
        _llm(), tools=[consultar_politicas_clinica],
        prompt=_load_prompt("agente_rag_v1.md"),
    )
    result = agent.invoke({"messages": state["messages"]})
    return {"messages": [result["messages"][-1]]}


def nodo_agente_reservas(state: EstadoConversacion) -> dict:
    agent = create_react_agent(
        _llm(), tools=TOOLS_TRANSACCIONALES,
        prompt=_load_prompt("agente_reservas_v1.md") + _contexto_fecha(),
    )
    result = agent.invoke({"messages": state["messages"]})
    return {"messages": [result["messages"][-1]]}


def nodo_deep_agent(state: EstadoConversacion) -> dict:
    """Deep Agent (plan-and-execute) para solicitudes complejas multi-paso.

    Usa la librería `deepagents`, que añade planificación con TODO list,
    sistema de archivos virtual y subagentes sobre LangGraph.
    """
    from deepagents import create_deep_agent

    agent = create_deep_agent(
        tools=TOOLS_TRANSACCIONALES + [consultar_politicas_clinica],
        system_prompt=_load_prompt("deep_agent_v1.md") + _contexto_fecha(),
        model=_llm(get_settings().deep_agent_model),
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
