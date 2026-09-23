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

@fixture_decorator
def client():
    with TestClient(app) as test_client:
        yield test_client

def get_auth_headers(client):
    """Obtiene la cabecera Bearer Token usando el usuario admin genérico."""
    res_login = client.post("/api/v1/auth/login", json={"email": "admin@coopya.com", "password": "admin"})
    assert res_login.status_code == 200, f"Error en login admin: {res_login.text}"
    token = res_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_create_and_get_candidato_flow(client):
    auth_headers = get_auth_headers(client)
    uid = uuid.uuid4().hex[:6]
    payload = {
        "nombreCompleto": f"María González {uid}",
        "dni": f"30{uid[:6]}",
        "email": f"maria_{uid}@email.com",
        "telefono": "+54 11 5555-5555",
        "direccion": "Av. Corrientes 1234, CABA",
        "genero": "female",
        "edad": 42,
        "situacionLaboral": "graciable",
        "ingresoMensual": 400000,
        "moneda": "ARS",
        "bancosSeleccionados": ["nacion", "provincia"],
        "productoSeleccionado": {
            "familia": "Asistodo",
            "plan": "1",
            "monto": 400000,
            "plazoMeses": 12
        },
        "origen": "web"
    }

    # 1. Crear candidato (POST es público - sin token)
    res_post = client.post("/api/v1/candidatos", json=payload)
    assert res_post.status_code == 201, f"Error al crear: {res_post.text}"
    created = res_post.json()

    assert "id" in created
    assert created["id"] is not None
    assert created["nombreCompleto"] == payload["nombreCompleto"]
    assert created["dni"] == payload["dni"]
    assert created["email"] == payload["email"]
    assert created["telefono"] == payload["telefono"]
    assert created["direccion"] == payload["direccion"]
    assert created["genero"] == "female"
    assert created["edad"] == 42
    assert created["situacionLaboral"] == "graciable"
    assert created["ingresoMensual"] == 400000.0
    assert created["moneda"] == "ARS"
    assert created["bancosSeleccionados"] == ["nacion", "provincia"]
    assert created["productoSeleccionado"] == payload["productoSeleccionado"]
    assert created["origen"] == "web"
    assert "fechaCreacion" in created

    candidato_id = created["id"]

    # 2. Consultar candidato sin autenticación (debe rechazar con 401)
    res_no_auth = client.get(f"/api/v1/candidatos/{candidato_id}")
    assert res_no_auth.status_code in [401, 403]

    # 3. Consultar candidato por ID con Bearer Token (GET /{id} -> 200)
    res_get = client.get(f"/api/v1/candidatos/{candidato_id}", headers=auth_headers)
    assert res_get.status_code == 200
    fetched = res_get.json()
    assert fetched["id"] == candidato_id
    assert fetched["dni"] == payload["dni"]
    assert fetched["email"] == payload["email"]

    # 4. Listar candidatos sin token (debe rechazar con 401)
    res_list_no_auth = client.get("/api/v1/candidatos?limit=50")
    assert res_list_no_auth.status_code in [401, 403]

    # 5. Listar candidatos con Bearer Token (GET / -> 200)
    res_list = client.get("/api/v1/candidatos?limit=50", headers=auth_headers)
    assert res_list.status_code == 200
    candidatos_list = res_list.json()
    assert isinstance(candidatos_list, list)
    assert any(c["id"] == candidato_id for c in candidatos_list)

def test_candidato_not_found(client):
    auth_headers = get_auth_headers(client)
    fake_id = "507f1f77bcf86cd799439011"
    res = client.get(f"/api/v1/candidatos/{fake_id}", headers=auth_headers)
    assert res.status_code == 404
    assert "no encontrado" in res.json().get("message", "")

def test_candidato_validation_errors(client):
    # Payload sin campos requeridos (POST público)
    bad_payload = {
        "nombreCompleto": "Incompleto"
    }
    res = client.post("/api/v1/candidatos", json=bad_payload)
    assert res.status_code == 422

    # Edad menor a 18
    invalid_age_payload = {
        "nombreCompleto": "Menor de Edad",
        "dni": "45123456",
        "email": "menor@email.com",
        "telefono": "+54 11 1234-5678",
        "direccion": "Calle Falsa 123",
        "genero": "male",
        "edad": 15,
        "situacionLaboral": "estudiante",
        "ingresoMensual": 50000,
        "productoSeleccionado": {
            "familia": "Asistodo",
            "plan": "1",
            "monto": 50000,
            "plazoMeses": 6
        }
    }
    res_age = client.post("/api/v1/candidatos", json=invalid_age_payload)
    assert res_age.status_code == 422

def test_delete_candidato_flow(client):
    auth_headers = get_auth_headers(client)
    uid = uuid.uuid4().hex[:6]
    payload = {
        "nombreCompleto": f"Para Eliminar {uid}",
        "dni": f"31{uid[:6]}",
        "email": f"eliminar_{uid}@email.com",
        "telefono": "+54 11 4444-4444",
        "direccion": "Calle Falsa 456",
        "genero": "male",
        "edad": 30,
        "situacionLaboral": "relacion_dependencia",
        "ingresoMensual": 350000,
        "moneda": "ARS",
        "bancosSeleccionados": ["santander"],
        "productoSeleccionado": {
            "familia": "Prestamo",
            "plan": "A",
            "monto": 200000,
            "plazoMeses": 6
        },
        "origen": "mobile"
    }

    # 1. Crear candidato (público)
    res_post = client.post("/api/v1/candidatos", json=payload)
    assert res_post.status_code == 201
    cand_id = res_post.json()["id"]

    # 2. Intento de eliminar sin token -> 401/403
    res_del_no_auth = client.delete(f"/api/v1/candidatos/{cand_id}")
    assert res_del_no_auth.status_code in [401, 403]

    # 3. Eliminar candidato autenticado (DELETE -> 204)
    res_del = client.delete(f"/api/v1/candidatos/{cand_id}", headers=auth_headers)
    assert res_del.status_code == 204

    # 4. Verificar que ya no existe (GET -> 404)
    res_get = client.get(f"/api/v1/candidatos/{cand_id}", headers=auth_headers)
    assert res_get.status_code == 404

    # 5. Intentar eliminarlo de nuevo (DELETE -> 404)
    res_del_again = client.delete(f"/api/v1/candidatos/{cand_id}", headers=auth_headers)
    assert res_del_again.status_code == 404
