"""API HTTP (FastAPI): webhook de Telegram, chat directo y métricas de éxito/ROI."""
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import responder
from app.core.config import get_settings
from app.core.notificaciones import enviar_telegram
from app.models.db import Cita, EstadoCita, EventoSistema, get_session

router = APIRouter()

# Historial de conversación por sesión (en memoria; máx. 20 mensajes c/u)
_conversaciones: dict[str, list] = {}
_MAX_HISTORIAL = 20


class ChatInput(BaseModel):
    mensaje: str
    session_id: str = "default"


@router.get("/health")
def health():
    return {"status": "ok", "app": get_settings().app_name}


@router.post("/chat")
def chat(body: ChatInput):
    """Canal web/app: conversa con el sistema multiagente, con memoria por sesión."""
    historial = _conversaciones.setdefault(body.session_id, [])
    try:
        respuesta = responder(body.mensaje, historial)
    except Exception:  # noqa: BLE001 — el LLM puede fallar (rate limit, tool call inválido)
        logging.getLogger(__name__).exception("Error procesando mensaje del chat")
        return {"respuesta": ("Lo siento, tuve un inconveniente procesando tu solicitud. "
                              "¿Podrías intentarlo de nuevo, por favor?")}
    historial += [HumanMessage(content=body.mensaje), AIMessage(content=respuesta)]
    del historial[:-_MAX_HISTORIAL]
    return {"respuesta": respuesta}


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Webhook de Telegram: pasa el mensaje del paciente al grafo y responde."""
    update = await request.json()
    msg = update.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    texto = msg.get("text", "")
    if chat_id and texto:
        historial = _conversaciones.setdefault(f"tg:{chat_id}", [])
        respuesta = responder(texto, historial)
        historial += [HumanMessage(content=texto), AIMessage(content=respuesta)]
        del historial[:-_MAX_HISTORIAL]
        enviar_telegram(chat_id, respuesta)
    return {"ok": True}


@router.get("/metricas")
def metricas():
    """Métricas de éxito y ROI (criterio 8 de la rúbrica)."""
    session = get_session()
    try:
        total = session.scalar(select(func.count()).select_from(Cita)) or 0
        por_estado = dict(session.execute(
            select(Cita.estado, func.count()).group_by(Cita.estado)).all())
        eventos = session.scalar(select(func.count()).select_from(EventoSistema)) or 0
        confirmadas = por_estado.get(EstadoCita.CONFIRMADA, 0)
        no_asistio = por_estado.get(EstadoCita.NO_ASISTIO, 0)
        atendidas = por_estado.get(EstadoCita.ATENDIDA, 0)
        cerradas = atendidas + no_asistio
        return {
            "citas_totales": total,
            "citas_por_estado": {k.value: v for k, v in por_estado.items()},
            "eventos_auditados": eventos,
            "tasa_inasistencia": round(no_asistio / cerradas, 3) if cerradas else None,
            "tasa_confirmacion": round(confirmadas / total, 3) if total else None,
            "linea_base_asis": {"tiempo_agendamiento_min": 8, "tasa_inasistencia": 0.25,
                                 "horario_atencion": "8:00-18:00 L-V"},
            "objetivo_tobe": {"tiempo_agendamiento_min": 2, "tasa_inasistencia": 0.10,
                               "horario_atencion": "24/7"},
        }
    finally:
        session.close()
