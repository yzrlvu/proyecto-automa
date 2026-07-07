"""Pruebas del API (health y métricas) con TestClient."""
from fastapi.testclient import TestClient


def test_health_y_metricas(session):
    from app.main import app
    with TestClient(app) as client:
        r = client.get("/api/v1/health")
        assert r.status_code == 200 and r.json()["status"] == "ok"
        m = client.get("/api/v1/metricas")
        assert m.status_code == 200 and "citas_totales" in m.json()
