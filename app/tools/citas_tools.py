"""Tools del sistema multiagente (LangChain @tool) con contratos Pydantic.

Cada tool es la interfaz que los agentes LangGraph usan para actuar sobre el
mundo (BD, notificaciones). La reserva usa SELECT ... FOR UPDATE para
garantizar exclusividad ante concurrencia (sección 4.1 del informe).
"""
from datetime import date, datetime, time

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.event_bus import publicar
from app.models.db import Cita, Doctor, EstadoCita, Paciente, Slot, get_session


# ---------- Contratos Pydantic (estilo MCP) ----------

class DisponibilidadInput(BaseModel):
    especialidad: str = Field(description="medicina_general | cardiologia | pediatria | dermatologia")
    fecha: str = Field(description="Fecha deseada en formato YYYY-MM-DD")


class ReservaInput(BaseModel):
    dni: str = Field(description="DNI del paciente")
    slot_id: int = Field(description="ID del slot elegido (obtenido de consultar_disponibilidad)")


class GestionCitaInput(BaseModel):
    dni: str = Field(description="DNI del paciente")
    cita_id: str = Field(description="UUID de la cita")


# ---------- Tools ----------

@tool(args_schema=DisponibilidadInput)
def consultar_disponibilidad(especialidad: str, fecha: str) -> str:
    """Consulta los slots disponibles de una especialidad para una fecha dada."""
    session = get_session()
    try:
        f = date.fromisoformat(fecha)
        rows = session.execute(
            select(Slot, Doctor)
            .join(Doctor)
            .where(Doctor.especialidad == especialidad, Slot.fecha == f, Slot.disponible == 1)
            .order_by(Slot.hora)
        ).all()
        if not rows:
            return f"No hay slots disponibles para {especialidad} el {fecha}."
        lineas = [
            f"slot_id={s.id} | Dr(a). {d.nombre} | {s.fecha} {s.hora.strftime('%H:%M')}"
            for s, d in rows
        ]
        publicar("disponibilidad.consultada", "agente_disponibilidad", {"especialidad": especialidad, "fecha": fecha, "n": len(rows)})
        return "\n".join(lineas)
    finally:
        session.close()


@tool(args_schema=ReservaInput)
def reservar_cita(dni: str, slot_id: int) -> str:
    """Reserva un slot para el paciente. Adquiere lock de fila (FOR UPDATE) para evitar doble reserva."""
    session = get_session()
    try:
        paciente = session.execute(select(Paciente).where(Paciente.dni == dni)).scalar_one_or_none()
        if not paciente:
            return f"Paciente con DNI {dni} no registrado. Solicita nombre y regístralo con registrar_paciente."
        # Lock pesimista a nivel de fila
        slot = session.execute(
            select(Slot).where(Slot.id == slot_id).with_for_update()
        ).scalar_one_or_none()
        if not slot or slot.disponible == 0:
            session.rollback()
            return "Ese slot ya no está disponible. Consulta nuevamente la disponibilidad."
        slot.disponible = 0
        cita = Cita(paciente_id=paciente.id, slot_id=slot.id, estado=EstadoCita.PENDIENTE)
        session.add(cita)
        session.commit()
        publicar("cita.creada", "agente_reservas", {"cita_id": str(cita.id), "slot_id": slot_id, "dni": dni})
        return (f"Cita reservada (estado PENDIENTE). cita_id={cita.id}. "
                f"Debe confirmarse en los próximos 10 minutos o el cupo se libera.")
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        return f"Error al reservar: {exc}"
    finally:
        session.close()


@tool(args_schema=GestionCitaInput)
def confirmar_cita(dni: str, cita_id: str) -> str:
    """Confirma una cita pendiente del paciente."""
    return _cambiar_estado(dni, cita_id, EstadoCita.CONFIRMADA, "cita.confirmada")


@tool(args_schema=GestionCitaInput)
def cancelar_cita(dni: str, cita_id: str) -> str:
    """Cancela una cita y libera el slot para otros pacientes."""
    session = get_session()
    try:
        cita = session.get(Cita, cita_id)
        if not cita or cita.paciente.dni != dni:
            return "Cita no encontrada para ese paciente."
        cita.estado = EstadoCita.CANCELADA
        slot = session.execute(select(Slot).where(Slot.id == cita.slot_id).with_for_update()).scalar_one()
        slot.disponible = 1
        session.commit()
        publicar("cita.cancelada", "agente_reservas", {"cita_id": cita_id})
        return "Cita cancelada y cupo liberado."
    finally:
        session.close()


class RegistroInput(BaseModel):
    dni: str
    nombre: str
    telegram_chat_id: str | None = None
    email: str | None = None
    seguro: str | None = None


@tool(args_schema=RegistroInput)
def registrar_paciente(dni: str, nombre: str, telegram_chat_id: str | None = None,
                       email: str | None = None, seguro: str | None = None) -> str:
    """Registra un paciente nuevo en la base de datos."""
    session = get_session()
    try:
        if session.execute(select(Paciente).where(Paciente.dni == dni)).scalar_one_or_none():
            return "El paciente ya está registrado."
        session.add(Paciente(dni=dni, nombre=nombre, telegram_chat_id=telegram_chat_id,
                             email=email, seguro=seguro))
        session.commit()
        publicar("paciente.registrado", "agente_registro", {"dni": dni})
        return f"Paciente {nombre} registrado correctamente."
    finally:
        session.close()


class SeguroInput(BaseModel):
    dni: str
    aseguradora: str = Field(description="Nombre de la aseguradora declarada por el paciente")


@tool(args_schema=SeguroInput)
def verificar_seguro(dni: str, aseguradora: str) -> str:
    """Verifica cobertura del seguro (simulación de consulta a aseguradora, sección 4.3)."""
    cubiertas = {"rimac", "pacifico", "mapfre", "essalud", "sanitas"}
    ok = aseguradora.strip().lower() in cubiertas
    publicar("seguro.verificado", "agente_seguros", {"dni": dni, "aseguradora": aseguradora, "cubierto": ok})
    return ("Cobertura VERIFICADA: la clínica trabaja con esa aseguradora."
            if ok else "La aseguradora no tiene convenio; la cita será particular.")


@tool
def listar_citas_paciente(dni: str) -> str:
    """Lista las citas activas (pendientes/confirmadas) de un paciente por DNI."""
    session = get_session()
    try:
        paciente = session.execute(select(Paciente).where(Paciente.dni == dni)).scalar_one_or_none()
        if not paciente:
            return "Paciente no registrado."
        activas = [c for c in paciente.citas if c.estado in (EstadoCita.PENDIENTE, EstadoCita.CONFIRMADA)]
        if not activas:
            return "El paciente no tiene citas activas."
        return "\n".join(
            f"cita_id={c.id} | {c.slot.fecha} {c.slot.hora.strftime('%H:%M')} | Dr(a). {c.slot.doctor.nombre} | {c.estado.value}"
            for c in activas
        )
    finally:
        session.close()


def _cambiar_estado(dni: str, cita_id: str, estado: EstadoCita, evento: str) -> str:
    session = get_session()
    try:
        cita = session.get(Cita, cita_id)
        if not cita or cita.paciente.dni != dni:
            return "Cita no encontrada para ese paciente."
        cita.estado = estado
        session.commit()
        publicar(evento, "agente_reservas", {"cita_id": cita_id})
        return f"Cita actualizada a estado {estado.value}."
    finally:
        session.close()


TOOLS_TRANSACCIONALES = [
    consultar_disponibilidad, reservar_cita, confirmar_cita,
    cancelar_cita, registrar_paciente, verificar_seguro, listar_citas_paciente,
]
