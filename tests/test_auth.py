import sys
import os
import uuid
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import pytest
    fixture_decorator = pytest.fixture(scope="module")
except ImportError:
    def fixture_decorator(func):
        return func

from starlette.testclient import TestClient
from src.main import app
from src.modules.auth.security import decode_access_token

@fixture_decorator
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_register_endpoint_is_disabled(client):
    """Verifica que el endpoint /register se encuentre deshabilitado (404/405)."""
    res = client.post("/api/v1/auth/register", json={
        "email": "test@coopya.com",
        "password": "password123",
        "nombre": "Test",
        "rol": "operador"
    })
    assert res.status_code in [404, 405], f"Se esperaba 404/405 pero retornó: {res.status_code}"

def test_auth_login_and_me_flow(client):
    """Verifica el flujo completo de autenticación y consulta de perfil con el usuario inicial."""
    # 1. Login con contraseña errónea (POST /api/v1/auth/login) -> 401
    bad_login = {
        "email": "admin@coopya.com",
        "password": "WrongPassword!"
    }
    res_bad = client.post("/api/v1/auth/login", json=bad_login)
    assert res_bad.status_code == 401

    # 2. Login con usuario inexistente -> 401
    fake_login = {
        "email": "noexiste@coopya.com",
        "password": "admin"
    }
    res_fake = client.post("/api/v1/auth/login", json=fake_login)
    assert res_fake.status_code == 401

    # 3. Login exitoso con admin@coopya.com / admin -> 200
    good_login = {
        "email": "admin@coopya.com",
        "password": "admin"
    }
    res_login = client.post("/api/v1/auth/login", json=good_login)
    assert res_login.status_code == 200
    token_resp = res_login.json()
    assert "access_token" in token_resp
    assert token_resp["token_type"] == "bearer"
    assert token_resp["user"]["email"] == "admin@coopya.com"
    assert token_resp["user"]["rol"] == "admin"
    token = token_resp["access_token"]

    # 4. Obtener perfil actual con Bearer Token (GET /api/v1/auth/me) -> 200
    headers = {"Authorization": f"Bearer {token}"}
    res_me = client.get("/api/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    me_data = res_me.json()
    assert me_data["email"] == "admin@coopya.com"
    assert me_data["rol"] == "admin"

    # 5. Intentar acceder a /me sin token -> 401 o 403
    res_no_token = client.get("/api/v1/auth/me")
    assert res_no_token.status_code in [401, 403]

    # 6. Intentar acceder a /me con token inválido -> 401
    res_fake_token = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token_invalido_123"})
    assert res_fake_token.status_code == 401

def test_default_admin_user_and_long_token_expiration(client):
    """Valida que el token emitido tenga vigencia prolongada (> 300 días)."""
    login_payload = {
        "email": "admin@coopya.com",
        "password": "admin"
    }
    res = client.post("/api/v1/auth/login", json=login_payload)
    assert res.status_code == 200
    data = res.json()

    token = data["access_token"]
    payload = decode_access_token(token)
    assert "exp" in payload and "iat" in payload
    expiration_duration_seconds = payload["exp"] - payload["iat"]
    # 365 días son 31,536,000 segundos. Validamos que supere 300 días
    assert expiration_duration_seconds >= 300 * 24 * 3600
