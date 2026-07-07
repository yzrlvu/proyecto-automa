"""Tareas programadas con APScheduler (sección 4.2 del informe).

- Recordatorios T-24h para citas confirmadas.
- Liberación de cupos de reservas PENDIENTES no confirmadas (timeout 10 min).
Ambos jobs corren cada 5 minutos.
"""
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import get_settings
from app.core.event_bus import publicar
from app.core.notificaciones import notificar_paciente
from app.models.db import Cita, EstadoCita, Slot, get_session

logger = logging.getLogger("scheduler")


def job_recordatorios() -> None:
    s = get_settings()
    session = get_session()
    try:
        ahora = datetime.now()
        limite = ahora + timedelta(hours=s.reminder_hours_before)
        citas = session.execute(
            select(Cita).where(Cita.estado == EstadoCita.CONFIRMADA,
                               Cita.recordatorio_enviado == 0)
        ).scalars().all()
        for cita in citas:
            inicio = datetime.combine(cita.slot.fecha, cita.slot.hora)
            if ahora <= inicio <= limite:
                texto = (f"Recordatorio: tienes una cita el {cita.slot.fecha} a las "
                         f"{cita.slot.hora.strftime('%H:%M')} con Dr(a). {cita.slot.doctor.nombre}. "
                         f"Responde CONFIRMAR o CANCELAR.")
                canal = notificar_paciente(cita.paciente, texto)
                cita.recordatorio_enviado = 1
                session.commit()
                publicar("recordatorio.enviado", "scheduler", {"cita_id": str(cita.id), "canal": canal})
    finally:
        session.close()


def job_liberar_cupos() -> None:
    s = get_settings()
    session = get_session()
    try:
        limite = datetime.utcnow() - timedelta(minutes=s.slot_hold_timeout_minutes)
        vencidas = session.execute(
            select(Cita).where(Cita.estado == EstadoCita.PENDIENTE, Cita.creada_en < limite)
        ).scalars().all()
        for cita in vencidas:
            cita.estado = EstadoCita.CANCELADA
            slot = session.execute(select(Slot).where(Slot.id == cita.slot_id).with_for_update()).scalar_one()
            slot.disponible = 1
            session.commit()
            publicar("cupo.liberado_timeout", "scheduler", {"cita_id": str(cita.id)})
    finally:
        session.close()


def start_scheduler() -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="America/Lima")
    sched.add_job(job_recordatorios, "interval", minutes=5, id="recordatorios")
    sched.add_job(job_liberar_cupos, "interval", minutes=5, id="liberar_cupos")
    sched.start()
    logger.info("Scheduler iniciado (jobs cada 5 min)")
    return sched
