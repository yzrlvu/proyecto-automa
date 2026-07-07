"""EventBus centralizado: registra todos los eventos del sistema en PostgreSQL."""
import logging
from typing import Any

from app.models.db import EventoSistema, get_session

logger = logging.getLogger("event_bus")


def publicar(tipo: str, agente: str, payload: dict[str, Any] | None = None) -> None:
    """Publica un evento de dominio. Nunca interrumpe el flujo principal si falla."""
    try:
        session = get_session()
        session.add(EventoSistema(tipo=tipo, agente=agente, payload=payload or {}))
        session.commit()
        session.close()
    except Exception:  # noqa: BLE001
        logger.exception("No se pudo persistir el evento %s", tipo)
