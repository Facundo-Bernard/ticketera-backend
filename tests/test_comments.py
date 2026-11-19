import asyncio
import uuid

import pytest
from starlette.testclient import TestClient

from src.config.settings import settings
from src.core.sse_manager import sse_manager
from src.main import app
from tests.conftest import login_admin_headers


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def _create_helper_ticket(client, correo_prefix="comment_test"):
    uid = uuid.uuid4().hex[:6]
    form_data = {
        "titulo": f"Ticket para prueba de comentarios {uid}",
        "descripcion": "Descripción del ticket de prueba",
        "correo": f"{correo_prefix}_{uid}@coopya.com",
        "prioridad": "media",
        "columna": 1,
    }
    res = client.post("/api/v1/tickets/", data=form_data)
    assert res.status_code == 201, f"Error al crear ticket auxiliar: {res.text}"
    return res.json()


def test_create_and_get_comments_flow(client, silence_push_notifications_in_tests):
    headers = login_admin_headers(client)
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]

    # Sin autenticación debe rechazar
    assert client.get(f"/api/v1/tickets/{ticket_id}/comments").status_code == 401

    # 1. El ticket recién creado debe tener 0 comentarios
    count_res = client.get(f"/api/v1/tickets/{ticket_id}/comments/count", headers=headers)
    assert count_res.status_code == 200
    assert count_res.json() == {"ticket_id": ticket_id, "total": 0}

    # 2. Agregar primer comentario (el servidor fuerza el autor al usuario autenticado)
    silence_push_notifications_in_tests.reset_mock()
    create_res_1 = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        json={"autor": "Autor Falsificado", "mensaje": "Se inició la revisión del caso técnico."},
        headers=headers,
    )
    assert create_res_1.status_code == 201
    c1 = create_res_1.json()
    assert c1["ticket_id"] == ticket_id
    assert c1["autor"] == settings.MASTER_ADMIN_EMAIL
    assert c1["mensaje"] == "Se inició la revisión del caso técnico."
    assert "fecha_creacion" in c1
    assert "id" in c1
    # Verifica que la notificación push de comentario se disparó sin AttributeError
    assert silence_push_notifications_in_tests.await_count >= 1

    # 3. Agregar segundo comentario
    create_res_2 = client.post(
        f"/api/v1/tickets/{ticket_id}/comments",
        json={"autor": "Otro", "mensaje": "Confirmado, el servidor ya responde adecuadamente."},
        headers=headers,
    )
    assert create_res_2.status_code == 201
    c2 = create_res_2.json()

    # 4. Verificar conteo actualizado
    count_res_2 = client.get(f"/api/v1/tickets/{ticket_id}/comments/count", headers=headers)
    assert count_res_2.status_code == 200
    assert count_res_2.json()["total"] == 2

    # 5. Listar comentarios y validar orden del más nuevo al más viejo
    list_res = client.get(f"/api/v1/tickets/{ticket_id}/comments", headers=headers)
    assert list_res.status_code == 200
    comments = list_res.json()
    assert len(comments) == 2
    assert comments[0]["id"] == c2["id"]
    assert comments[1]["id"] == c1["id"]

    # 6. Eliminar el primer comentario
    del_res = client.delete(f"/api/v1/tickets/{ticket_id}/comments/{c1['id']}", headers=headers)
    assert del_res.status_code == 204

    # 7. Verificar que el conteo disminuyó a 1
    count_res_3 = client.get(f"/api/v1/tickets/{ticket_id}/comments/count", headers=headers)
    assert count_res_3.json()["total"] == 1

    list_res_2 = client.get(f"/api/v1/tickets/{ticket_id}/comments", headers=headers)
    remaining_comments = list_res_2.json()
    assert len(remaining_comments) == 1
    assert remaining_comments[0]["id"] == c2["id"]

    # 8. Al eliminar el ticket, el bucket de comentarios también se purga en cascada
    del_ticket = client.delete(f"/api/v1/tickets/{ticket_id}", headers=headers)
    assert del_ticket.status_code == 204
    count_after_delete = client.get(f"/api/v1/tickets/{ticket_id}/comments/count", headers=headers)
    assert count_after_delete.status_code == 200
    assert count_after_delete.json()["total"] == 0


def test_comment_nonexistent_ticket(client):
    headers = login_admin_headers(client)
    fake_ticket_id = "507f1f77bcf86cd799439011"
    res = client.post(
        f"/api/v1/tickets/{fake_ticket_id}/comments",
        json={"autor": "Operador", "mensaje": "Mensaje en ticket inexistente"},
        headers=headers,
    )
    assert res.status_code == 404

    res_get = client.get(f"/api/v1/tickets/{fake_ticket_id}/comments", headers=headers)
    assert res_get.status_code == 404


def test_delete_nonexistent_comment(client):
    headers = login_admin_headers(client)
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]
    fake_comment_id = "507f1f77bcf86cd799439011"

    del_res = client.delete(f"/api/v1/tickets/{ticket_id}/comments/{fake_comment_id}", headers=headers)
    assert del_res.status_code == 404


def test_comment_sse_events(client):
    headers = login_admin_headers(client)
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    queue = loop.run_until_complete(sse_manager.subscribe())
    try:
        create_res = client.post(
            f"/api/v1/tickets/{ticket_id}/comments",
            json={"autor": "Operador SSE", "mensaje": "Verificación de evento en tiempo real"},
            headers=headers,
        )
        assert create_res.status_code == 201
        comment_obj = create_res.json()

        assert not queue.empty()
        msg = queue.get_nowait()
        assert msg["event"] == "nuevo_comentario"
        assert msg["data"]["ticket_id"] == ticket_id
        assert msg["data"]["comentario"]["id"] == comment_obj["id"]

        del_res = client.delete(f"/api/v1/tickets/{ticket_id}/comments/{comment_obj['id']}", headers=headers)
        assert del_res.status_code == 204

        assert not queue.empty()
        msg_del = queue.get_nowait()
        assert msg_del["event"] == "comentario_eliminado"
        assert msg_del["data"]["ticket_id"] == ticket_id
        assert msg_del["data"]["comment_id"] == comment_obj["id"]
    finally:
        sse_manager.unsubscribe(queue)


def test_comment_filters_pagination_and_regex_escape(client):
    headers = login_admin_headers(client)
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]

    for idx in range(1, 5):
        res = client.post(
            f"/api/v1/tickets/{ticket_id}/comments",
            json={"autor": "Ignored", "mensaje": f"Mensaje {idx}"},
            headers=headers,
        )
        assert res.status_code == 201

    # 1. Paginación limit=2, skip=0 (los 2 más nuevos: Mensaje 4 y Mensaje 3)
    page1 = client.get(f"/api/v1/tickets/{ticket_id}/comments?skip=0&limit=2", headers=headers)
    assert page1.status_code == 200
    assert len(page1.json()) == 2
    assert page1.json()[0]["mensaje"] == "Mensaje 4"
    assert page1.json()[1]["mensaje"] == "Mensaje 3"

    # 2. Paginación limit=2, skip=2 (Mensaje 2 y Mensaje 1)
    page2 = client.get(f"/api/v1/tickets/{ticket_id}/comments?skip=2&limit=2", headers=headers)
    assert page2.status_code == 200
    assert len(page2.json()) == 2
    assert page2.json()[0]["mensaje"] == "Mensaje 2"
    assert page2.json()[1]["mensaje"] == "Mensaje 1"

    # 3. Filtro por autor autenticado
    author_res = client.get(
        f"/api/v1/tickets/{ticket_id}/comments?autor={settings.MASTER_ADMIN_EMAIL.split('@')[0]}",
        headers=headers,
    )
    assert author_res.status_code == 200
    assert len(author_res.json()) == 4

    # 4. Filtro con metacaracteres regex debe escaparse (no devolver 500 ni matchear como wildcard '.*')
    regex_res = client.get(f"/api/v1/tickets/{ticket_id}/comments?autor=.*", headers=headers)
    assert regex_res.status_code == 200
    assert regex_res.json() == []

    # 5. Conteo con filtro y fecha de hoy
    from datetime import date

    hoy_str = date.today().isoformat()
    date_res = client.get(f"/api/v1/tickets/{ticket_id}/comments?fecha_desde={hoy_str}", headers=headers)
    assert date_res.status_code == 200
    assert len(date_res.json()) == 4
