# Arquitectura y Diseño Técnico

## Visión general (patrón Hub-and-Spoke)

El sistema implementa una arquitectura multiagente orquestada con **LangGraph**,
donde un agente **supervisor** (hub) clasifica la intención del paciente con
salida estructurada (Pydantic) y enruta a agentes especializados (spokes):

```
Paciente (Telegram / Web / App)
        │
        ▼
FastAPI (webhook /api/v1/webhook/telegram, /api/v1/chat)
        │
        ▼
┌───────────────────────── LangGraph ─────────────────────────┐
│                      ┌────────────┐                          │
│                      │ SUPERVISOR │  salida estructurada      │
│                      └─────┬──────┘                          │
│    ┌───────────────┬───────┴────────────┬───────────────┐    │
│    ▼               ▼                    ▼               ▼    │
│ AGENTE RAG    AGENTE RESERVAS      DEEP AGENT        HUMANO  │
│ (Chroma +     (ReAct + 7 tools     (plan-and-      (escala-  │
│  políticas)    transaccionales)     execute)        miento)  │
└──────────────────────────────────────────────────────────────┘
        │                    │
        ▼                    ▼
   Chroma (KB)      PostgreSQL (ACID + SELECT FOR UPDATE)
                             │
                     EventBus (tabla eventos → auditoría)
                             │
                     APScheduler (recordatorios T-24h,
                                  liberación de cupos)
```

## Componentes

| Componente | Tecnología | Responsabilidad |
|---|---|---|
| API Gateway | FastAPI | Webhooks Telegram, chat web, métricas |
| Supervisor | LangGraph + Claude (structured output) | Clasificación de intención y enrutamiento |
| Agente RAG | create_react_agent + Chroma | Preguntas de políticas, tarifas, horarios |
| Agente Reservas | create_react_agent + 7 tools | Ciclo de vida de citas con locks |
| Deep Agent | deepagents (plan-and-execute) | Solicitudes complejas multi-paso |
| Persistencia | PostgreSQL + SQLAlchemy | Transacciones ACID, locks de fila |
| EventBus | Tabla `eventos` (JSONB) | Auditoría y trazabilidad completa |
| Scheduler | APScheduler (cron cada 5 min) | Recordatorios T-24h, timeouts de 10 min |
| Notificaciones | Telegram Bot API → SMTP fallback | Confirmaciones y recordatorios |
| Observabilidad | LangSmith | Trazas de cada nodo/tool, evals |

## Decisiones de diseño (ADR resumidas)

1. **LangGraph sobre orquestación ad-hoc**: el grafo explícito con edges
   condicionales hace el enrutamiento auditable y testeable; cada nodo emite
   trazas independientes a LangSmith.
2. **Locks pesimistas (`SELECT ... FOR UPDATE`)**: ante 50–80 citas/día con
   picos matutinos, el lock de fila garantiza que dos pacientes no reserven el
   mismo slot. El costo de contención es despreciable a esta escala.
3. **RAG con embeddings locales (MiniLM)**: la base de conocimiento es pequeña
   (< 100 chunks); embeddings locales eliminan costo/latencia por token y
   permiten reindexar libremente.
4. **Deep Agent solo para la ruta compleja**: plan-and-execute agrega latencia
   y costo; el supervisor lo reserva a solicitudes multi-paso reales.
5. **Contratos Pydantic en todas las tools (estilo MCP)**: tipado fuerte y
   validación automática de requests entre agentes.

## Concurrencia (flujo de reserva)

1. `reservar_cita` abre transacción y ejecuta `SELECT ... FOR UPDATE` sobre el slot.
2. Si `disponible = 0` → rollback y mensaje al paciente.
3. Si libre → `disponible = 0`, se crea `Cita(PENDIENTE)`, commit.
4. Job `liberar_cupos` (cada 5 min) cancela pendientes con > 10 min y libera el slot.
