# 🎫 Sistema de Tickets - Backend (FastAPI + MongoDB GridFS)

Backend robusto para la gestión y seguimiento de tickets de soporte con almacenamiento nativo de imágenes en **MongoDB GridFS**, arquitectura en capas y soporte de **Rollback automático**.

---

## 🛠️ Tecnologías Utilizadas

- **Lenguaje**: Python 3.12+
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Asíncrono, OpenAPI 3.1)
- **ODM / Base de Datos**: [Beanie](https://beanie-odm.dev/) & [Motor](https://motor.readthedocs.io/) (MongoDB Async)
- **Almacenamiento de Archivos**: **MongoDB GridFS** nativo en streams
- **Validación de Datos**: [Pydantic v2](https://docs.pydantic.dev/)
- **Servidor ASGI**: [Uvicorn](https://www.uvicorn.org/)
- **Testing**: [Pytest](https://docs.pytest.org/)

---

## 🚀 Guía de Inicio Rápido (Setup)

### 1. Clonar el repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd ticketscoopya_backend
```

### 2. Crear y activar el entorno virtual

- **En Windows**:
  ```bash
  python -m venv venv
  venv\Scripts\activate
  ```
- **En Linux / macOS**:
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crea el archivo `.env` a partir de `.env.example`:
- **En Windows**:
  ```bash
  copy .env.example .env
  ```
- **En Linux / macOS**:
  ```bash
  cp .env.example .env
  ```

Asegúrate de que MongoDB esté corriendo en tu sistema o ajusta la variable `MONGO_URI` dentro del archivo `.env`:
```env
MONGO_URI=mongodb://localhost:27017/tickets_db
BACKEND_CORS_ORIGINS=["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]
```

### 5. Iniciar el servidor
```bash
uvicorn src.main:app --reload
```

---

## 🌐 URLs de Acceso

- 📖 **Documentación Interactiva (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- 📑 **Documentación Alternativa (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- 🎫 **Visor Web de Tickets (Frontend Integrado)**: [http://localhost:8000/](http://localhost:8000/)
- 🩺 **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 📌 Guía de Endpoints y Payloads para Frontend

Base URL: `http://localhost:8000/api/v1`

---

### 1. 🎫 Tickets (`/api/v1/tickets`)

#### `POST /api/v1/tickets/` — Crear Ticket con Imágenes
> **Content-Type**: `multipart/form-data`  
> **Seguridad**: Cooldown de 60 segundos por correo y máximo 8 tickets diarios.  
> **Formatos de imagen permitidos**: PNG, JPEG, JPG, WebP, GIF, SVG, AVIF, BMP.

**Campos del Formulario (`FormData`)**:
| Campo | Tipo | Obligatorio | Descripción | Ejemplo |
| :--- | :--- | :---: | :--- | :--- |
| `titulo` | `string` | Sí | Título del problema (3-150 caracteres) | `"Falla en impresora de recepción"` |
| `descripcion` | `string` | Sí | Detalle completo del incidente | `"No toma papel y parpadea luz roja"` |
| `correo` | `string (email)` | Sí | Correo del solicitante | `"carlos@coopya.com"` |
| `prioridad` | `string` | No | `"baja" \| "media" \| "alta" \| "critica"` (default: `"media"`) | `"alta"` |
| `asignar` | `string` | No | Nombre del técnico asignado | `"Facundo Bernard"` |
| `files` | `File[] (binario)` | No | Archivos de imagen adjuntos (múltiples) | `captura1.png`, `foto2.jpg` |

**Respuesta Exitosa (`201 Created`)**:
```json
{
  "id": "66d34b9e4a1b2c3d4e5f6a7b",
  "identificador": "TCK-1001",
  "titulo": "Falla en impresora de recepción",
  "descripcion": "No toma papel y parpadea luz roja",
  "correo": "carlos@coopya.com",
  "prioridad": "alta",
  "estado": "abierto",
  "asignar": "Facundo Bernard",
  "imagenes": [
    "/api/v1/files/66d34b9e4a1b2c3d4e5f6a7c",
    "/api/v1/files/66d34b9e4a1b2c3d4e5f6a7d"
  ],
  "fecha_creacion": "2026-08-31T18:24:39.123456Z",
  "fecha_edicion": null
}
```

---

#### `GET /api/v1/tickets/` — Listar Tickets (con Filtros y Paginación)
> **Método**: `GET`  
> **Query Params (todos opcionales)**:

| Parámetro | Tipo | Descripción | Ejemplo |
| :--- | :--- | :--- | :--- |
| `fecha_desde` | `string` | Filtro desde fecha (autocompleta a las 00:00 UTC) | `2026-08-01` o `01/08/2026` |
| `fecha_hasta` | `string` | Filtro hasta fecha (autocompleta a las 23:59 UTC) | `2026-08-31` o `31/08/2026` |
| `estado` | `string` | `"abierto" \| "en_progreso" \| "resuelto" \| "cerrado"` | `en_progreso` |
| `prioridad` | `string` | `"baja" \| "media" \| "alta" \| "critica"` | `critica` |
| `asignar` | `string` | Búsqueda parcial / insensible a mayúsculas | `Facundo` |
| `skip` | `int` | Paginación: registros a omitir (default: `0`) | `0` |
| `limit` | `int` | Paginación: cantidad a traer (default: `100`, máx: `500`) | `20` |

**Respuesta Exitosa (`200 OK`)**:
```json
[
  {
    "id": "66d34b9e4a1b2c3d4e5f6a7b",
    "identificador": "TCK-1001",
    "titulo": "Falla en impresora",
    "descripcion": "No toma papel",
    "correo": "carlos@coopya.com",
    "prioridad": "alta",
    "estado": "abierto",
    "asignar": "Facundo Bernard",
    "imagenes": ["/api/v1/files/66d34b9e4a1b2c3d4e5f6a7c"],
    "fecha_creacion": "2026-08-31T18:24:39.123456Z",
    "fecha_edicion": null
  }
]
```

---

#### `GET /api/v1/tickets/{id}` — Detalle de Ticket
- **Respuesta (`200 OK`)**: Objeto `TicketResponse`.
- **Respuesta (`404 Not Found`)**: `{"error": "Not Found", "message": "Ticket con id ... no encontrado"}`

---

#### `PATCH /api/v1/tickets/{id}` — Actualizar Estado o Campos
> **Content-Type**: `application/json`  
> Permite enviar únicamente los campos que se desean modificar.

**Payload de Entrada**:
```json
{
  "estado": "en_progreso",
  "asignar": "Nahuel Monti",
  "prioridad": "critica"
}
```

**Respuesta (`200 OK`)**: Objeto `TicketResponse` con `fecha_edicion` actualizada automáticamente en UTC.

---

#### `DELETE /api/v1/tickets/{id}` — Eliminar Ticket y sus Fotos
- **Respuesta (`204 No Content`)**: Elimina el ticket de MongoDB y borra automáticamente todas sus fotos asociadas de GridFS.

---

#### `DELETE /api/v1/tickets/{id}/images/{file_id}` — Eliminar Foto Específica
- **Respuesta (`200 OK`)**: Elimina la foto puntual de GridFS y del array `imagenes` del ticket.

---

### 2. 🧱 Catálogos (`/api/v1/catalogs`)

Todos los catálogos devuelven el formato estándar `OptionItem[]` (`[{ value, label }]`) para vincular directamente con componentes `<select>` de React.

#### `GET /api/v1/catalogs/estados`
```json
[
  { "value": "abierto", "label": "Abierto" },
  { "value": "en_progreso", "label": "En Progreso" },
  { "value": "resuelto", "label": "Resuelto" },
  { "value": "cerrado", "label": "Cerrado" }
]
```

#### `GET /api/v1/catalogs/prioridades`
```json
[
  { "value": "baja", "label": "Baja" },
  { "value": "media", "label": "Media" },
  { "value": "alta", "label": "Alta" },
  { "value": "critica", "label": "Crítica" }
]
```

#### `GET /api/v1/catalogs/asignables`
```json
[
  { "value": "facundo_bernard", "label": "Facundo Bernard" },
  { "value": "nicolas_gonzalez", "label": "Nicolas Gonzalez" },
  { "value": "nahuel_monti", "label": "Nahuel Monti" }
]
```

---

### 3. 🖼️ Archivos e Imágenes (`/api/v1/files`)

#### `GET /api/v1/files/{file_id}`
- **Respuesta**: Stream binario directo de la imagen (`image/png`, `image/jpeg`, etc.).
- **Caché**: Incluye cabecera `Cache-Control: public, max-age=86400, immutable` (caché local de 24 horas en el navegador).
- **Uso en Frontend**:
  ```tsx
  <img src={`http://localhost:8000${url}`} alt="Adjunto" loading="lazy" />
  ```

---

## 🧪 Ejecución de Pruebas Automatizadas

Para correr toda la suite de pruebas unitarias y de integración:
```bash
pytest -v
```
