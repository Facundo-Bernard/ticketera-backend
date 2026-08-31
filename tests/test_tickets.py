import io
import sys
import os
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

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Service is running"}

def test_ticket_crud_and_gridfs_flow(client):
    # 1. Crear un ticket con formulario y fotos adjuntas todo en una sola petición
    form_data = {
        "titulo": "Falla en monitor principal",
        "descripcion": "La pantalla no enciende tras corte de luz",
        "correo": "soporte@coopya.com",
        "prioridad": "alta",
        "asignar": "Tecnico Redes"
    }
    fake_img1 = b"\x89PNG_IMAGE_1_DATA"
    fake_img2 = b"\x89PNG_IMAGE_2_DATA"
    files = [
        ("files", ("captura_1.png", io.BytesIO(fake_img1), "image/png")),
        ("files", ("captura_2.png", io.BytesIO(fake_img2), "image/png"))
    ]
    create_res = client.post("/api/v1/tickets/", data=form_data, files=files)
    assert create_res.status_code == 201, f"Error al crear: {create_res.text}"
    ticket = create_res.json()
    
    # Validaciones de reglas de negocio iniciales
    assert ticket["titulo"] == form_data["titulo"]
    assert ticket["correo"] == form_data["correo"]
    assert ticket["prioridad"] == "alta"
    assert ticket["estado"] == "abierto"
    assert ticket["identificador"].startswith("TCK-")
    assert ticket["fecha_edicion"] is None
    assert len(ticket["imagenes"]) == 2
    
    ticket_id = ticket["id"]
    image_url_1 = ticket["imagenes"][0]
    image_url_2 = ticket["imagenes"][1]
    assert image_url_1.startswith("/api/v1/files/")
    assert image_url_2.startswith("/api/v1/files/")

    # 2. Obtener el ticket por ID
    get_res = client.get(f"/api/v1/tickets/{ticket_id}")
    assert get_res.status_code == 200
    assert get_res.json()["identificador"] == ticket["identificador"]

    # 3. Subir una imagen extra posterior (POST /{id}/images)
    fake_img3 = b"\x89PNG_IMAGE_3_DATA"
    files_extra = [
        ("files", ("captura_3.png", io.BytesIO(fake_img3), "image/png"))
    ]
    img_res = client.post(f"/api/v1/tickets/{ticket_id}/images", files=files_extra)
    assert img_res.status_code == 200, f"Error al subir imagen extra: {img_res.text}"
    ticket_con_imagenes = img_res.json()
    
    assert len(ticket_con_imagenes["imagenes"]) == 3
    assert ticket_con_imagenes["fecha_edicion"] is not None
    image_url_3 = ticket_con_imagenes["imagenes"][2]

    # 4. Descargar las imágenes desde GridFS y verificar contenido
    file_res1 = client.get(image_url_1)
    assert file_res1.status_code == 200
    assert file_res1.content == fake_img1

    file_res2 = client.get(image_url_2)
    assert file_res2.status_code == 200
    assert file_res2.content == fake_img2

    # 5. Eliminar una imagen específica del ticket (DELETE /{id}/images/{file_id})
    file_id_to_delete = image_url_1.split("/")[-1]
    del_img_res = client.delete(f"/api/v1/tickets/{ticket_id}/images/{file_id_to_delete}")
    assert del_img_res.status_code == 200
    ticket_after_img_del = del_img_res.json()
    assert len(ticket_after_img_del["imagenes"]) == 2
    assert image_url_1 not in ticket_after_img_del["imagenes"]

    # Verificar que el archivo fue eliminado físicamente de GridFS (404)
    file_deleted_res = client.get(image_url_1)
    assert file_deleted_res.status_code == 404

    # 6. Actualizar campos del ticket con PATCH
    patch_payload = {
        "estado": "en_progreso",
        "prioridad": "critica"
    }
    patch_res = client.patch(f"/api/v1/tickets/{ticket_id}", json=patch_payload)
    assert patch_res.status_code == 200
    updated_ticket = patch_res.json()
    assert updated_ticket["estado"] == "en_progreso"
    assert updated_ticket["prioridad"] == "critica"

    # 7. Eliminar el ticket completo (DELETE) y limpiar sus fotos restantes
    delete_res = client.delete(f"/api/v1/tickets/{ticket_id}")
    assert delete_res.status_code == 204

    # 8. Verificar que el ticket ya no existe (404 Exception Handler)
    not_found_res = client.get(f"/api/v1/tickets/{ticket_id}")
    assert not_found_res.status_code == 404
    assert not_found_res.json()["error"] == "Not Found"

def test_ticket_filters(client):
    # Crear tickets para probar filtros
    client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Filtro 1",
        "descripcion": "Problema con impresora",
        "correo": "user1@coopya.com",
        "prioridad": "baja",
        "asignar": "Carlos Tecnico"
    })
    client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Filtro 2",
        "descripcion": "Problema con servidor",
        "correo": "user2@coopya.com",
        "prioridad": "alta",
        "asignar": "Maria Redes"
    })

    # 1. Filtrar por estado 'abierto'
    res_estado = client.get("/api/v1/tickets/?estado=abierto")
    assert res_estado.status_code == 200
    tickets_abiertos = res_estado.json()
    assert all(t["estado"] == "abierto" for t in tickets_abiertos)

    # 2. Filtrar por asignado 'Carlos'
    res_asignado = client.get("/api/v1/tickets/?asignar=Carlos")
    assert res_asignado.status_code == 200
    tickets_carlos = res_asignado.json()
    assert len(tickets_carlos) >= 1
    assert any("Carlos" in t["asignar"] for t in tickets_carlos)

    # 3. Filtrar por rango de fechas (desde hoy temprano hasta mañana)
    from datetime import datetime, timezone, timedelta
    ahora = datetime.now(timezone.utc)
    desde = (ahora - timedelta(hours=1)).isoformat()
    hasta = (ahora + timedelta(hours=1)).isoformat()
    res_fechas = client.get("/api/v1/tickets/", params={"fecha_desde": desde, "fecha_hasta": hasta})
    assert res_fechas.status_code == 200, f"Error en filtro de fechas: {res_fechas.text}"
    assert len(res_fechas.json()) >= 2

def test_catalog_endpoints(client):
    # 1. Estados
    res_estados = client.get("/api/v1/catalogs/estados")
    assert res_estados.status_code == 200
    estados = res_estados.json()
    assert len(estados) == 4
    assert any(e["value"] == "abierto" for e in estados)

    # 2. Prioridades
    res_prioridades = client.get("/api/v1/catalogs/prioridades")
    assert res_prioridades.status_code == 200
    prioridades = res_prioridades.json()
    assert len(prioridades) == 4
    assert any(p["value"] == "alta" for p in prioridades)

    # 3. Asignables
    res_asignables = client.get("/api/v1/catalogs/asignables")
    assert res_asignables.status_code == 200
    asignables = res_asignables.json()
    assert len(asignables) >= 3
    assert any(a["id"] == "soporte_tecnico" for a in asignables)

def test_invalid_file_upload_rejected(client):
    # Intentar crear un ticket adjuntando un PDF o archivo no soportado
    form_data = {
        "titulo": "Ticket con archivo inválido",
        "descripcion": "Intentando subir un PDF o script malicioso",
        "correo": "seguridad@coopya.com"
    }
    fake_pdf = b"%PDF-1.4 Fake PDF content"
    files = [
        ("files", ("documento.pdf", io.BytesIO(fake_pdf), "application/pdf"))
    ]
    res = client.post("/api/v1/tickets/", data=form_data, files=files)
    assert res.status_code == 400
    assert "no es una imagen válida" in res.json()["message"]

if __name__ == "__main__":
    import sys
    print("Ejecutando suite de pruebas...")
    with TestClient(app) as test_client:
        test_health_check(test_client)
        print(" [OK] test_health_check")
        test_ticket_crud_and_gridfs_flow(test_client)
        print(" [OK] test_ticket_crud_and_gridfs_flow")
        test_ticket_filters(test_client)
        print(" [OK] test_ticket_filters")
        test_catalog_endpoints(test_client)
        print(" [OK] test_catalog_endpoints")
        test_invalid_file_upload_rejected(test_client)
        print(" [OK] test_invalid_file_upload_rejected")
    print("\n Todas las pruebas pasaron exitosamente!")
