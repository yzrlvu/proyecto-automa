"""Pruebas unitarias de las tools transaccionales (requieren PostgreSQL de prueba)."""
from datetime import date, time, timedelta

import pytest

from app.models.db import Cita, Doctor, Especialidad, EstadoCita, Paciente, Slot
from app.tools.citas_tools import (
    cancelar_cita, confirmar_cita, consultar_disponibilidad,
    registrar_paciente, reservar_cita, verificar_seguro,
)

MANANA = (date.today() + timedelta(days=1)).isoformat()


@pytest.fixture()
def datos(session):
    doc = Doctor(nombre="Elena Vásquez", especialidad=Especialidad.CARDIOLOGIA)
    session.add(doc); session.flush()
    slot = Slot(doctor_id=doc.id, fecha=date.fromisoformat(MANANA), hora=time(9, 0))
    pac = Paciente(dni="12345678", nombre="Juan Pérez")
    session.add_all([slot, pac]); session.commit()
    return {"slot_id": slot.id}


def test_consultar_disponibilidad(datos):
    out = consultar_disponibilidad.invoke({"especialidad": "cardiologia", "fecha": MANANA})
    assert "Elena Vásquez" in out and "slot_id=" in out


def test_reserva_y_confirmacion(datos):
    out = reservar_cita.invoke({"dni": "12345678", "slot_id": datos["slot_id"]})
    assert "PENDIENTE" in out
    cita_id = out.split("cita_id=")[1].split(".")[0]
    out2 = confirmar_cita.invoke({"dni": "12345678", "cita_id": cita_id})
    assert "confirmada" in out2


def test_doble_reserva_bloqueada(datos):
    reservar_cita.invoke({"dni": "12345678", "slot_id": datos["slot_id"]})
    out = reservar_cita.invoke({"dni": "12345678", "slot_id": datos["slot_id"]})
    assert "ya no está disponible" in out


def test_cancelacion_libera_cupo(datos, session):
    out = reservar_cita.invoke({"dni": "12345678", "slot_id": datos["slot_id"]})
    cita_id = out.split("cita_id=")[1].split(".")[0]
    cancelar_cita.invoke({"dni": "12345678", "cita_id": cita_id})
    slot = session.get(Slot, datos["slot_id"])
    session.refresh(slot)
    assert slot.disponible == 1


def test_registro_paciente(session):
    out = registrar_paciente.invoke({"dni": "87654321", "nombre": "Ana Torres"})
    assert "registrado" in out


def test_verificar_seguro():
    assert "VERIFICADA" in verificar_seguro.invoke({"dni": "12345678", "aseguradora": "Rímac"})
    assert "particular" in verificar_seguro.invoke({"dni": "12345678", "aseguradora": "OtraSA"})
