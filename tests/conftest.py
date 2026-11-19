import os
import sys
from typing import Dict
from unittest.mock import AsyncMock, patch

import pytest
from pymongo import MongoClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Aislar siempre los tests en una base dedicada local para no tocar datos reales
TEST_DB_NAME = "tickets_db_test"
TEST_MONGO_URI = f"mongodb://127.0.0.1:27017/{TEST_DB_NAME}"

from src.config.settings import settings  # noqa: E402

settings.MONGO_DB_NAME = TEST_DB_NAME
settings.MONGO_URI = TEST_MONGO_URI
settings.MASTER_ADMIN_EMAIL = "admin_test@sistemas.com"
settings.MASTER_ADMIN_PASSWORD = "TestAdminPassword123!"
settings.JWT_SECRET_KEY = "test_secret_key_for_pytest_only_32chars_long"
if "admin_test@sistemas.com" not in settings.ADMIN_EMAILS:
    settings.ADMIN_EMAILS.append("admin_test@sistemas.com")


@pytest.fixture(scope="session", autouse=True)
def isolated_test_database():
    """Limpia la base de pruebas local antes y después de la corrida completa."""
    client = MongoClient(TEST_MONGO_URI, serverSelectionTimeoutMS=3000)
    client.drop_database(TEST_DB_NAME)
    yield
    client.drop_database(TEST_DB_NAME)
    client.close()


@pytest.fixture(autouse=True)
def reset_ip_rate_limit():
    """Evita que el rate limit en memoria por IP bloquee tests independientes en TestClient."""
    from src.services.rate_limit_service import _ip_requests

    _ip_requests.clear()
    yield
    _ip_requests.clear()


@pytest.fixture(autouse=True)
def silence_push_notifications_in_tests():
    """Silencia el envío de notificaciones Web Push reales durante los tests."""
    with patch(
        "src.modules.notifications.service.NotificationService.broadcast",
        new_callable=AsyncMock,
    ) as mock_broadcast:
        mock_broadcast.return_value = 0
        yield mock_broadcast


def login_admin_headers(client) -> Dict[str, str]:
    """Helper compartido para autenticar el cliente de pruebas como admin sin dejar cookies residuales."""
    res = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.MASTER_ADMIN_EMAIL,
            "password": settings.MASTER_ADMIN_PASSWORD,
        },
    )
    assert res.status_code == 200, f"Error en login de test: {res.text}"
    token = res.json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}
