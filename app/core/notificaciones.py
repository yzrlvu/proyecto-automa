"""Notificaciones: Telegram (primario) con fallback a email (sección 4.3)."""
import logging
import smtplib
from email.mime.text import MIMEText

import httpx

from app.core.config import get_settings
from app.core.event_bus import publicar

logger = logging.getLogger("notificaciones")


def enviar_telegram(chat_id: str, texto: str) -> bool:
    s = get_settings()
    if not s.telegram_bot_token or not chat_id:
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": texto}, timeout=10,
        )
        return r.status_code == 200
    except Exception:  # noqa: BLE001
        logger.exception("Fallo Telegram")
        return False


def enviar_email(destino: str, asunto: str, texto: str) -> bool:
    s = get_settings()
    if not s.smtp_user or not destino:
        return False
    try:
        msg = MIMEText(texto)
        msg["Subject"], msg["From"], msg["To"] = asunto, s.smtp_user, destino
        with smtplib.SMTP(s.smtp_host, s.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Fallo email")
        return False


def notificar_paciente(paciente, texto: str, asunto: str = "Clínica San Gabriel") -> str:
    """Intenta Telegram; si falla, email. Devuelve el canal usado."""
    if enviar_telegram(paciente.telegram_chat_id, texto):
        publicar("notificacion.enviada", "motor_notificaciones", {"canal": "telegram"})
        return "telegram"
    if enviar_email(paciente.email, asunto, texto):
        publicar("notificacion.enviada", "motor_notificaciones", {"canal": "email"})
        return "email"
    publicar("notificacion.fallida", "motor_notificaciones", {"paciente": str(paciente.id)})
    return "ninguno"
