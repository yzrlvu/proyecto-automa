# Medición de Éxito y ROI

## Línea base (AS-IS, proceso manual)

| Indicador | Valor AS-IS | Fuente |
|---|---|---|
| Citas diarias | 50–80 | Caso de estudio |
| Tiempo medio por agendamiento | ~8 min (llamada + Excel) | Estimación operativa |
| Horario de atención de agendamiento | 10 h/día, L–V | Caso de estudio |
| Tasa de inasistencia | ~25 % | Referencia sector salud LatAm |
| Recordatorios | Llamada manual el día anterior | Caso de estudio |
| Dedicación de recepcionista al agendamiento | ~70 % de su jornada | Estimación |

## Objetivos (TO-BE) y KPIs

| KPI | Objetivo | Cómo se mide |
|---|---|---|
| Tiempo medio de agendamiento | ≤ 2 min | Timestamps de eventos `disponibilidad.consultada` → `cita.creada` |
| Disponibilidad del canal | 24/7 | Uptime del API (health checks) |
| Tasa de inasistencia | ≤ 10 % | `no_asistio / (atendidas + no_asistio)` — endpoint `/metricas` |
| Tasa de confirmación | ≥ 85 % | `confirmadas / total` — endpoint `/metricas` |
| Recordatorios entregados | ≥ 95 % | Eventos `recordatorio.enviado` vs. citas confirmadas |
| Intervención humana | ≤ 10 % de casos | Eventos `caso.escalado` / total de conversaciones |
| Calidad de respuestas del agente | ≥ 90 % enrutamiento correcto | Evals en LangSmith (`evals/eval_langsmith.py`) |

Todos los KPIs operativos se calculan sobre el **EventBus** (tabla `eventos`),
lo que da trazabilidad completa sin instrumentación adicional.

## Análisis de ROI (proyección anual, escenario conservador)

### Costos del sistema (anual)
| Concepto | Monto (S/) |
|---|---|
| API Groq (capa gratuita/uso bajo, ≈ 70 conversaciones/día) | 0–1,200 |
| Infraestructura (VPS + PostgreSQL gestionado) | 2,400 |
| LangSmith (plan developer) | 1,500 |
| Mantenimiento (10 h/mes × S/ 50) | 6,000 |
| **Total anual** | **9,900–11,100** |

### Beneficios (anual)
| Concepto | Cálculo | Monto (S/) |
|---|---|---|
| Liberación de tiempo de recepción | 70 % de 1 puesto (S/ 1,500/mes × 12 × 0.7) | 12,600 |
| Reducción de inasistencias (25 %→10 %) | 15 % × 65 citas/día × 22 días × 12 m × S/ 100 ticket medio × 40 % margen | 103,000 |
| Citas fuera de horario (canal 24/7) | +5 % de citas incrementales | 15,400 |
| **Total anual** | | **131,000** |

### Resultado
- **ROI = (131,000 − 10,500) / 10,500 ≈ 1,148 %** (punto medio del rango de costos)
- **Payback ≈ 0.9 meses**
- Escenario pesimista (solo 5 % de reducción de inasistencias y sin citas
  incrementales): beneficio ≈ S/ 47,000 → ROI ≈ 348 %, payback < 3 meses.

## Análisis de sensibilidad

| Variable | −50 % | Base | +50 % |
|---|---|---|---|
| Reducción de inasistencias (pp) | 7.5 → ROI 495 % | 15 → ROI 1,148 % | 22.5 → ROI 1,800 % |
| Costo del sistema | ROI 2,395 % | ROI 1,148 % | ROI 665 % |

El ROI es positivo en todos los escenarios: la variable dominante es la
reducción de inasistencias, que el sistema ataca directamente con
recordatorios automáticos T-24h con confirmación/cancelación en un toque.
