"""Carga datos iniciales: 4 doctores y calendario de slots de 30 min (2 semanas)."""
from datetime import date, time, timedelta

from app.models.db import Doctor, Especialidad, Slot, get_session, init_db


def generar_horas():
    horas, h, m = [], 8, 0
    while h < 18:
        horas.append(time(h, m))
        m += 30
        if m == 60:
            h, m = h + 1, 0
    return horas


def main():
    init_db()
    session = get_session()
    if session.query(Doctor).count() > 0:
        print("Seed ya aplicado."); return
    doctores = [
        Doctor(nombre="Ricardo Paredes", especialidad=Especialidad.MEDICINA_GENERAL),
        Doctor(nombre="Elena Vásquez", especialidad=Especialidad.CARDIOLOGIA),
        Doctor(nombre="Carmen Ruiz", especialidad=Especialidad.PEDIATRIA),
        Doctor(nombre="Jorge Salinas", especialidad=Especialidad.DERMATOLOGIA),
    ]
    session.add_all(doctores); session.flush()
    hoy = date.today()
    n = 0
    for i in range(14):
        f = hoy + timedelta(days=i)
        if f.weekday() >= 5:  # sin domingos; sábado limitado
            if f.weekday() == 6: continue
        for d in doctores:
            if f.weekday() == 5 and d.especialidad in (Especialidad.CARDIOLOGIA, Especialidad.DERMATOLOGIA):
                continue
            horas = generar_horas() if f.weekday() < 5 else [h for h in generar_horas() if h < time(13, 0)]
            for h in horas:
                session.add(Slot(doctor_id=d.id, fecha=f, hora=h)); n += 1
    session.commit()
    print(f"Seed OK: {len(doctores)} doctores, {n} slots.")


if __name__ == "__main__":
    main()
