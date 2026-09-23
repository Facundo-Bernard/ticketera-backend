# Módulo de Candidatos (`src/modules/candidatos`)

Módulo autónomo (*Package by Feature*) que actúa como puente temporal para el registro y consulta de candidatos y postulaciones crediticias dentro de la API de **Coopya Sistemas**.

---

## 1. Responsabilidad y Arquitectura

- **Colección dedicada en MongoDB**: `candidatos`.
- **Independencia absoluta**: No interactúa ni modifica la lógica de tickets, comentarios ni usuarios del sistema de soporte.
- **Nomenclatura CamelCase**: Mantiene compatibilidad directa con los contratos JSON del frontend y aplicaciones cliente (`nombreCompleto`, `ingresoMensual`, `productoSeleccionado`, etc.).
- **Índices de Búsqueda**:
  - `dni`: Búsquedas rápidas por documento.
  - `email`: Verificación de contacto.
  - `-fechaCreacion`: Ordenamiento cronológico de las postulaciones más recientes.

---

## 2. Estructura de Archivos

```text
src/modules/candidatos/
├── __init__.py           # Exportaciones del módulo
├── model.py              # Modelos Beanie: Candidato y ProductoSeleccionado
├── schemas.py            # Esquemas Pydantic v2 (CandidatoCreate, CandidatoResponse)
├── repository.py         # Hereda de BaseRepository[Candidato, ...]
├── service.py            # Lógica de registro y consulta
├── controller.py         # Endpoints FastAPI (/api/v1/candidatos)
└── README.md             # Esta documentación
```

---

## 3. Endpoints de la API

Montados bajo `/api/v1/candidatos`:

| Método | Endpoint | Estado HTTP | Descripción |
| :--- | :--- | :---: | :--- |
| `POST` | `/api/v1/candidatos` | `201 Created` | Registra una postulación y retorna el candidato con su `id` generado. |
| `GET` | `/api/v1/candidatos/{id}` | `200 OK` | Obtiene el detalle de un candidato por su ObjectId. Retorna `404` si no existe. |
| `GET` | `/api/v1/candidatos` | `200 OK` | Listado paginado de candidatos ordenados del más reciente al más antiguo. |

---

## 4. Ejemplo de Payload

### Petición (`POST /api/v1/candidatos`)
```json
{
  "nombreCompleto": "María González",
  "dni": "30123456",
  "email": "maria@email.com",
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
```

### Respuesta (`201 Created`)
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
  "fechaCreacion": "2026-09-23T09:40:00Z"
}
```
