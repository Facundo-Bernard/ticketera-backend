import pytest
from starlette.testclient import TestClient

from src.config.settings import settings
from src.main import app
from src.modules.auth.security import decode_access_token


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_register_endpoint_is_disabled(client):
    """Verifica que el endpoint /register se encuentre deshabilitado (404/405)."""
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@coopya.com",
            "password": "password123",
            "nombre": "Test",
            "rol": "operador",
        },
    )
    assert res.status_code in [404, 405], f"Se esperaba 404/405 pero retornó: {res.status_code}"


def test_auth_login_and_me_flow(client):
    """Verifica login, cookie HttpOnly, Bearer Token y logout."""
    # 1. Login con contraseña errónea -> 401
    res_bad = client.post(
        "/api/v1/auth/login",
        json={"email": settings.MASTER_ADMIN_EMAIL, "password": "WrongPassword!"},
    )
    assert res_bad.status_code == 401

    # 2. Login con usuario inexistente -> 401
    res_fake = client.post(
        "/api/v1/auth/login",
        json={"email": "noexiste@coopya.com", "password": "admin"},
    )
    assert res_fake.status_code == 401

    # 3. Login exitoso -> 200 + cookie HttpOnly
    res_login = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.MASTER_ADMIN_EMAIL,
            "password": settings.MASTER_ADMIN_PASSWORD,
        },
    )
    assert res_login.status_code == 200
    token_resp = res_login.json()
    assert "access_token" in token_resp
    assert token_resp["token_type"] == "bearer"
    assert token_resp["user"]["email"] == settings.MASTER_ADMIN_EMAIL
    assert token_resp["user"]["rol"] == "admin"
    assert "coopya_auth_token" in res_login.cookies
    token = token_resp["access_token"]

    # 4. Consultar /me usando cookie HttpOnly o Bearer Token -> 200
    res_me_cookie = client.get("/api/v1/auth/me")
    assert res_me_cookie.status_code == 200
    assert res_me_cookie.json()["email"] == settings.MASTER_ADMIN_EMAIL

    res_me_bearer = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res_me_bearer.status_code == 200
    assert res_me_bearer.json()["rol"] == "admin"

    # 5. Logout limpia la cookie de sesión
    res_logout = client.post("/api/v1/auth/logout")
    assert res_logout.status_code == 200

    res_no_token = client.get("/api/v1/auth/me")
    assert res_no_token.status_code in [401, 403]

    # 6. Token inválido -> 401
    res_fake_token = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer token_invalido_123"})
    assert res_fake_token.status_code == 401


def test_default_admin_user_and_token_expiration(client):
    """Valida que la expiración del JWT coincida con ACCESS_TOKEN_EXPIRE_MINUTES."""
    res = client.post(
        "/api/v1/auth/login",
        json={
            "email": settings.MASTER_ADMIN_EMAIL,
            "password": settings.MASTER_ADMIN_PASSWORD,
        },
    )
    assert res.status_code == 200
    token = res.json()["access_token"]

    payload = decode_access_token(token)
    assert "exp" in payload and "iat" in payload
    expiration_duration_seconds = payload["exp"] - payload["iat"]
    assert expiration_duration_seconds == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_notifications_endpoints_require_auth(client):
    """Verifica que los endpoints mutantes de Web Push exijan autenticación."""
    client.cookies.clear()
    res_sub = client.post(
        "/api/v1/notifications/subscribe",
        json={"endpoint": "https://example.com/push/1", "keys": {"p256dh": "k1", "auth": "a1"}},
    )
    assert res_sub.status_code == 401

    res_unsub = client.post("/api/v1/notifications/unsubscribe?endpoint=https://example.com/push/1")
    assert res_unsub.status_code == 401

    res_test = client.post(
        "/api/v1/notifications/test",
        json={"title": "Test", "body": "Body"},
    )
    assert res_test.status_code == 401


def test_operators_crud_and_rbac_flow(client):
    """Verifica el ABM completo de operadores, RBAC admin/operador y sincronía con asignables."""
    from tests.conftest import login_admin_headers

    client.cookies.clear()
    # 1. Sin auth rechaza
    assert client.get("/api/v1/auth/users").status_code == 401

    admin_headers = login_admin_headers(client)

    # 2. Listar usuarios iniciales (incluye admin seed)
    res_list = client.get("/api/v1/auth/users", headers=admin_headers)
    assert res_list.status_code == 200
    users = res_list.json()
    assert any(u["email"] == settings.MASTER_ADMIN_EMAIL for u in users)

    # 3. Crear un nuevo operador
    op_email = "operador_abm@coopya.com"
    res_create = client.post(
        "/api/v1/auth/users",
        json={
            "email": op_email,
            "nombre": "Laura Gomez",
            "password": "ClaveSegura123",
            "rol": "operador",
        },
        headers=admin_headers,
    )
    assert res_create.status_code == 201, res_create.text
    created = res_create.json()
    op_id = created["id"]
    assert created["email"] == op_email
    assert created["rol"] == "operador"
    assert created["activo"] is True

    # 4. Verificar que aparece en /catalogs/asignables
    res_asig = client.get("/api/v1/catalogs/asignables")
    assert res_asig.status_code == 200
    assert any(a["label"] == "Laura Gomez" for a in res_asig.json())

    # 5. El operador puede loguearse pero NO acceder al ABM de usuarios (403)
    res_op_login = client.post(
        "/api/v1/auth/login",
        json={"email": op_email, "password": "ClaveSegura123"},
    )
    assert res_op_login.status_code == 200
    op_token = res_op_login.json()["access_token"]
    client.cookies.clear()
    op_headers = {"Authorization": f"Bearer {op_token}"}
    assert client.get("/api/v1/auth/users", headers=op_headers).status_code == 403

    # 6. Admin actualiza nombre, contraseña y lo desactiva
    res_patch = client.patch(
        f"/api/v1/auth/users/{op_id}",
        json={"nombre": "Laura Gomez Mod", "password": "NuevaClave456", "activo": False},
        headers=admin_headers,
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["nombre"] == "Laura Gomez Mod"
    assert res_patch.json()["activo"] is False

    # Operador inactivo no puede loguearse ni aparecer en asignables
    res_inactive_login = client.post(
        "/api/v1/auth/login",
        json={"email": op_email, "password": "NuevaClave456"},
    )
    assert res_inactive_login.status_code == 401
    res_asig_after = client.get("/api/v1/catalogs/asignables")
    assert all(a["label"] != "Laura Gomez Mod" for a in res_asig_after.json())

    # 7. Admin no puede auto-desactivarse ni auto-eliminarse
    master_user = next(u for u in users if u["email"] == settings.MASTER_ADMIN_EMAIL)
    assert (
        client.patch(
            f"/api/v1/auth/users/{master_user['id']}",
            json={"activo": False},
            headers=admin_headers,
        ).status_code
        == 400
    )
    assert (
        client.delete(f"/api/v1/auth/users/{master_user['id']}", headers=admin_headers).status_code
        == 400
    )

    # 8. Admin elimina al operador creado
    assert client.delete(f"/api/v1/auth/users/{op_id}", headers=admin_headers).status_code == 204
    assert all(u["id"] != op_id for u in client.get("/api/v1/auth/users", headers=admin_headers).json())
