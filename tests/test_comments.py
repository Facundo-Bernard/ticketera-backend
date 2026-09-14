import sys
import os
import uuid
import asyncio
from beanie import PydanticObjectId
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import pytest
    fixture_decorator = pytest.fixture(scope="module")
except ImportError:
    def fixture_decorator(func):
        return func

from starlette.testclient import TestClient
from src.main import app
from src.core.sse_manager import sse_manager

@fixture_decorator
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
        "columna": 1
    }
    res = client.post("/api/v1/tickets/", data=form_data)
    assert res.status_code == 201, f"Error al crear ticket auxiliar: {res.text}"
    return res.json()

def test_create_and_get_comments_flow(client):
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]

    # 1. El ticket recién creado debe tener 0 comentarios
    count_res = client.get(f"/api/v1/tickets/{ticket_id}/comments/count")
    assert count_res.status_code == 200
    assert count_res.json() == {"ticket_id": ticket_id, "total": 0}

    # 2. Agregar primer comentario
    comment_data_1 = {
        "autor": "Facundo Bernard",
        "mensaje": "Se inició la revisión del caso técnico."
    }
    create_res_1 = client.post(f"/api/v1/tickets/{ticket_id}/comments", json=comment_data_1)
    assert create_res_1.status_code == 201
    c1 = create_res_1.json()
    assert c1["ticket_id"] == ticket_id
    assert c1["autor"] == comment_data_1["autor"]
    assert c1["mensaje"] == comment_data_1["mensaje"]
    assert "fecha_creacion" in c1
    assert "id" in c1

    # 3. Agregar segundo comentario
    comment_data_2 = {
        "autor": "Nahuel Monti",
        "mensaje": "Confirmado, el servidor ya responde adecuadamente."
    }
    create_res_2 = client.post(f"/api/v1/tickets/{ticket_id}/comments", json=comment_data_2)
    assert create_res_2.status_code == 201
    c2 = create_res_2.json()

    # 4. Verificar conteo actualizado
    count_res_2 = client.get(f"/api/v1/tickets/{ticket_id}/comments/count")
    assert count_res_2.status_code == 200
    assert count_res_2.json()["total"] == 2

    # 5. Listar comentarios y validar orden del más nuevo al más viejo
    list_res = client.get(f"/api/v1/tickets/{ticket_id}/comments")
    assert list_res.status_code == 200
    comments = list_res.json()
    assert len(comments) == 2
    assert comments[0]["id"] == c2["id"]  # c2 es el más reciente
    assert comments[1]["id"] == c1["id"]  # c1 es el más antiguo

    # 6. Eliminar el primer comentario
    del_res = client.delete(f"/api/v1/tickets/{ticket_id}/comments/{c1['id']}")
    assert del_res.status_code == 204

    # 7. Verificar que el conteo disminuyó a 1
    count_res_3 = client.get(f"/api/v1/tickets/{ticket_id}/comments/count")
    assert count_res_3.json()["total"] == 1

    list_res_2 = client.get(f"/api/v1/tickets/{ticket_id}/comments")
    remaining_comments = list_res_2.json()
    assert len(remaining_comments) == 1
    assert remaining_comments[0]["id"] == c2["id"]

def test_comment_nonexistent_ticket(client):
    fake_ticket_id = "507f1f77bcf86cd799439011"
    res = client.post(
        f"/api/v1/tickets/{fake_ticket_id}/comments",
        json={"autor": "Operador", "mensaje": "Mensaje en ticket inexistente"}
    )
    assert res.status_code == 404

    res_get = client.get(f"/api/v1/tickets/{fake_ticket_id}/comments")
    assert res_get.status_code == 404

def test_delete_nonexistent_comment(client):
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]
    fake_comment_id = "507f1f77bcf86cd799439011"

    del_res = client.delete(f"/api/v1/tickets/{ticket_id}/comments/{fake_comment_id}")
    assert del_res.status_code == 404

def test_comment_sse_events(client):
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    queue = loop.run_until_complete(sse_manager.subscribe())
    try:
        # Crear comentario
        comment_payload = {"autor": "Operador SSE", "mensaje": "Verificación de evento en tiempo real"}
        create_res = client.post(f"/api/v1/tickets/{ticket_id}/comments", json=comment_payload)
        assert create_res.status_code == 201
        comment_obj = create_res.json()

        # Verificar que el evento llegó a la cola SSE
        assert not queue.empty()
        msg = queue.get_nowait()
        assert msg["event"] == "nuevo_comentario"
        assert msg["data"]["ticket_id"] == ticket_id
        assert msg["data"]["comentario"]["id"] == comment_obj["id"]

        # Eliminar comentario
        del_res = client.delete(f"/api/v1/tickets/{ticket_id}/comments/{comment_obj['id']}")
        assert del_res.status_code == 204

        # Verificar evento de eliminación
        assert not queue.empty()
        msg_del = queue.get_nowait()
        assert msg_del["event"] == "comentario_eliminado"
        assert msg_del["data"]["ticket_id"] == ticket_id
        assert msg_del["data"]["comment_id"] == comment_obj["id"]
    finally:
        sse_manager.unsubscribe(queue)

def test_comment_filters_and_pagination(client):
    ticket = _create_helper_ticket(client)
    ticket_id = ticket["id"]

    # Insertar 4 comentarios (2 de Carlos, 2 de Maria)
    client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"autor": "Carlos Soporte", "mensaje": "Mensaje 1"})
    client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"autor": "Maria Redes", "mensaje": "Mensaje 2"})
    client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"autor": "Carlos Soporte", "mensaje": "Mensaje 3"})
    client.post(f"/api/v1/tickets/{ticket_id}/comments", json={"autor": "Maria Redes", "mensaje": "Mensaje 4"})

    # 1. Probar paginación limit=2, skip=0 (los 2 más nuevos: Mensaje 4 y Mensaje 3)
    page1 = client.get(f"/api/v1/tickets/{ticket_id}/comments?skip=0&limit=2")
    assert page1.status_code == 200
    assert len(page1.json()) == 2
    assert page1.json()[0]["mensaje"] == "Mensaje 4"
    assert page1.json()[1]["mensaje"] == "Mensaje 3"

    # 2. Probar paginación limit=2, skip=2 (los siguientes 2 más viejos: Mensaje 2 y Mensaje 1)
    page2 = client.get(f"/api/v1/tickets/{ticket_id}/comments?skip=2&limit=2")
    assert page2.status_code == 200
    assert len(page2.json()) == 2
    assert page2.json()[0]["mensaje"] == "Mensaje 2"
    assert page2.json()[1]["mensaje"] == "Mensaje 1"

    # 3. Probar filtro por autor
    carlos_res = client.get(f"/api/v1/tickets/{ticket_id}/comments?autor=Carlos")
    assert carlos_res.status_code == 200
    carlos_comments = carlos_res.json()
    assert len(carlos_comments) == 2
    assert all("Carlos" in c["autor"] for c in carlos_comments)

    # 4. Probar conteo con filtro
    carlos_count = client.get(f"/api/v1/tickets/{ticket_id}/comments/count?autor=Carlos")
    assert carlos_count.status_code == 200
    assert carlos_count.json()["total"] == 2

    # 5. Probar filtro por fecha (hoy)
    from datetime import date
    hoy_str = date.today().isoformat()
    date_res = client.get(f"/api/v1/tickets/{ticket_id}/comments?fecha_desde={hoy_str}")
    assert date_res.status_code == 200
    assert len(date_res.json()) == 4

