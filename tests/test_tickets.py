import io
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

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Service is running"}

def test_ticket_crud_and_gridfs_flow(client):
    uid = uuid.uuid4().hex[:6]
    # 1. Crear un ticket con formulario y fotos adjuntas todo en una sola petición
    form_data = {
        "titulo": "Falla en monitor principal",
        "descripcion": "La pantalla no enciende tras corte de luz",
        "correo": f"soporte_{uid}@coopya.com",
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
    assert ticket["columna"] == 1
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
        "prioridad": "critica",
        "columna": 3
    }
    patch_res = client.patch(f"/api/v1/tickets/{ticket_id}", json=patch_payload)
    assert patch_res.status_code == 200
    updated_ticket = patch_res.json()
    assert updated_ticket["estado"] == "en_progreso"
    assert updated_ticket["prioridad"] == "critica"
    assert updated_ticket["columna"] == 3

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

    # 3. Filtrar por fecha parcial simple (solo día YYYY-MM-DD sin hora)
    from datetime import datetime, timezone
    ahora = datetime.now(timezone.utc)
    hoy_str = ahora.strftime("%Y-%m-%d")
    res_fecha_simple = client.get("/api/v1/tickets/", params={"fecha_desde": hoy_str, "fecha_hasta": hoy_str})
    assert res_fecha_simple.status_code == 200, f"Error en filtro de fecha simple: {res_fecha_simple.text}"
    assert len(res_fecha_simple.json()) >= 2

    # 5. Filtrar pasando solo fecha_hasta con hora (debe autocompletar hasta las 23:59:59 y encontrar los tickets)
    hoy_iso_hora = ahora.strftime("%Y-%m-%dT%H:%M")
    res_solo_hasta = client.get("/api/v1/tickets/", params={"fecha_hasta": hoy_iso_hora})
    assert res_solo_hasta.status_code == 200
    assert len(res_solo_hasta.json()) >= 2

    # 6. Filtrar por columna
    uid_col = uuid.uuid4().hex[:6]
    client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Columna 2",
        "descripcion": "Probando filtro columna",
        "correo": f"col2_{uid_col}@coopya.com",
        "columna": 2
    })
    res_col = client.get("/api/v1/tickets/?columna=2")
    assert res_col.status_code == 200
    tickets_col2 = res_col.json()
    assert len(tickets_col2) >= 1
    assert all(t["columna"] == 2 for t in tickets_col2)

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
    assert len(asignables) == 3
    assert any(a["value"] == "facundo_bernard" and a["label"] == "Facundo Bernard" for a in asignables)

def test_invalid_file_upload_rejected(client):
    uid = uuid.uuid4().hex[:6]
    # Intentar crear un ticket adjuntando un binario/ejecutable no soportado (.exe)
    form_data = {
        "titulo": "Ticket con archivo inválido",
        "descripcion": "Intentando subir un binario ejecutable",
        "correo": f"seguridad_{uid}@coopya.com"
    }
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00Fake Executable Binary"
    files = [
        ("files", ("malware.exe", io.BytesIO(fake_exe), "application/x-msdownload"))
    ]
    res = client.post("/api/v1/tickets/", data=form_data, files=files)
    assert res.status_code == 400
    assert "no tiene un formato permitido" in res.json()["message"]

def test_allowed_document_types_upload(client):
    uid = uuid.uuid4().hex[:6]
    form_data = {
        "titulo": "Ticket con adjuntos PDF, CSV, XLSX y TXT",
        "descripcion": "Adjuntando reportes y archivos de texto",
        "correo": f"doc_upload_{uid}@coopya.com"
    }
    fake_pdf = b"%PDF-1.4 Fake PDF Content"
    fake_csv = b"id,nombre,valor\n1,Prueba,100\n"
    fake_xlsx = b"PK\x03\x04Fake Excel Binary Content"
    fake_txt = b"Texto plano de diagnostico de sistema\n"

    files = [
        ("files", ("reporte.pdf", io.BytesIO(fake_pdf), "application/pdf")),
        ("files", ("datos.csv", io.BytesIO(fake_csv), "text/csv")),
        ("files", ("planilla.xlsx", io.BytesIO(fake_xlsx), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ("files", ("notas.txt", io.BytesIO(fake_txt), "text/plain"))
    ]
    res = client.post("/api/v1/tickets/", data=form_data, files=files)
    assert res.status_code == 201, f"Error: {res.text}"
    ticket = res.json()
    assert len(ticket["imagenes"]) == 4

    # Verificar que cada archivo se puede consultar y tiene su Content-Type adecuado
    for file_url in ticket["imagenes"]:
        file_res = client.get(file_url)
        assert file_res.status_code == 200
        assert "Content-Disposition" in file_res.headers

def test_atomic_sequence_no_collision_on_delete(client):
    uid = uuid.uuid4().hex[:6]
    # 1. Crear ticket A
    res_a = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Secuencia A",
        "descripcion": "Probando secuencia única",
        "correo": f"seq_a_{uid}@coopya.com"
    })
    assert res_a.status_code == 201
    ticket_a = res_a.json()
    num_a = int(ticket_a["identificador"].split("-")[1])

    # 2. Crear ticket B
    res_b = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Secuencia B",
        "descripcion": "Probando secuencia única",
        "correo": f"seq_b_{uid}@coopya.com"
    })
    assert res_b.status_code == 201
    ticket_b = res_b.json()
    num_b = int(ticket_b["identificador"].split("-")[1])
    assert num_b > num_a

    # 3. Eliminar ticket A
    del_res = client.delete(f"/api/v1/tickets/{ticket_a['id']}")
    assert del_res.status_code == 204

    # 4. Crear ticket C (debe avanzar a num_b + 1 y NUNCA retroceder o colisionar con num_a)
    res_c = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Secuencia C",
        "descripcion": "Probando secuencia única post delete",
        "correo": f"seq_c_{uid}@coopya.com"
    })
    assert res_c.status_code == 201
    ticket_c = res_c.json()
    num_c = int(ticket_c["identificador"].split("-")[1])
    assert num_c > num_b

def test_rate_limit_and_cooldown(client):
    uid = uuid.uuid4().hex[:6]
    email = f"antispam_{uid}@coopya.com"

    # 1. Primer ticket debe crearse con éxito
    res1 = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Anti-Spam 1",
        "descripcion": "Primer ticket del usuario",
        "correo": email
    })
    assert res1.status_code == 201

    # 2. Segundo ticket inmediato debe ser bloqueado por Cooldown (60 seg)
    res2 = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Anti-Spam 2 Inmediato",
        "descripcion": "Segundo ticket intentado al instante",
        "correo": email
    })
    assert res2.status_code == 400
    assert "espera" in res2.json()["message"].lower() or "anti-spam" in res2.json()["message"].lower()

def test_admin_whitelist_bypasses_rate_limit(client):
    from src.config.settings import settings
    admin_email = "admin_unlimited@coopya.com"
    if admin_email not in settings.ADMIN_EMAILS:
        settings.ADMIN_EMAILS.append(admin_email)

    try:
        # El admin debe poder crear múltiples tickets de forma consecutiva e inmediata sin cooldown
        res1 = client.post("/api/v1/tickets/", data={
            "titulo": "Ticket Admin 1",
            "descripcion": "Primer ticket de admin",
            "correo": admin_email
        })
        assert res1.status_code == 201

        res2 = client.post("/api/v1/tickets/", data={
            "titulo": "Ticket Admin 2 Inmediato",
            "descripcion": "Segundo ticket inmediato sin esperar cooldown",
            "correo": admin_email
        })
        assert res2.status_code == 201
        assert res2.json()["identificador"] != res1.json()["identificador"]
    finally:
        if admin_email in settings.ADMIN_EMAILS:
            settings.ADMIN_EMAILS.remove(admin_email)

def test_frecuencia_support(client):
    uid = uuid.uuid4().hex[:6]
    # 1. Crear ticket con frecuencia válida
    frecuencia_json = '{"numero": 2, "periodo": "Meses"}'
    res = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Recurrente",
        "descripcion": "Mantenimiento bimestral",
        "correo": f"frec_{uid}@coopya.com",
        "frecuencia": frecuencia_json
    })
    assert res.status_code == 201
    ticket = res.json()
    assert ticket["frecuencia"] is not None
    assert ticket["frecuencia"]["numero"] == 2
    assert ticket["frecuencia"]["periodo"] == "Meses"

    # 2. Rechazar período inválido
    uid_inv = uuid.uuid4().hex[:6]
    frecuencia_invalida = '{"numero": 1, "periodo": "Horas"}'
    res_inv = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket Inválido",
        "descripcion": "Mantenimiento horario no soportado",
        "correo": f"inv_{uid_inv}@coopya.com",
        "frecuencia": frecuencia_invalida
    })
    assert res_inv.status_code == 400
    assert "frecuencia" in res_inv.json()["message"].lower()

def test_ticket_read_status(client):
    uid = uuid.uuid4().hex[:6]
    # 1. Ticket recién creado tiene leido=False
    res = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket No Leído",
        "descripcion": "Verificar flag leido",
        "correo": f"read_{uid}@coopya.com"
    })
    assert res.status_code == 201
    ticket = res.json()
    assert ticket["leido"] is False
    ticket_id = ticket["id"]

    # 2. Marcar como leído vía PATCH /{id}/read
    read_res = client.patch(f"/api/v1/tickets/{ticket_id}/read")
    assert read_res.status_code == 200
    assert read_res.json()["leido"] is True

    # 3. Verificar que al consultar por GET permanezca leído
    get_res = client.get(f"/api/v1/tickets/{ticket_id}")
    assert get_res.status_code == 200
    assert get_res.json()["leido"] is True

def test_sse_broadcast_on_ticket_creation(client):
    import asyncio
    from src.core.sse_manager import sse_manager

    loop = asyncio.get_event_loop() if not asyncio.get_event_loop().is_closed() else asyncio.new_event_loop()
    queue = loop.run_until_complete(sse_manager.subscribe())

    uid = uuid.uuid4().hex[:6]
    try:
        res = client.post("/api/v1/tickets/", data={
            "titulo": "Ticket para SSE",
            "descripcion": "Probando transmisión SSE",
            "correo": f"sse_{uid}@coopya.com"
        })
        assert res.status_code == 201
        ticket = res.json()

        assert not queue.empty()
        event = queue.get_nowait()
        assert event["event"] == "nuevo_ticket"
        assert event["data"]["identificador"] == ticket["identificador"]
    finally:
        sse_manager.unsubscribe(queue)

def test_ticket_lock_manager_logic():
    from src.core.ticket_lock_manager import TicketLockManager
    import time
    from datetime import timedelta

    manager = TicketLockManager(ttl_seconds=1)
    
    # 1. Adquirir lock exitosamente
    success, lock = manager.acquire_lock("tck-1", "operador_a")
    assert success is True
    assert lock.usuario == "operador_a"
    assert manager.is_locked("tck-1") is not None

    # 2. Otro operador intenta adquirirlo -> Rechazado
    success_b, lock_b = manager.acquire_lock("tck-1", "operador_b")
    assert success_b is False
    assert lock_b.usuario == "operador_a"

    # 3. Mismo operador renueva lock
    success_a2, lock_a2 = manager.acquire_lock("tck-1", "operador_a")
    assert success_a2 is True

    # 4. Liberar lock
    released = manager.release_lock("tck-1", "operador_a")
    assert released is True
    assert manager.is_locked("tck-1") is None

    # 5. Adquirir después de liberar
    success_b2, lock_b2 = manager.acquire_lock("tck-1", "operador_b")
    assert success_b2 is True
    assert lock_b2.usuario == "operador_b"

    # 6. TTL expiración
    manager.release_lock("tck-1")
    manager.acquire_lock("tck-exp", "operador_x")
    time.sleep(1.1)
    assert manager.is_locked("tck-exp") is None

    # 7. Obtener bloqueos activos (get_active_locks)
    manager.acquire_lock('tck-live', 'operador_live')
    active = manager.get_active_locks()
    assert 'tck-live' in active
    assert active['tck-live'].usuario == 'operador_live'
    time.sleep(1.1)
    assert len(manager.get_active_locks()) == 0

def test_concurrency_lock_endpoints(client):
    from src.core.ticket_lock_manager import ticket_lock_manager
    ticket_lock_manager.clear()

    # 1. Crear un ticket
    uid = uuid.uuid4().hex[:6]
    res = client.post("/api/v1/tickets/", data={
        "titulo": "Ticket para Test de Bloqueo",
        "descripcion": "Probando endpoints de bloqueo",
        "correo": f"lock_{uid}@coopya.com"
    })
    assert res.status_code == 201
    ticket_id = res.json()["id"]

    # 2. Consultar estado inicial -> no bloqueado
    status_res = client.get(f"/api/v1/tickets/{ticket_id}/bloqueo")
    assert status_res.status_code == 200
    assert status_res.json()["bloqueado"] is False

    # 3. Operador A bloquea el ticket -> 200 OK
    lock_res_a = client.post(f"/api/v1/tickets/{ticket_id}/bloquear", json={"usuario": "facundo@coopya.com"})
    assert lock_res_a.status_code == 200
    assert lock_res_a.json()["status"] == "bloqueado"
    assert lock_res_a.json()["usuario"] == "facundo@coopya.com"

    # 4. Consultar estado -> bloqueado por Operador A
    status_res2 = client.get(f"/api/v1/tickets/{ticket_id}/bloqueo")
    assert status_res2.status_code == 200
    assert status_res2.json()["bloqueado"] is True
    assert status_res2.json()["usuario"] == "facundo@coopya.com"

    # 5. Operador B intenta bloquearlo -> 409 Conflict
    lock_res_b = client.post(f"/api/v1/tickets/{ticket_id}/bloquear", json={"usuario": "nahuel@coopya.com"})
    assert lock_res_b.status_code == 409
    assert "Facundo" in lock_res_b.json()["detail"] or "facundo@coopya.com" in lock_res_b.json()["detail"]

    # 6. Operador A libera el bloqueo
    unlock_res = client.post(f"/api/v1/tickets/{ticket_id}/desbloquear", json={"usuario": "facundo@coopya.com"})
    assert unlock_res.status_code == 200
    assert unlock_res.json()["status"] == "desbloqueado"

    # 7. Ahora Operador B puede bloquearlo
    lock_res_b2 = client.post(f"/api/v1/tickets/{ticket_id}/bloquear", json={"usuario": "nahuel@coopya.com"})
    assert lock_res_b2.status_code == 200
    assert lock_res_b2.json()["usuario"] == "nahuel@coopya.com"

    # 8. Al actualizar el ticket vía PATCH, se libera automáticamente
    patch_res = client.patch(f"/api/v1/tickets/{ticket_id}", json={"prioridad": "alta"})
    assert patch_res.status_code == 200
    status_res3 = client.get(f"/api/v1/tickets/{ticket_id}/bloqueo")
    assert status_res3.json()["bloqueado"] is False

    # 9. Si el ticket está bloqueado, intentar eliminarlo debe retornar 409 Conflict
    client.post(f"/api/v1/tickets/{ticket_id}/bloquear", json={"usuario": "nahuel@coopya.com"})
    del_res_conflict = client.delete(f"/api/v1/tickets/{ticket_id}")
    assert del_res_conflict.status_code == 409
    assert "nahuel@coopya.com" in del_res_conflict.json()["detail"]

    # 10. Una vez desbloqueado, se puede eliminar normalmente
    client.post(f"/api/v1/tickets/{ticket_id}/desbloquear", json={"usuario": "nahuel@coopya.com"})
    del_res_ok = client.delete(f"/api/v1/tickets/{ticket_id}")
    assert del_res_ok.status_code == 204

def test_sse_events_on_update_delete_and_lock(client):
    import asyncio
    from src.core.sse_manager import sse_manager
    from src.core.ticket_lock_manager import ticket_lock_manager
    ticket_lock_manager.clear()

    loop = asyncio.get_event_loop() if not asyncio.get_event_loop().is_closed() else asyncio.new_event_loop()
    queue = loop.run_until_complete(sse_manager.subscribe())

    uid = uuid.uuid4().hex[:6]
    try:
        # 1. Crear ticket -> evento nuevo_ticket
        res = client.post("/api/v1/tickets/", data={
            "titulo": "Ticket eventos SSE",
            "descripcion": "Verificar todos los eventos emitidos",
            "correo": f"events_{uid}@coopya.com"
        })
        assert res.status_code == 201
        ticket = res.json()
        ticket_id = ticket["id"]

        ev_nuevo = queue.get_nowait()
        assert ev_nuevo["event"] == "nuevo_ticket"

        # 2. Bloquear ticket -> evento ticket_bloqueado
        client.post(f"/api/v1/tickets/{ticket_id}/bloquear", json={"usuario": "admin@coopya.com"})
        ev_lock = queue.get_nowait()
        assert ev_lock["event"] == "ticket_bloqueado"
        assert ev_lock["data"]["ticket_id"] == ticket_id
        assert ev_lock["data"]["usuario"] == "admin@coopya.com"

        # 3. Desbloquear ticket -> evento ticket_desbloqueado
        client.post(f"/api/v1/tickets/{ticket_id}/desbloquear", json={"usuario": "admin@coopya.com"})
        ev_unlock = queue.get_nowait()
        assert ev_unlock["event"] == "ticket_desbloqueado"
        assert ev_unlock["data"]["ticket_id"] == ticket_id

        # 4. Actualizar ticket vía PATCH -> eventos ticket_actualizado y ticket_desbloqueado
        client.patch(f"/api/v1/tickets/{ticket_id}", json={"titulo": "Título Modificado"})
        ev_upd = queue.get_nowait()
        assert ev_upd["event"] == "ticket_actualizado"
        assert ev_upd["data"]["titulo"] == "Título Modificado"

        ev_unl2 = queue.get_nowait()
        assert ev_unl2["event"] == "ticket_desbloqueado"

        # 5. Marcar como leído -> evento ticket_actualizado
        client.patch(f"/api/v1/tickets/{ticket_id}/read")
        ev_read = queue.get_nowait()
        assert ev_read["event"] == "ticket_actualizado"
        assert ev_read["data"]["leido"] is True

        # 6. Eliminar ticket -> evento ticket_eliminado
        client.delete(f"/api/v1/tickets/{ticket_id}")
        ev_del = queue.get_nowait()
        assert ev_del["event"] == "ticket_eliminado"
        assert ev_del["data"]["id"] == ticket_id
        assert ev_del["data"]["identificador"] == ticket["identificador"]
    finally:
        sse_manager.unsubscribe(queue)

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
        test_atomic_sequence_no_collision_on_delete(test_client)
        print(" [OK] test_atomic_sequence_no_collision_on_delete")
        test_rate_limit_and_cooldown(test_client)
        print(" [OK] test_rate_limit_and_cooldown")
    print("\n Todas las pruebas pasaron exitosamente!")
