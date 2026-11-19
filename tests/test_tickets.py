import asyncio
import io
import time
import uuid

import pytest
from starlette.testclient import TestClient

from src.config.settings import settings
from src.core.sse_manager import sse_manager
from src.core.ticket_lock_manager import TicketLockManager, ticket_lock_manager
from src.main import app
from src.models.ticket_model import normalize_asignados
from tests.conftest import login_admin_headers


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "message": "Service is running"}


def test_ticket_crud_and_gridfs_flow(client):
    headers = login_admin_headers(client)
    uid = uuid.uuid4().hex[:6]

    # 1. Crear ticket con formulario y fotos adjuntas (POST público)
    form_data = {
        "titulo": "Falla en monitor principal",
        "descripcion": "La pantalla no enciende tras corte de luz",
        "correo": f"soporte_{uid}@coopya.com",
        "prioridad": "alta",
        "asignar": "Tecnico Redes",
    }
    fake_img1 = b"\x89PNG_IMAGE_1_DATA"
    fake_img2 = b"\x89PNG_IMAGE_2_DATA"
    files = [
        ("files", ("captura_1.png", io.BytesIO(fake_img1), "image/png")),
        ("files", ("captura_2.png", io.BytesIO(fake_img2), "image/png")),
    ]
    create_res = client.post("/api/v1/tickets/", data=form_data, files=files)
    assert create_res.status_code == 201, f"Error al crear: {create_res.text}"
    ticket = create_res.json()

    assert ticket["titulo"] == form_data["titulo"]
    assert ticket["correo"] == form_data["correo"]
    assert ticket["prioridad"] == "alta"
    assert ticket["estado"] == "abierto"
    assert ticket["asignar"] == ["Tecnico Redes"]
    assert ticket["identificador"].startswith("TCK-")
    assert ticket["fecha_edicion"] is None
    assert ticket["columna"] == 1
    assert len(ticket["imagenes"]) == 2

    ticket_id = ticket["id"]
    image_url_1, image_url_2 = ticket["imagenes"]
    assert image_url_1.startswith("/api/v1/files/")
    assert image_url_2.startswith("/api/v1/files/")

    # Sin auth, GET /tickets/{id} debe rechazar con 401
    assert client.get(f"/api/v1/tickets/{ticket_id}").status_code == 401

    # 2. Obtener ticket por ID autenticado
    get_res = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["identificador"] == ticket["identificador"]

    # 3. Subir una imagen extra posterior
    fake_img3 = b"\x89PNG_IMAGE_3_DATA"
    img_res = client.post(
        f"/api/v1/tickets/{ticket_id}/images",
        files=[("files", ("captura_3.png", io.BytesIO(fake_img3), "image/png"))],
        headers=headers,
    )
    assert img_res.status_code == 200, f"Error al subir imagen extra: {img_res.text}"
    ticket_con_imagenes = img_res.json()
    assert len(ticket_con_imagenes["imagenes"]) == 3
    assert ticket_con_imagenes["fecha_edicion"] is not None

    # 4. Descargar imágenes desde GridFS
    file_res1 = client.get(image_url_1, headers=headers)
    assert file_res1.status_code == 200
    assert file_res1.content == fake_img1

    file_res2 = client.get(image_url_2, headers=headers)
    assert file_res2.status_code == 200
    assert file_res2.content == fake_img2

    # 5. Eliminar imagen específica
    file_id_to_delete = image_url_1.split("/")[-1]
    del_img_res = client.delete(
        f"/api/v1/tickets/{ticket_id}/images/{file_id_to_delete}",
        headers=headers,
    )
    assert del_img_res.status_code == 200
    assert len(del_img_res.json()["imagenes"]) == 2
    assert image_url_1 not in del_img_res.json()["imagenes"]
    assert client.get(image_url_1, headers=headers).status_code == 404

    # 6. Actualizar campos con PATCH
    patch_res = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"estado": "en_progreso", "prioridad": "critica", "columna": 3},
        headers=headers,
    )
    assert patch_res.status_code == 200
    updated_ticket = patch_res.json()
    assert updated_ticket["estado"] == "en_progreso"
    assert updated_ticket["prioridad"] == "critica"
    assert updated_ticket["columna"] == 3

    # 7. Eliminar ticket completo
    delete_res = client.delete(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert delete_res.status_code == 204

    not_found_res = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert not_found_res.status_code == 404
    assert not_found_res.json()["error"] == "Not Found"


def test_multiple_operators_and_legacy_normalization(client):
    assert normalize_asignados(None) == []
    assert normalize_asignados("") == []
    assert normalize_asignados("Facundo Bernard") == ["Facundo Bernard"]
    assert normalize_asignados(["Nahuel Monti", "nahuel monti", "Facundo Bernard"]) == [
        "Nahuel Monti",
        "Facundo Bernard",
    ]

    headers = login_admin_headers(client)
    uid = uuid.uuid4().hex[:6]

    res = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": f"Ticket Multi Operador {uid}",
            "descripcion": "Asignado a varios operadores",
            "correo": f"multi_{uid}@coopya.com",
            "prioridad": "alta",
            "asignar": ["Facundo Bernard", "Nahuel Monti"],
        },
    )
    assert res.status_code == 201, res.text
    created = res.json()
    assert created["asignar"] == ["Facundo Bernard", "Nahuel Monti"]
    ticket_id = created["id"]

    # Agregar tercer operador con PATCH
    patch_res = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"asignar": ["Facundo Bernard", "Nahuel Monti", "Nicolas Fernandez"]},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["asignar"] == ["Facundo Bernard", "Nahuel Monti", "Nicolas Fernandez"]

    # Filtrar por segundo operador
    filter_res = client.get("/api/v1/tickets/?asignar=Nahuel", headers=headers)
    assert filter_res.status_code == 200
    assert any(t["id"] == ticket_id for t in filter_res.json()["items"])

    # Limpiar operadores
    clear_res = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"asignar": []},
        headers=headers,
    )
    assert clear_res.status_code == 200
    assert clear_res.json()["asignar"] == []


def test_ticket_filters(client):
    headers = login_admin_headers(client)
    uid = uuid.uuid4().hex[:6]

    res1 = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Filtro 1",
            "descripcion": "Problema con impresora",
            "correo": f"user1_{uid}@coopya.com",
            "prioridad": "baja",
            "asignar": "Carlos Tecnico",
        },
    )
    assert res1.status_code == 201
    res2 = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Filtro 2",
            "descripcion": "Problema con servidor",
            "correo": f"user2_{uid}@coopya.com",
            "prioridad": "alta",
            "asignar": "Maria Redes",
        },
    )
    assert res2.status_code == 201

    # 1. Filtrar por estado 'abierto'
    res_estado = client.get("/api/v1/tickets/?estado=abierto", headers=headers)
    assert res_estado.status_code == 200
    tickets_abiertos = res_estado.json()["items"]
    assert all(t["estado"] == "abierto" for t in tickets_abiertos)

    # 2. Filtrar por asignado 'Carlos'
    res_asignado = client.get("/api/v1/tickets/?asignar=Carlos", headers=headers)
    assert res_asignado.status_code == 200
    tickets_carlos = res_asignado.json()["items"]
    assert len(tickets_carlos) >= 1
    assert any(any("Carlos" in op for op in t["asignar"]) for t in tickets_carlos)

    # 3. Filtrar por fecha parcial simple
    from datetime import datetime, timezone

    ahora = datetime.now(timezone.utc)
    hoy_str = ahora.strftime("%Y-%m-%d")
    res_fecha_simple = client.get(
        "/api/v1/tickets/",
        params={"fecha_desde": hoy_str, "fecha_hasta": hoy_str},
        headers=headers,
    )
    assert res_fecha_simple.status_code == 200, res_fecha_simple.text
    assert len(res_fecha_simple.json()["items"]) >= 2

    # 4. Filtrar solo fecha_hasta con hora
    hoy_iso_hora = ahora.strftime("%Y-%m-%dT%H:%M")
    res_solo_hasta = client.get(
        "/api/v1/tickets/",
        params={"fecha_hasta": hoy_iso_hora},
        headers=headers,
    )
    assert res_solo_hasta.status_code == 200
    assert len(res_solo_hasta.json()["items"]) >= 2

    # 5. Filtrar por columna
    res_col_create = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Columna 2",
            "descripcion": "Probando filtro columna",
            "correo": f"col2_{uid}@coopya.com",
            "columna": 2,
        },
    )
    assert res_col_create.status_code == 201
    res_col = client.get("/api/v1/tickets/?columna=2", headers=headers)
    assert res_col.status_code == 200
    tickets_col2 = res_col.json()["items"]
    assert len(tickets_col2) >= 1
    assert all(t["columna"] == 2 for t in tickets_col2)

    # 6. Búsqueda libre (q)
    res_q = client.get("/api/v1/tickets/?q=impresora", headers=headers)
    assert res_q.status_code == 200
    items_q = res_q.json()["items"]
    assert len(items_q) >= 1
    assert any("impresora" in t["descripcion"].lower() for t in items_q)


def test_catalog_endpoints(client):
    res_estados = client.get("/api/v1/catalogs/estados")
    assert res_estados.status_code == 200
    estados = res_estados.json()
    assert len(estados) == 4
    assert any(e["value"] == "abierto" for e in estados)

    res_prioridades = client.get("/api/v1/catalogs/prioridades")
    assert res_prioridades.status_code == 200
    prioridades = res_prioridades.json()
    assert len(prioridades) == 4
    assert any(p["value"] == "alta" for p in prioridades)

    res_asignables = client.get("/api/v1/catalogs/asignables")
    assert res_asignables.status_code == 200
    asignables = res_asignables.json()
    assert len(asignables) >= 3
    assert any(a["value"] == "facundo_bernard" and a["label"] == "Facundo Bernard" for a in asignables)


def test_invalid_file_upload_rejected(client):
    uid = uuid.uuid4().hex[:6]
    form_data = {
        "titulo": "Ticket con archivo inválido",
        "descripcion": "Intentando subir un binario ejecutable",
        "correo": f"seguridad_{uid}@coopya.com",
    }
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00Fake Executable Binary"
    res = client.post(
        "/api/v1/tickets/",
        data=form_data,
        files=[("files", ("malware.exe", io.BytesIO(fake_exe), "application/x-msdownload"))],
    )
    assert res.status_code == 400
    assert "formato seguro o permitido" in res.json()["message"]


def test_allowed_document_types_upload(client):
    headers = login_admin_headers(client)
    uid = uuid.uuid4().hex[:6]
    form_data = {
        "titulo": "Ticket con adjuntos PDF, CSV, XLSX y TXT",
        "descripcion": "Adjuntando reportes y archivos de texto",
        "correo": f"doc_upload_{uid}@coopya.com",
    }
    files = [
        ("files", ("reporte.pdf", io.BytesIO(b"%PDF-1.4 Fake PDF Content"), "application/pdf")),
        ("files", ("datos.csv", io.BytesIO(b"id,nombre,valor\n1,Prueba,100\n"), "text/csv")),
        (
            "files",
            (
                "planilla.xlsx",
                io.BytesIO(b"PK\x03\x04Fake Excel Binary Content"),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        ),
        ("files", ("notas.txt", io.BytesIO(b"Texto plano de diagnostico de sistema\n"), "text/plain")),
    ]
    res = client.post("/api/v1/tickets/", data=form_data, files=files)
    assert res.status_code == 201, res.text
    ticket = res.json()
    assert len(ticket["imagenes"]) == 4

    for file_url in ticket["imagenes"]:
        file_res = client.get(file_url, headers=headers)
        assert file_res.status_code == 200
        assert "Content-Disposition" in file_res.headers


def test_atomic_sequence_no_collision_on_delete(client):
    headers = login_admin_headers(client)
    uid = uuid.uuid4().hex[:6]

    res_a = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Secuencia A",
            "descripcion": "Probando secuencia única",
            "correo": f"seq_a_{uid}@coopya.com",
        },
    )
    assert res_a.status_code == 201
    ticket_a = res_a.json()
    num_a = int(ticket_a["identificador"].split("-")[1])

    res_b = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Secuencia B",
            "descripcion": "Probando secuencia única",
            "correo": f"seq_b_{uid}@coopya.com",
        },
    )
    assert res_b.status_code == 201
    num_b = int(res_b.json()["identificador"].split("-")[1])
    assert num_b > num_a

    del_res = client.delete(f"/api/v1/tickets/{ticket_a['id']}", headers=headers)
    assert del_res.status_code == 204

    res_c = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Secuencia C",
            "descripcion": "Probando secuencia única post delete",
            "correo": f"seq_c_{uid}@coopya.com",
        },
    )
    assert res_c.status_code == 201
    num_c = int(res_c.json()["identificador"].split("-")[1])
    assert num_c > num_b


def test_rate_limit_and_cooldown(client):
    uid = uuid.uuid4().hex[:6]
    email = f"antispam_{uid}@coopya.com"

    res1 = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Anti-Spam 1",
            "descripcion": "Primer ticket del usuario",
            "correo": email,
        },
    )
    assert res1.status_code == 201

    res2 = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Anti-Spam 2 Inmediato",
            "descripcion": "Segundo ticket intentado al instante",
            "correo": email,
        },
    )
    assert res2.status_code == 400
    assert "espera" in res2.json()["message"].lower() or "anti-spam" in res2.json()["message"].lower()


def test_admin_whitelist_bypasses_rate_limit(client):
    admin_email = "admin_unlimited@coopya.com"
    if admin_email not in settings.ADMIN_EMAILS:
        settings.ADMIN_EMAILS.append(admin_email)

    try:
        res1 = client.post(
            "/api/v1/tickets/",
            data={
                "titulo": "Ticket Admin 1",
                "descripcion": "Primer ticket de admin",
                "correo": admin_email,
            },
        )
        assert res1.status_code == 201

        res2 = client.post(
            "/api/v1/tickets/",
            data={
                "titulo": "Ticket Admin 2 Inmediato",
                "descripcion": "Segundo ticket inmediato sin esperar cooldown",
                "correo": admin_email,
            },
        )
        assert res2.status_code == 201
        assert res2.json()["identificador"] != res1.json()["identificador"]
    finally:
        if admin_email in settings.ADMIN_EMAILS:
            settings.ADMIN_EMAILS.remove(admin_email)


def test_frecuencia_support(client):
    uid = uuid.uuid4().hex[:6]
    res = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Recurrente",
            "descripcion": "Mantenimiento bimestral",
            "correo": f"frec_{uid}@coopya.com",
            "frecuencia": '{"numero": 2, "periodo": "Meses"}',
        },
    )
    assert res.status_code == 201
    ticket = res.json()
    assert ticket["frecuencia"] is not None
    assert ticket["frecuencia"]["numero"] == 2
    assert ticket["frecuencia"]["periodo"] == "Meses"

    uid_inv = uuid.uuid4().hex[:6]
    res_inv = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket Inválido",
            "descripcion": "Mantenimiento horario no soportado",
            "correo": f"inv_{uid_inv}@coopya.com",
            "frecuencia": '{"numero": 1, "periodo": "Horas"}',
        },
    )
    assert res_inv.status_code == 400
    assert "frecuencia" in res_inv.json()["message"].lower()


def test_ticket_read_status(client):
    headers = login_admin_headers(client)
    uid = uuid.uuid4().hex[:6]

    res = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket No Leído",
            "descripcion": "Verificar flag leido",
            "correo": f"read_{uid}@coopya.com",
        },
    )
    assert res.status_code == 201
    ticket = res.json()
    assert ticket["leido"] is False
    ticket_id = ticket["id"]

    read_res = client.patch(f"/api/v1/tickets/{ticket_id}/read", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["leido"] is True

    get_res = client.get(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["leido"] is True


def test_sse_broadcast_on_ticket_creation(client):
    loop = asyncio.get_event_loop() if not asyncio.get_event_loop().is_closed() else asyncio.new_event_loop()
    queue = loop.run_until_complete(sse_manager.subscribe())

    uid = uuid.uuid4().hex[:6]
    try:
        res = client.post(
            "/api/v1/tickets/",
            data={
                "titulo": "Ticket para SSE",
                "descripcion": "Probando transmisión SSE",
                "correo": f"sse_{uid}@coopya.com",
            },
        )
        assert res.status_code == 201
        ticket = res.json()

        assert not queue.empty()
        event = queue.get_nowait()
        assert event["event"] == "nuevo_ticket"
        assert event["data"]["identificador"] == ticket["identificador"]
    finally:
        sse_manager.unsubscribe(queue)


def test_ticket_lock_manager_logic():
    manager = TicketLockManager(ttl_seconds=1)

    success, lock = manager.acquire_lock("tck-1", "operador_a")
    assert success is True
    assert lock.usuario == "operador_a"
    assert manager.is_locked("tck-1") is not None

    success_b, lock_b = manager.acquire_lock("tck-1", "operador_b")
    assert success_b is False
    assert lock_b.usuario == "operador_a"

    success_a2, _ = manager.acquire_lock("tck-1", "operador_a")
    assert success_a2 is True

    released = manager.release_lock("tck-1", "operador_a")
    assert released is True
    assert manager.is_locked("tck-1") is None

    success_b2, lock_b2 = manager.acquire_lock("tck-1", "operador_b")
    assert success_b2 is True
    assert lock_b2.usuario == "operador_b"

    manager.release_lock("tck-1")
    manager.acquire_lock("tck-exp", "operador_x")
    time.sleep(1.1)
    assert manager.is_locked("tck-exp") is None

    manager.acquire_lock("tck-live", "operador_live")
    active = manager.get_active_locks()
    assert "tck-live" in active
    assert active["tck-live"].usuario == "operador_live"
    time.sleep(1.1)
    assert len(manager.get_active_locks()) == 0


def test_concurrency_lock_endpoints(client):
    headers = login_admin_headers(client)
    ticket_lock_manager.clear()

    uid = uuid.uuid4().hex[:6]
    res = client.post(
        "/api/v1/tickets/",
        data={
            "titulo": "Ticket para Test de Bloqueo",
            "descripcion": "Probando endpoints de bloqueo",
            "correo": f"lock_{uid}@coopya.com",
        },
    )
    assert res.status_code == 201
    ticket_id = res.json()["id"]

    status_res = client.get(f"/api/v1/tickets/{ticket_id}/bloqueo", headers=headers)
    assert status_res.status_code == 200
    assert status_res.json()["bloqueado"] is False

    lock_res_a = client.post(
        f"/api/v1/tickets/{ticket_id}/bloquear",
        json={"usuario": "facundo@coopya.com"},
        headers=headers,
    )
    assert lock_res_a.status_code == 200
    assert lock_res_a.json()["status"] == "bloqueado"

    status_res2 = client.get(f"/api/v1/tickets/{ticket_id}/bloqueo", headers=headers)
    assert status_res2.status_code == 200
    assert status_res2.json()["bloqueado"] is True
    assert status_res2.json()["usuario"] == "facundo@coopya.com"

    lock_res_b = client.post(
        f"/api/v1/tickets/{ticket_id}/bloquear",
        json={"usuario": "nahuel@coopya.com"},
        headers=headers,
    )
    assert lock_res_b.status_code == 409
    assert "facundo@coopya.com" in lock_res_b.json()["detail"].lower()

    unlock_res = client.post(
        f"/api/v1/tickets/{ticket_id}/desbloquear",
        json={"usuario": "facundo@coopya.com"},
        headers=headers,
    )
    assert unlock_res.status_code == 200

    lock_res_b2 = client.post(
        f"/api/v1/tickets/{ticket_id}/bloquear",
        json={"usuario": "nahuel@coopya.com"},
        headers=headers,
    )
    assert lock_res_b2.status_code == 200

    patch_res = client.patch(
        f"/api/v1/tickets/{ticket_id}",
        json={"prioridad": "alta"},
        headers=headers,
    )
    assert patch_res.status_code == 200
    assert client.get(f"/api/v1/tickets/{ticket_id}/bloqueo", headers=headers).json()["bloqueado"] is False

    client.post(
        f"/api/v1/tickets/{ticket_id}/bloquear",
        json={"usuario": "nahuel@coopya.com"},
        headers=headers,
    )
    del_res_conflict = client.delete(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert del_res_conflict.status_code == 409

    client.post(
        f"/api/v1/tickets/{ticket_id}/desbloquear",
        json={"usuario": "nahuel@coopya.com"},
        headers=headers,
    )
    del_res_ok = client.delete(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert del_res_ok.status_code == 204


def test_sse_events_on_update_delete_and_lock(client):
    headers = login_admin_headers(client)
    ticket_lock_manager.clear()

    loop = asyncio.get_event_loop() if not asyncio.get_event_loop().is_closed() else asyncio.new_event_loop()
    queue = loop.run_until_complete(sse_manager.subscribe())

    uid = uuid.uuid4().hex[:6]
    try:
        res = client.post(
            "/api/v1/tickets/",
            data={
                "titulo": "Ticket eventos SSE",
                "descripcion": "Verificar todos los eventos emitidos",
                "correo": f"events_{uid}@coopya.com",
            },
        )
        assert res.status_code == 201
        ticket = res.json()
        ticket_id = ticket["id"]

        ev_nuevo = queue.get_nowait()
        assert ev_nuevo["event"] == "nuevo_ticket"

        client.post(
            f"/api/v1/tickets/{ticket_id}/bloquear",
            json={"usuario": settings.MASTER_ADMIN_EMAIL},
            headers=headers,
        )
        ev_lock = queue.get_nowait()
        assert ev_lock["event"] == "ticket_bloqueado"
        assert ev_lock["data"]["ticket_id"] == ticket_id

        client.post(
            f"/api/v1/tickets/{ticket_id}/desbloquear",
            json={"usuario": settings.MASTER_ADMIN_EMAIL},
            headers=headers,
        )
        ev_unlock = queue.get_nowait()
        assert ev_unlock["event"] == "ticket_desbloqueado"

        client.patch(
            f"/api/v1/tickets/{ticket_id}",
            json={"titulo": "Título Modificado"},
            headers=headers,
        )
        ev_upd = queue.get_nowait()
        assert ev_upd["event"] == "ticket_actualizado"
        assert ev_upd["data"]["titulo"] == "Título Modificado"

        ev_unl2 = queue.get_nowait()
        assert ev_unl2["event"] == "ticket_desbloqueado"

        client.patch(f"/api/v1/tickets/{ticket_id}/read", headers=headers)
        ev_read = queue.get_nowait()
        assert ev_read["event"] == "ticket_actualizado"
        assert ev_read["data"]["leido"] is True

        client.delete(f"/api/v1/tickets/{ticket_id}", headers=headers)
        ev_del = queue.get_nowait()
        assert ev_del["event"] == "ticket_eliminado"
        assert ev_del["data"]["id"] == ticket_id
    finally:
        sse_manager.unsubscribe(queue)


def test_sse_manager_replay_with_last_event_id():
    from src.core.sse_manager import SSEManager

    manager = SSEManager(history_limit=10)
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(manager.broadcast("nuevo_ticket", {"id": "1"}))
        loop.run_until_complete(manager.broadcast("ticket_actualizado", {"id": "1"}))
        loop.run_until_complete(manager.broadcast("ticket_eliminado", {"id": "1"}))

        # Simula reconexión enviando Last-Event-ID: 1 -> debe recibir eventos 2 y 3
        queue = loop.run_until_complete(manager.subscribe(last_event_id=1))
        ev2 = queue.get_nowait()
        ev3 = queue.get_nowait()
        assert ev2["id"] == 2 and ev2["event"] == "ticket_actualizado"
        assert ev3["id"] == 3 and ev3["event"] == "ticket_eliminado"
        assert queue.empty()
        manager.unsubscribe(queue)
    finally:
        loop.close()
