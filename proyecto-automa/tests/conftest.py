"""Fixtures: base de datos PostgreSQL de prueba (usa TEST_DATABASE_URL o docker-compose)."""
import os

import pytest

os.environ.setdefault("DATABASE_URL", os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/citas_test"))

from app.models.db import Base, get_engine, get_session  # noqa: E402


@pytest.fixture()
def session():
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = get_session()
    yield s
    s.close()
