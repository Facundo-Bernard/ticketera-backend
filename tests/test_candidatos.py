import sys
import os
import io
import json
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

def test_create_and_get_candidato_with_papeleria_pdf_flow(client):
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

    pdf_content = b"%PDF-1.4 mock binary content for testing papeleria"

    # 1. Crear candidato con archivo PDF adjunto (POST multipart/form-data es público)
    res_post = client.post(
        "/api/v1/candidatos",
        data={"data": json.dumps(payload)},
        files={"papeleria": ("recibo_sueldo.pdf", io.BytesIO(pdf_content), "application/pdf")}
    )
    assert res_post.status_code == 201, f"Error al crear: {res_post.text}"
    created = res_post.json()

    assert "id" in created
    assert created["id"] is not None
    assert created["nombreCompleto"] == payload["nombreCompleto"]
    assert created["dni"] == payload["dni"]
    assert created["email"] == payload["email"]
    assert "papeleria" in created
    assert created["papeleria"].startswith("/api/v1/candidatos/papeleria/")

    candidato_id = created["id"]
    papeleria_url = created["papeleria"]

    # 2. Consultar candidato sin autenticación (debe rechazar con 401/403)
    res_no_auth = client.get(f"/api/v1/candidatos/{candidato_id}")
    assert res_no_auth.status_code in [401, 403]

    # 3. Consultar candidato por ID con Bearer Token (GET /{id} -> 200)
    res_get = client.get(f"/api/v1/candidatos/{candidato_id}", headers=auth_headers)
    assert res_get.status_code == 200
    fetched = res_get.json()
    assert fetched["id"] == candidato_id
    assert fetched["dni"] == payload["dni"]
    assert fetched["papeleria"] == papeleria_url

    # 4. Descargar / Ver Papelería sin autenticación (debe rechazar con 401/403)
    res_pap_no_auth = client.get(papeleria_url)
    assert res_pap_no_auth.status_code in [401, 403]

    # 5. Descargar / Ver Papelería con autenticación usando la URL con File ID (GET /papeleria/{file_id} -> 200)
    res_pap = client.get(papeleria_url, headers=auth_headers)
    assert res_pap.status_code == 200
    assert res_pap.content == pdf_content
    assert "application/pdf" in res_pap.headers.get("content-type", "")
    assert "inline" in res_pap.headers.get("content-disposition", "")

    # 6. Listar candidatos con Bearer Token (GET / -> 200)
    res_list = client.get("/api/v1/candidatos?limit=50", headers=auth_headers)
    assert res_list.status_code == 200
    candidatos_list = res_list.json()
    assert isinstance(candidatos_list, list)
    assert any(c["id"] == candidato_id for c in candidatos_list)

def test_create_candidato_without_papeleria(client):
    auth_headers = get_auth_headers(client)
    uid = uuid.uuid4().hex[:6]
    payload = {
        "nombreCompleto": f"Sin Papeleria {uid}",
        "dni": f"32{uid[:6]}",
        "email": f"sin_papeleria_{uid}@email.com",
        "telefono": "+54 11 9999-8888",
        "direccion": "Av. Santa Fe 123",
        "genero": "male",
        "edad": 35,
        "situacionLaboral": "relacion_dependencia",
        "ingresoMensual": 500000,
        "moneda": "ARS",
        "productoSeleccionado": {
            "familia": "Asistodo",
            "plan": "2",
            "monto": 500000,
            "plazoMeses": 24
        }
    }

    # Creación enviando data pero sin archivo papeleria
    res = client.post("/api/v1/candidatos", data={"data": json.dumps(payload)})
    assert res.status_code == 201
    cand = res.json()
    assert cand["papeleria"] is None

def test_candidato_validation_and_file_errors(client):
    # 1. Payload con JSON mal formado en 'data' -> 400 o 422
    res_bad_json = client.post("/api/v1/candidatos", data={"data": "{ esto no es json valido }"})
    assert res_bad_json.status_code in [400, 422]

    # 2. Payload sin campos requeridos -> 422
    bad_payload = {"nombreCompleto": "Incompleto"}
    res_missing = client.post("/api/v1/candidatos", data={"data": json.dumps(bad_payload)})
    assert res_missing.status_code == 422

    # 3. Edad menor a 18 -> 422
    underage_payload = {
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
    res_age = client.post("/api/v1/candidatos", data={"data": json.dumps(underage_payload)})
    assert res_age.status_code == 422

    # 4. Formato de archivo no permitido (ej. ejecutable o zip) -> 400
    valid_payload = {
        "nombreCompleto": "Test Archivo Invalido",
        "dni": "35123456",
        "email": "archivo_invalido@email.com",
        "telefono": "+54 11 5555-5555",
        "direccion": "Av. Corrientes 1234",
        "genero": "female",
        "edad": 30,
        "situacionLaboral": "monotributista",
        "ingresoMensual": 300000,
        "productoSeleccionado": {
            "familia": "Asistodo",
            "plan": "1",
            "monto": 300000,
            "plazoMeses": 12
        }
    }
    res_bad_file = client.post(
        "/api/v1/candidatos",
        data={"data": json.dumps(valid_payload)},
        files={"papeleria": ("malicioso.exe", b"MZ fake executable content", "application/x-msdownload")}
    )
    assert res_bad_file.status_code == 400
    assert "no tiene un formato permitido" in res_bad_file.json().get("message", "")

def test_delete_candidato_with_papeleria_cascade_flow(client):
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

    img_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR mock image png bytes"

    # 1. Crear candidato con imagen PNG adjunta
    res_post = client.post(
        "/api/v1/candidatos",
        data={"data": json.dumps(payload)},
        files={"papeleria": ("dni_frente.png", io.BytesIO(img_content), "image/png")}
    )
    assert res_post.status_code == 201
    created_data = res_post.json()
    cand_id = created_data["id"]
    papeleria_url = created_data["papeleria"]

    # 2. Verificar que se pueda ver la imagen por su URL de file_id
    res_img = client.get(papeleria_url, headers=auth_headers)
    assert res_img.status_code == 200
    assert res_img.content == img_content

    # 3. Intento de eliminar sin token -> 401/403
    res_del_no_auth = client.delete(f"/api/v1/candidatos/{cand_id}")
    assert res_del_no_auth.status_code in [401, 403]

    # 4. Eliminar candidato autenticado (DELETE -> 204)
    res_del = client.delete(f"/api/v1/candidatos/{cand_id}", headers=auth_headers)
    assert res_del.status_code == 204

    # 5. Verificar que el candidato ya no existe (GET -> 404)
    res_get = client.get(f"/api/v1/candidatos/{cand_id}", headers=auth_headers)
    assert res_get.status_code == 404

    # 6. Verificar que el archivo en GridFS fue purgado en cascada (GET papeleria_url -> 404)
    res_pap_purged = client.get(papeleria_url, headers=auth_headers)
    assert res_pap_purged.status_code == 404

def test_candidato_endpoints_with_trailing_slash(client):
    auth_headers = get_auth_headers(client)
    uid = uuid.uuid4().hex[:6]
    payload = {
        "nombreCompleto": f"Trailing Slash {uid}",
        "dni": f"32{uid[:6]}",
        "email": f"slash_{uid}@email.com",
        "telefono": "+54 11 9999-9999",
        "direccion": "Avenida Siempre Viva 742",
        "genero": "other",
        "edad": 28,
        "situacionLaboral": "monotributista",
        "ingresoMensual": 600000,
        "moneda": "ARS",
        "bancosSeleccionados": ["macro"],
        "productoSeleccionado": {
            "familia": "Asistodo",
            "plan": "1",
            "monto": 300000,
            "plazoMeses": 12
        },
        "origen": "web"
    }

    # Probar POST con trailing slash sin seguir redirecciones (follow_redirects=False)
    res_post_slash = client.post(
        "/api/v1/candidatos/",
        data={"data": json.dumps(payload)},
        follow_redirects=False
    )
    assert res_post_slash.status_code == 201, f"Falló POST con barra: {res_post_slash.status_code} {res_post_slash.text}"

    # Probar GET con trailing slash sin seguir redirecciones (follow_redirects=False)
    res_get_slash = client.get(
        "/api/v1/candidatos/",
        headers=auth_headers,
        follow_redirects=False
    )
    assert res_get_slash.status_code == 200, f"Falló GET con barra: {res_get_slash.status_code} {res_get_slash.text}"

