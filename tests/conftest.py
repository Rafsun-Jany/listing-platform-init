import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite://")
os.environ.setdefault("GATEWAY_SECRET", "test-gateway-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from order_api.database import Base, get_db
from order_api.main import app
from order_api.models import Product


@pytest.fixture
def client():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def configure_sqlite_transaction(connection, _record):
        connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def begin_sqlite_transaction(connection):
        connection.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as db:
        db.add_all([
            Product(id=501, name="Product 501", unit_price="50.00", stock=5, active=True),
            Product(id=502, name="Product 502", unit_price="25.50", stock=3, active=True),
        ])

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client, factory
    app.dependency_overrides.clear()
    engine.dispose()


def headers(subject="customer-a", role="customer", key=None):
    result = {
        "x-gateway-secret": "test-gateway-secret",
        "x-consumer-id": subject,
        "x-consumer-role": role,
    }
    if key is not None:
        result["Idempotency-Key"] = key
    return result
