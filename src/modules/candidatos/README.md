# Módulo de Candidatos (`src/modules/candidatos`)

Módulo autónomo (*Package by Feature*) que actúa como puente temporal para el registro y consulta de candidatos, postulaciones crediticias y almacenamiento de **papelería** dentro de la API de **Coopya Sistemas**.

---

## 1. Responsabilidad y Arquitectura

- **Colección dedicada en MongoDB**: `candidatos`.
- **Almacenamiento Binario Aislado en GridFS**:
  - Bucket exclusivo: `candidatos_papeleria`.
  - Colecciones físicas: `candidatos_papeleria.files` y `candidatos_papeleria.chunks`.
  - **Completamente aislado** de los archivos de la ticketera (`fs.files` / `fs.chunks`).
- **Validación de Papelería**:
  - Estrictamente **1 solo archivo** adjunto por candidato.
  - Formatos admitidos: Documentos **PDF** (`.pdf`) o imágenes (**PNG, JPEG, WebP, BMP**).
  - Límite máximo: **25 MB**.
- **Limpieza en Cascada**: Al eliminar un candidato (`DELETE`), se purga físicamente su archivo y chunks de GridFS.
- **Nomenclatura CamelCase**: Mantiene compatibilidad directa con los contratos JSON del frontend y aplicaciones cliente (`nombreCompleto`, `ingresoMensual`, `productoSeleccionado`, etc.).

---

## 2. Estructura de Archivos

```text
src/modules/candidatos/
├── __init__.py           # Exportaciones del módulo
├── model.py              # Modelos Beanie: Candidato y ProductoSeleccionado
├── schemas.py            # Esquemas Pydantic v2 (CandidatoCreate, CandidatoResponse)
├── repository.py         # Repositorio de candidatos en MongoDB
├── gridfs_service.py     # Servicio GridFS en bucket 'candidatos_papeleria'
├── service.py            # Lógica de registro, papelería y eliminación
├── controller.py         # Endpoints FastAPI (/api/v1/candidatos)
└── README.md             # Esta documentación
```

---

## 3. Endpoints de la API

Montados bajo `/api/v1/candidatos`:

| Método | Endpoint | Estado HTTP | Auth Requerida | Descripción |
| :--- | :--- | :---: | :---: | :--- |
| `POST` | `/api/v1/candidatos` | `201 Created` | **Público** | Registra una postulación mediante `multipart/form-data` con JSON `data` y archivo opcional `papeleria`. |
| `GET` | `/api/v1/candidatos/{id}` | `200 OK` | **Bearer Token** | Obtiene el detalle de un candidato por su ObjectId. Retorna `404` si no existe. |
| `GET` | `/api/v1/candidatos` | `200 OK` | **Bearer Token** | Listado paginado de candidatos ordenados del más reciente al más antiguo. |
| `GET` | `/api/v1/candidatos/papeleria/{file_id}` | `200 OK` | **Bearer Token** | Previsualiza / descarga inline un archivo de papelería (PDF o imagen) desde GridFS por su `file_id`. |
| `DELETE` | `/api/v1/candidatos/{id}` | `204 No Content` | **Bearer Token** | Elimina un candidato y purga en cascada su papelería de GridFS. |

---

## 4. Ejemplo de Creación (`POST /api/v1/candidatos`)

La petición se envía bajo `Content-Type: multipart/form-data` con dos partes:
1. **`data`** (Texto / JSON String): Contiene la información personal y financiera.
2. **`papeleria`** (Archivo binario opcional): Archivo PDF o imagen.

### En JavaScript / React (Frontend):
```javascript
const formData = new FormData();
formData.append("data", JSON.stringify({
  nombreCompleto: "María González",
  dni: "30123456",
  email: "maria@email.com",
  telefono: "+54 11 5555-5555",
  direccion: "Av. Corrientes 1234, CABA",
  genero: "female",
  edad: 42,
  situacionLaboral: "graciable",
  ingresoMensual: 400000,
  moneda: "ARS",
  bancosSeleccionados: ["nacion", "provincia"],
  productoSeleccionado: {
    familia: "Asistodo",
    plan: "1",
    monto: 400000,
    plazoMeses: 12
  },
  origen: "web"
}));

// Si el usuario seleccionó un archivo:
if (archivoFile) {
  formData.append("papeleria", archivoFile);
}

const response = await fetch("/api/v1/candidatos", {
  method: "POST",
  body: formData
});
const data = await response.json();
```

### Respuesta (`201 Created`):
```json
{
  "id": "66f1234567890abcdef12345",
  "nombreCompleto": "María González",
  "dni": "30123456",
  "email": "maria@email.com",
  "telefono": "+54 11 5555-5555",
  "direccion": "Av. Corrientes 1234, CABA",
  "genero": "female",
  "edad": 42,
  "situacionLaboral": "graciable",
  "ingresoMensual": 400000.0,
  "moneda": "ARS",
  "bancosSeleccionados": [
    "nacion",
    "provincia"
  ],
  "productoSeleccionado": {
    "familia": "Asistodo",
    "plan": "1",
    "monto": 400000.0,
    "plazoMeses": 12
  },
  "origen": "web",
  "papeleria": "/api/v1/candidatos/papeleria/66f1234567890abcdef99999",
  "fechaCreacion": "2026-09-23T09:40:00Z"
}
```

---

## 5. Visualización / Descarga de Papelería

### Petición (`GET /api/v1/candidatos/papeleria/{file_id}`)
- **Encabezado requerido:** `Authorization: Bearer <token>`
- **Respuesta:** Stream binario directo desde el bucket `candidatos_papeleria` de GridFS.
- **Headers de respuesta:**
  - `Content-Type`: `application/pdf` o `image/png` / `image/jpeg`
  - `Content-Disposition`: `inline; filename="documento.pdf"` (permite visualización directa en visor web sin forzar descarga inmediata).

