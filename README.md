---
title: Clínica San Gabriel — Asistente de Citas
emoji: 🏥
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# 🏥 Sistema Automatizado de Gestión de Citas — Clínica San Gabriel

**Grupo 10** — Escobedo Bopp · Montoya Granda · Salvador Mauricio
Curso: *Automatización Inteligente de Procesos* — UPAO, 2026

Sistema multiagente para la reingeniería del proceso de gestión de citas de una
clínica (60 pacientes/día, 4 especialidades), construido con **LangGraph**,
**RAG**, **Deep Agents**, **FastAPI** y **PostgreSQL**, con observabilidad y
evaluación en **LangSmith**.

## ✨ Capacidades

- 🤖 **Supervisor LangGraph** (Hub-and-Spoke) que enruta cada mensaje al agente adecuado.
- 📚 **RAG** sobre políticas, tarifas, horarios y FAQ de la clínica (Chroma + MiniLM).
- 🛠️ **7 tools transaccionales** con contratos Pydantic: disponibilidad, reserva
  con lock `SELECT ... FOR UPDATE`, confirmación, cancelación, registro,
  verificación de seguro y listado de citas.
- 🧠 **Deep Agent** (plan-and-execute con TODO list) para solicitudes complejas
  multi-paso (varias citas / varios pacientes).
- ⏰ **APScheduler**: recordatorios T-24h con fallback Telegram → email y
  liberación automática de cupos no confirmados (timeout 10 min).
- 📊 **EventBus** persistente en PostgreSQL para auditoría y KPIs.
- 🔍 **LangSmith**: trazas de todos los nodos/tools + suite de evaluación.
- 📈 **Endpoint `/metricas`** con KPIs de éxito y línea base AS-IS vs TO-BE.

## 🚀 Inicio rápido

```bash
git clone https://github.com/yzrlvu/proyecto-automa.git && cd proyecto-automa
cp .env.example .env                                # completar claves
docker compose -f deploy/docker-compose.yml up --build -d
docker compose -f deploy/docker-compose.yml exec api python -m scripts.seed
docker compose -f deploy/docker-compose.yml exec api python -m scripts.index_kb
```

Probar el chat:
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"mensaje": "¿Cuánto cuesta la consulta de cardiología?"}'
```

## 📁 Estructura

```
app/
├── agents/graph.py        # Grafo LangGraph: supervisor + RAG + reservas + deep agent
├── tools/citas_tools.py   # Tools transaccionales (Pydantic + locks)
├── rag/retriever.py       # Pipeline RAG (Chroma, chunking, tool de consulta)
├── models/db.py           # Modelos SQLAlchemy (citas, slots, EventBus)
├── core/                  # Config, EventBus, notificaciones (Telegram→email)
├── scheduler/jobs.py      # APScheduler: recordatorios y liberación de cupos
└── api/routes.py          # FastAPI: webhook Telegram, chat, métricas
prompts/                   # Prompts versionados con changelog (v1, v2…)
data/knowledge_base/       # Base de conocimiento del RAG
evals/eval_langsmith.py    # Dataset + evaluadores en LangSmith
tests/                     # Pruebas unitarias (pytest) — CI en GitHub Actions
docs/                      # Arquitectura, ROI, guía de despliegue
deploy/                    # Dockerfile + docker-compose
```

## 🧪 Pruebas y evaluación

```bash
pytest -q                          # unitarias (requiere PostgreSQL de prueba)
python -m evals.eval_langsmith     # evaluación de enrutamiento/calidad en LangSmith
```

## 📖 Documentación

| Documento | Contenido |
|---|---|
| [docs/arquitectura.md](docs/arquitectura.md) | Diagrama, componentes, ADRs, concurrencia |
| [docs/roi.md](docs/roi.md) | KPIs, línea base AS-IS, ROI ≈ 870 %, sensibilidad |
| [docs/despliegue.md](docs/despliegue.md) | Despliegue Docker/manual, webhook, operación |

## 🗺️ Mapeo con la rúbrica

| # | Criterio | Evidencia |
|---|---|---|
| 1 | Análisis del problema y requisitos | `docs/arquitectura.md` §Visión, informe del caso |
| 2 | Arquitectura y diseño técnico | `docs/arquitectura.md` (Hub-and-Spoke, ADRs) |
| 3 | Implementación (RAG, tools, LangGraph, Deep Agent) | `app/rag/`, `app/tools/`, `app/agents/graph.py` |
| 4 | Observabilidad y evaluación (LangSmith) | Trazas automáticas + `evals/eval_langsmith.py` |
| 5 | Calidad del código y prompts versionados | Tipado, Pydantic, `prompts/*_vN.md` con changelog |
| 6 | Documentación | `README.md` + `docs/` |
| 7 | Despliegue y operación | `deploy/`, `docs/despliegue.md`, CI |
| 8 | Medición de éxito y ROI | `docs/roi.md` + endpoint `/api/v1/metricas` |
| 9 | Innovación y contribución | Deep agent para casos multi-paso, EventBus auditable, fallback multicanal |

## ⚖️ Licencia
Proyecto académico — UPAO 2026.
