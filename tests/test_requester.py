from datetime import datetime, timedelta, timezone
import io
import uuid

from pymongo import MongoClient
import pytest
from starlette.testclient import TestClient

from src.main import app
from tests.conftest import TEST_DB_NAME, TEST_MONGO_URI, login_admin_headers


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _backdate_ticket_creation(correo: str, days_ago: int = 2) -> None:
    """Simula tickets históricos antiguos para no activar el cooldown de 60s en tests."""
    mongo = MongoClient(TEST_MONGO_URI)
    past_dt = datetime.now(timezone.utc) - timedelta(days=days_ago)
    mongo[TEST_DB_NAME]["tickets"].update_many(
        {"correo": correo},
        {"$set": {"fecha_creacion": past_dt}},
    )
    mongo.close()


def _create_operator_headers(client: TestClient) -> dict[str, str]:
    uid = uuid.uuid4().hex[:6]
    email = f"op_{uid}@coopya.com"
    headers = login_admin_headers(client)
    res = client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={
            "email": email,
            "nombre": "Operador Pruebas",
            "password": "OperatorPassword123!",
            "rol": "operador",
        },
    )
    assert res.status_code == 201, res.text
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "OperatorPassword123!"},
    )
    assert login_res.status_code == 200, login_res.text
    token = login_res.json()["access_token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def test_local_tracking_isolation_and_minimal_dto(client: TestClient):
    uid = uuid.uuid4().hex[:6]
    admin_headers = login_admin_headers(client)
    alice_email = f"alice_{uid}@coopya.com"
    bob_email = f"bob_{uid}@coopya.com"

    # Admin crea ticket previo de Alice (simulando historial anterior de hace 2 días)
    old_alice_res = client.post(
        "/api/v1/tickets/",
        headers=admin_headers,
        data={
            "titulo": "Ticket viejo de Alice",
            "descripcion": "Creado antes en otra PC",
            "correo": alice_email,
            "prioridad": "alta",
            "asignar": "Tecnico Secreto",
        },
    )
    assert old_alice_res.status_code == 201, old_alice_res.text
    old_alice_id = old_alice_res.json()["id"]
    _backdate_ticket_creation(alice_email, days_ago=2)

    # Bob crea un ticket con adjunto
    bob_res = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Problema de Bob",
            "descripcion": "Privado de Bob",
            "correo": bob_email,
        },
        files=[("files", ("bob_doc.png", io.BytesIO(b"\x89PNG_BOB_SECRET"), "image/png"))],
    )
    assert bob_res.status_code == 201, bob_res.text
    bob_file_path = bob_res.json()["imagenes"][0]
    client.cookies.clear()

    # Alice crea un ticket desde su navegador limpio (sin estar logueada)
    alice_res = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Monitor roto en oficina",
            "descripcion": "No da imagen",
            "correo": alice_email,
            "registrar_seguimiento": "true",
        },
        files=[("files", ("monitor.png", io.BytesIO(b"\x89PNG_ALICE_OK"), "image/png"))],
    )
    assert alice_res.status_code == 201, alice_res.text
    alice_created = alice_res.json()
    alice_file_path = alice_created["imagenes"][0]

    # Consulta sus solicitudes desde esa PC: ve SOLO el recién creado, NO el viejo ni el de Bob
    list_res = client.get("/api/v1/requester/tickets")
    assert list_res.status_code == 200
    body = list_res.json()
    assert body["linked_email"] is None
    returned_ids = [item["id"] for item in body["items"]]
    assert alice_created["id"] in returned_ids
    assert old_alice_id not in returned_ids

    # DTO reducido: nunca incluye prioridad, asignar ni columna
    item = body["items"][0]
    for forbidden_key in ("asignar", "prioridad", "columna", "leido", "frecuencia"):
        assert forbidden_key not in item

    # Acceso a archivos: puede ver el suyo, pero NO el de Bob
    own_file_res = client.get(alice_file_path)
    assert own_file_res.status_code == 200
    assert own_file_res.content == b"\x89PNG_ALICE_OK"

    bob_file_res = client.get(bob_file_path)
    assert bob_file_res.status_code == 401
    client.cookies.clear()


def test_temporary_code_flow_operator_and_single_use_history(client: TestClient):
    uid = uuid.uuid4().hex[:6]
    admin_headers = login_admin_headers(client)
    op_headers = _create_operator_headers(client)
    user_email = f"hist_{uid}@coopya.com"

    # Crear 2 tickets previos de user_email (simulando historial en otra PC)
    for idx in range(2):
        res = client.post(
            "/api/v1/tickets/",
            headers=admin_headers,
            data={
                "titulo": f"Historial previo {idx}",
                "descripcion": "Detalle histórico",
                "correo": user_email,
                "prioridad": "critica",
                "asignar": "Admin Oculto",
            },
        )
        assert res.status_code == 201, res.text
        _backdate_ticket_creation(user_email, days_ago=idx + 1)

    client.cookies.clear()

    # Anónimo no puede listar ni generar códigos internos
    assert client.get("/api/v1/requester/codes").status_code == 401
    assert client.post("/api/v1/requester/codes", json={"correo": user_email}).status_code == 401

    # Solicitante pide código desde /crearticket-usuario (la respuesta NO filtra el código)
    req_res = client.post("/api/v1/requester/request-code", json={"correo": user_email})
    assert req_res.status_code == 200
    req_json = req_res.json()
    assert "codigo" not in req_json
    assert "expira_en" in req_json

    # Un OPERADOR (no solo Admin) puede listar y ver el código generado
    codes_res = client.get(f"/api/v1/requester/codes?q={user_email}", headers=op_headers)
    assert codes_res.status_code == 200
    codes = codes_res.json()
    assert len(codes) == 1
    assert codes[0]["estado"] == "pendiente"
    assert codes[0]["solicitado_por"] == "usuario"
    active_code = codes[0]["codigo"]

    # Código incorrecto falla
    bad_res = client.post(
        "/api/v1/requester/verify-code",
        json={"correo": user_email, "codigo": "000000" if active_code != "000000" else "999999"},
    )
    assert bad_res.status_code == 400

    # Código correcto desbloquea TODO su historial y setea cookie por 365 días
    ok_res = client.post(
        "/api/v1/requester/verify-code",
        json={"correo": user_email, "codigo": active_code},
    )
    assert ok_res.status_code == 200
    ok_body = ok_res.json()
    assert ok_body["linked_email"] == user_email
    assert len(ok_body["items"]) == 2
    assert all("asignar" not in item and "prioridad" not in item for item in ok_body["items"])

    # No puede reutilizarse el mismo código una segunda vez
    reuse_res = client.post(
        "/api/v1/requester/verify-code",
        json={"correo": user_email, "codigo": active_code},
    )
    assert reuse_res.status_code == 400

    # Con la cookie de sesión ya cargada, ve todo su historial aunque cierre/reabra
    hist_res = client.get("/api/v1/requester/tickets")
    assert hist_res.status_code == 200
    assert len(hist_res.json()["items"]) == 2

    # Con la cookie de sesión ya cargada, no permite enviar con otro correo distinto
    mismatch_res = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Intento otro correo",
            "descripcion": "No debe permitir otro mail mientras está vinculado",
            "correo": f"otro_{uid}@coopya.com",
            "registrar_seguimiento": "true",
        },
    )
    assert mismatch_res.status_code == 400

    # Desvincular sesión limpia el acceso
    logout_res = client.post("/api/v1/requester/logout")
    assert logout_res.status_code == 200
    after_logout = client.get("/api/v1/requester/tickets").json()
    assert after_logout["linked_email"] is None
    assert after_logout["items"] == []


def test_operator_generate_revoke_and_bruteforce_lockout(client: TestClient):
    uid = uuid.uuid4().hex[:6]
    op_headers = _create_operator_headers(client)
    user_email = f"brute_{uid}@coopya.com"

    # Operador genera código directo
    gen_res = client.post(
        "/api/v1/requester/codes",
        headers=op_headers,
        json={"correo": user_email},
    )
    assert gen_res.status_code == 201
    code_data = gen_res.json()
    assert code_data["solicitado_por"] == "operador"
    wrong_code = "111111" if code_data["codigo"] != "111111" else "222222"

    # 5 intentos fallidos anulan el código automáticamente
    for _ in range(5):
        r = client.post(
            "/api/v1/requester/verify-code",
            json={"correo": user_email, "codigo": wrong_code},
        )
        assert r.status_code == 400

    # Incluso intentando con el código real después de 5 fallos debe rechazarlo
    locked_res = client.post(
        "/api/v1/requester/verify-code",
        json={"correo": user_email, "codigo": code_data["codigo"]},
    )
    assert locked_res.status_code == 400

    # Operador genera otro y luego lo revoca manualmente
    gen2 = client.post(
        "/api/v1/requester/codes",
        headers=op_headers,
        json={"correo": user_email},
    )
    assert gen2.status_code == 201
    code2 = gen2.json()
    del_res = client.delete(f"/api/v1/requester/codes/{code2['id']}", headers=op_headers)
    assert del_res.status_code == 204

    revoked_verify = client.post(
        "/api/v1/requester/verify-code",
        json={"correo": user_email, "codigo": code2["codigo"]},
    )
    assert revoked_verify.status_code == 400
