# 🎮 Capa de Controladores y Endpoints (`src/controllers/`)

La capa de **Controladores** expone la interfaz HTTP RESTful y los canales en tiempo real de la API utilizando **FastAPI**. Es la puerta de entrada para los clientes web (Frontend), manejando la serialización, negociación de contenido, inyección de dependencias y códigos de estado HTTP.

---

## 📂 Estructura del Directorio

```text
src/controllers/
├── health_controller.py    # Health check de liveness y readiness para infraestructura
├── api.py                  # Enrutador agregador central con prefijo /api/v1
├── v1/                     # Controladores versionados (v1)
│   ├── ticket_controller.py   # Endpoints de ciclo de vida de tickets, SSE y bloqueos
│   ├── file_controller.py     # Streaming y descarga de imágenes desde MongoDB GridFS
│   └── catalog_controller.py  # Endpoints de catálogos y opciones para React
└── README.md               # Este documento de arquitectura y especificación técnica
```

---

## 🗺️ Jerarquía de Enrutamiento

```text
FastAPI (app en src/main.py)
├── GET /health                         (health_controller.py)
└── /api/v1                             (api.py)
    ├── /tickets                        (v1/ticket_controller.py)
    ├── /files                          (v1/file_controller.py)
    └── /catalogs                       (v1/catalog_controller.py)
```

---

## 📄 Especificación Detallada de Controladores

### 1. 🩺 `health_controller.py` — Monitoreo y Health Check
- **Ruta**: `GET /health`
- **Propósito**: Sonda de verificación de estado (*liveness probe*) para Railway, balanceadores de carga y herramientas de uptime.
- **Respuesta (`200 OK`)**:
  ```json
  {
    "status": "ok",
    "message": "Service is running"
  }
  ```

---

### 2. 🎫 `v1/ticket_controller.py` — Gestión de Tickets y Concurrencia

Es el controlador más completo de la API. Integra subida de imágenes, streaming SSE y bloqueo optimista multi-operador.

#### A. Ciclo de Vida y CRUD:

| Método | Endpoint | Content-Type | Código Exitoso | Descripción |
| :--- | :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/tickets/` | `multipart/form-data` | `201 Created` | Crea un ticket con texto e imágenes opcionales bajo rollback automático. |
| `GET` | `/api/v1/tickets/` | — | `200 OK` | Lista tickets con soporte de filtros dinámicos y paginación (`skip`, `limit`). |
| `GET` | `/api/v1/tickets/{id}` | — | `200 OK` | Obtiene el detalle completo de un ticket por su ID. |
| `PATCH` | `/api/v1/tickets/{id}` | `application/json` | `200 OK` | Actualización parcial (`titulo`, `estado`, `prioridad`, `columna`, etc.). |
| `PATCH` | `/api/v1/tickets/{id}/read` | — | `200 OK` | Marca el ticket como leído (`leido = true`) y emite `ticket_actualizado`. |
| `DELETE`| `/api/v1/tickets/{id}` | — | `204 No Content` | Elimina el ticket y sus fotos en GridFS (protegido contra concurrencia). |

#### B. Bloqueo Optimista y Concurrencia (Locking):

| Método | Endpoint | Payload | Respuestas | Descripción |
| :--- | :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/tickets/{id}/bloquear` | `{"usuario": "correo"}` | `200 OK` / `409 Conflict` | Solicita edición exclusiva con TTL de 180s. Si otro operador lo tiene, retorna 409 con cabecera `X-Locked-By`. |
| `POST` | `/api/v1/tickets/{id}/desbloquear` | `{"usuario": "correo"}` | `200 OK` | Libera el bloqueo al cerrar o cancelar el modal y emite evento SSE `ticket_desbloqueado`. |
| `GET` | `/api/v1/tickets/{id}/bloqueo` | — | `200 OK` | Consulta el estado: `{"bloqueado": false}` o `{"bloqueado": true, "usuario": "...", "expira_en": "..."}`. |

#### C. Tiempo Real (Server-Sent Events - SSE):
- **Ruta**: `GET /api/v1/tickets/stream`
- **Content-Type**: `text/event-stream`
- **Cabeceras**: `Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`
- **Keep-Alive**: Emite comentarios `: ping\n\n` cada 15 segundos para evitar desconexiones por inactividad en proxies y Railway.
- **Eventos Emitidos**: `nuevo_ticket`, `ticket_actualizado`, `ticket_eliminado`, `ticket_bloqueado`, `ticket_desbloqueado`.

#### D. Manipulación de Adjuntos de Fotos:
- **`POST /api/v1/tickets/{id}/images`**: Sube imágenes adicionales a un ticket existente vía GridFS y emite `ticket_actualizado`.
- **`DELETE /api/v1/tickets/{id}/images/{file_id}`**: Remueve una foto individual del ticket y la purga físicamente de GridFS.

---

### 3. 🖼️ `v1/file_controller.py` — Servidor de Archivos GridFS

Sirve las imágenes adjuntas almacenadas en MongoDB GridFS mediante streams HTTP de alto rendimiento:

- **Ruta**: `GET /api/v1/files/{file_id}`
- **Respuesta**: `StreamingResponse(file_iterator(), media_type=content_type)`
- **Cabeceras de Optimización Web**:
  - `Content-Disposition: inline; filename="..."` (permite previsualización directa en la etiqueta `<img>` del navegador).
  - `Cache-Control: public, max-age=86400, immutable` (almacena en caché local del cliente durante 24 horas, reduciendo tráfico y lecturas a la base de datos).
- **Consumo de Memoria Cero**: Lee los fragmentos de 255 KB bajo demanda (`grid_out.readchunk()`), permitiendo servir archivos concurrentemente sin saturar la RAM del contenedor.

---

### 4. 🧱 `v1/catalog_controller.py` — Catálogos del Sistema

Alimenta los componentes de selección del frontend mediante respuestas estandarizadas `List[OptionItem]`:

| Método | Endpoint | Respuesta Modelo | Ejemplo de Elemento |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/catalogs/estados` | `List[OptionItem]` | `{"value": "en_progreso", "label": "En Progreso"}` |
| `GET` | `/api/v1/catalogs/prioridades` | `List[OptionItem]` | `{"value": "critica", "label": "Crítica"}` |
| `GET` | `/api/v1/catalogs/asignables` | `List[OptionItem]` | `{"value": "facundo_bernard", "label": "Facundo Bernard"}` |

---

## 🛡️ Matriz de Códigos de Respuesta HTTP

| Código | Significado | Escenario de Uso en la API |
| :---: | :--- | :--- |
| **`200 OK`** | Petición exitosa | Lecturas (`GET`), actualizaciones parciales (`PATCH`), bloqueos y catálogos. |
| **`201 Created`** | Recurso creado | Creación exitosa de ticket (`POST /api/v1/tickets/`). |
| **`204 No Content`** | Eliminación exitosa | Eliminación de ticket (`DELETE /api/v1/tickets/{id}`). |
| **`400 Bad Request`** | Error en la solicitud | Superación de límite diario de 8 tickets, cooldown menor a 60s o formato de archivo no permitido. |
| **`404 Not Found`** | Recurso no encontrado | ID de ticket o de archivo GridFS inexistente en la base de datos. |
| **`409 Conflict`** | Conflicto concurrente | Ticket en edición por otro operador al intentar bloquearlo o eliminarlo. |
| **`422 Unprocessable`** | Validación Pydantic fallida | Payload mal formado, correo con sintaxis inválida o columna fuera del rango `1..4`. |
