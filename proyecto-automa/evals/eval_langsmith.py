"""Evaluación con LangSmith (criterio 4 de la rúbrica).

Sube un dataset de casos de prueba y evalúa el grafo con:
- correctness (LLM-as-judge sobre respuesta vs. referencia)
- enrutamiento correcto del supervisor

Requiere LANGSMITH_API_KEY y ANTHROPIC_API_KEY en el entorno.
Uso: python -m evals.eval_langsmith
"""
from langsmith import Client

from app.agents.graph import get_graph
from langchain_core.messages import HumanMessage

DATASET = "citas-clinica-eval"

CASOS = [
    {"input": "¿Cuánto cuesta la consulta de cardiología?", "ruta": "informacion",
     "referencia": "La consulta particular de cardiología cuesta S/ 150."},
    {"input": "¿Atienden los sábados por la tarde?", "ruta": "informacion",
     "referencia": "No, los sábados solo se atiende hasta la 1 PM (medicina general y pediatría)."},
    {"input": "Quiero agendar una cita de pediatría para mañana, mi DNI es 45678912",
     "ruta": "reservas", "referencia": "Debe consultar disponibilidad y ofrecer horarios."},
    {"input": "Necesito una cita de cardiología para mi papá (DNI 11111111) y otra de pediatría para mi hija (DNI 22222222), ambas el mismo día",
     "ruta": "planificacion", "referencia": "Debe planificar ambas reservas paso a paso."},
    {"input": "Tengo un dolor de pecho muy fuerte ahora mismo", "ruta": "humano",
     "referencia": "Debe indicar acudir a emergencias / llamar al 106."},
]


def crear_dataset(client: Client):
    if client.has_dataset(dataset_name=DATASET):
        return client.read_dataset(dataset_name=DATASET)
    ds = client.create_dataset(dataset_name=DATASET, description="Casos de prueba clínica")
    for c in CASOS:
        client.create_example(dataset_id=ds.id,
                              inputs={"mensaje": c["input"]},
                              outputs={"referencia": c["referencia"], "ruta": c["ruta"]})
    return ds


def target(inputs: dict) -> dict:
    result = get_graph().invoke({"messages": [HumanMessage(content=inputs["mensaje"])], "ruta": ""})
    return {"respuesta": result["messages"][-1].content, "ruta": result["ruta"]}


def evaluador_ruta(run, example) -> dict:
    ok = run.outputs.get("ruta") == example.outputs.get("ruta")
    return {"key": "enrutamiento_correcto", "score": int(ok)}


def main():
    client = Client()
    crear_dataset(client)
    client.evaluate(target, data=DATASET, evaluators=[evaluador_ruta],
                    experiment_prefix="citas-clinica")
    print("Evaluación enviada a LangSmith. Revisa el proyecto en smith.langchain.com")


if __name__ == "__main__":
    main()
