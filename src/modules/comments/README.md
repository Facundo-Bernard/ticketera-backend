# Módulo de Comentarios (`src/modules/comments`)

Módulo autónomo (*Package by Feature*) responsable de la gestión de comentarios asociados a tickets en la plataforma **Ticketera Coopya**, implementado bajo el **Patrón Bucket de MongoDB** (*Document-per-Thread*).

---

## 1. Responsabilidad y Arquitectura

Este módulo sigue una arquitectura modular desacoplada del módulo de tickets (dejando intacta la colección `tickets`):
- **Patrón Bucket (Colección `comment_buckets`)**:
  - Cada documento representa el hilo completo de comentarios de un ticket (`ticket_id: Indexed(unique=True)`).
  - Almacena un contador atómico `total: int` y el array `comentarios: List[CommentItem]`.
- **Paginación Nativa con Proyección `$slice` de MongoDB**:
  - Paginación de 10 en 10 sin transferir comentarios innecesarios por la red.
  - O(1) en lecturas: Trae la ventana solicitada de un solo golpe de disco.
- **Diccionario de Filtros Avanzado**:
  - Filtro por `autor` (búsqueda insensible a mayúsculas/minúsculas vía `$regexMatch`).
  - Filtro por rango de fechas (`fecha_desde`, `fecha_hasta`).
  - Paginación (`skip`, `limit`, por defecto `10`).
- **Operaciones Atómicas sin Bloqueos**:
  - Inserción con `$push` y `$inc: {"total": 1}` con `upsert=True`.
  - Eliminación con `$pull` por `id` del subdocumento y `$inc: {"total": -1}`.
- **Sincronización en Tiempo Real (SSE)**:
  - Emisión instantánea de `nuevo_comentario` y `comentario_eliminado` a todos los operadores conectados vía `sse_manager`.

---

## 2. Estructura de Archivos

```text
src/modules/comments/
├── __init__.py           # Exportaciones del módulo
├── model.py              # Modelos CommentBucket y CommentItem
├── schemas.py            # Esquemas Pydantic v2 (CommentCreate, CommentFilter, CommentResponse)
├── repository.py         # Hereda de BaseRepository[CommentBucket, ...] con $slice y $filter
├── service.py            # Lógica de negocio, validación de ticket y SSE
├── controller.py         # Endpoints FastAPI (/api/v1/tickets/{ticket_id}/comments)
└── README.md             # Esta documentación
```

---

## 3. Endpoints de la API

Montados bajo `/api/v1/tickets/{ticket_id}/comments`:

| Método | Endpoint | Parámetros Query | Estado | Descripción |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | `autor`, `fecha_desde`, `fecha_hasta`, `skip`, `limit` (default: 10) | `200 OK` | Listar comentarios paginados con filtros opcionales. |
| `GET` | `/count` | `autor`, `fecha_desde`, `fecha_hasta` | `200 OK` | Conteo total o filtrado (`{"ticket_id": "...", "total": 12}`). |
| `POST` | `/` | Body: `{"autor": "...", "mensaje": "..."}` | `201 Created` | Agrega comentario al bucket del ticket y emite SSE `nuevo_comentario`. |
| `DELETE` | `/{comment_id}` | Path: `comment_id` | `204 No Content` | Elimina comentario del array del bucket y emite SSE `comentario_eliminado`. |

---

## 4. Eventos Server-Sent Events (SSE)

- **`nuevo_comentario`**:
  ```json
  {
    "event": "nuevo_comentario",
    "data": {
      "ticket_id": "66d8f1...",
      "comentario": {
        "id": "66d9b2...",
        "ticket_id": "66d8f1...",
        "autor": "Técnico Soporte",
        "mensaje": "Se revisó la conexión...",
        "fecha_creacion": "2026-09-14T10:30:00Z"
      }
    }
  }
  ```
- **`comentario_eliminado`**:
  ```json
  {
    "event": "comentario_eliminado",
    "data": {
      "ticket_id": "66d8f1...",
      "comment_id": "66d9b2..."
    }
  }
  ```
