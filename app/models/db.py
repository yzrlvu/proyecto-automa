"""Modelos de persistencia (PostgreSQL) — transacciones ACID con locks a nivel de fila."""
import enum
import uuid
from datetime import datetime, date, time

from sqlalchemy import (
    Column, String, Integer, Date, Time, DateTime, Enum, ForeignKey, Text,
    UniqueConstraint, create_engine
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.core.config import get_settings

Base = declarative_base()


class EstadoCita(str, enum.Enum):
    PENDIENTE = "pendiente"        # slot bloqueado, esperando confirmación
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    REPROGRAMADA = "reprogramada"
    ATENDIDA = "atendida"
    NO_ASISTIO = "no_asistio"


class Especialidad(str, enum.Enum):
    MEDICINA_GENERAL = "medicina_general"
    CARDIOLOGIA = "cardiologia"
    PEDIATRIA = "pediatria"
    DERMATOLOGIA = "dermatologia"


class Doctor(Base):
    __tablename__ = "doctores"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(120), nullable=False)
    especialidad = Column(Enum(Especialidad), nullable=False)
    slots = relationship("Slot", back_populates="doctor")


class Paciente(Base):
    __tablename__ = "pacientes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dni = Column(String(12), unique=True, nullable=False)
    nombre = Column(String(120), nullable=False)
    telegram_chat_id = Column(String(64), nullable=True)
    email = Column(String(120), nullable=True)
    seguro = Column(String(80), nullable=True)
    citas = relationship("Cita", back_populates="paciente")


class Slot(Base):
    """Bloque de 30 minutos del calendario semanal del médico."""
    __tablename__ = "slots"
    __table_args__ = (UniqueConstraint("doctor_id", "fecha", "hora", name="uq_slot"),)
    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("doctores.id"), nullable=False)
    fecha = Column(Date, nullable=False)
    hora = Column(Time, nullable=False)
    disponible = Column(Integer, default=1)  # 1 libre, 0 ocupado
    doctor = relationship("Doctor", back_populates="slots")


class Cita(Base):
    __tablename__ = "citas"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    paciente_id = Column(UUID(as_uuid=True), ForeignKey("pacientes.id"), nullable=False)
    slot_id = Column(Integer, ForeignKey("slots.id"), nullable=False)
    estado = Column(Enum(EstadoCita), default=EstadoCita.PENDIENTE, nullable=False)
    creada_en = Column(DateTime, default=datetime.utcnow)
    actualizada_en = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    recordatorio_enviado = Column(Integer, default=0)
    paciente = relationship("Paciente", back_populates="citas")
    slot = relationship("Slot")


class EventoSistema(Base):
    """EventBus persistente: auditoría completa y trazabilidad (sección 4.4 del informe)."""
    __tablename__ = "eventos"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(80), nullable=False)          # p.ej. cita.creada, recordatorio.enviado
    agente = Column(String(80), nullable=False)        # agente emisor
    payload = Column(JSONB, nullable=False, default=dict)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_session():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal()


def init_db():
    Base.metadata.create_all(get_engine())
