# 📦 Capa de Modelos de Base de Datos (`src/models/`)

La capa de **Modelos** define las entidades persistentes y estructuras de datos almacenadas en **MongoDB**, utilizando el ODM asíncrono **[Beanie](https://beanie-odm.dev/)** basado en **Motor** y **Pydantic v2**.

---

## 📂 Estructura del Directorio

```text
src/models/
├── ticket_model.py         # Definición del Documento Ticket, submodelos y enumeradores
└── README.md               # Este documento de arquitectura y especificación técnica
```

---

## 📑 Modelo Principal: `Ticket` (`ticket_model.py`)

Hereda de `beanie.Document` y se mapea directamente a la colección `"tickets"` en MongoDB.

```python
class Ticket(Document):
    titulo: str = Field(..., min_length=3, max_length=150)
    descripcion: str
    imagenes: List[str] = Field(default_factory=list)
    asignar: Optional[str] = Field(default=None)
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fecha_edicion: Optional[datetime] = Field(default=None)
    identificador: Indexed(str, unique=True, sparse=True)
    correo: EmailStr
    prioridad: PrioridadEnum = Field(default=PrioridadEnum.MEDIA)
    estado: EstadoEnum = Field(default=EstadoEnum.ABIERTO)
    columna: int = Field(default=1, ge=1, le=4)
    leido: bool = Field(default=False)
    frecuencia: Optional[Frecuencia] = Field(default=None)

    class Settings:
        name = "tickets"
```

---

### 📊 Especificación de Campos

| Campo | Tipo de Dato | Restricciones / Validaciones | Valor por Defecto | Descripción |
| :--- | :--- | :--- | :--- | :--- |
| `id` | `PydanticObjectId` | Autogenerado por MongoDB (`_id`) | Autogenerado | Identificador único del documento. |
| `identificador` | `Indexed(str)` | `unique=True, sparse=True` | Generado atómicamente | Código correlativo legible para humanos (ej: `"TCK-1001"`). Posee un índice único en MongoDB. |
| `titulo` | `str` | Longitud: `3` a `150` caracteres | *Requerido* | Título o resumen conciso de la solicitud. |
| `descripcion` | `str` | Texto sin límite | *Requerido* | Detalle completo del incidente o requerimiento. |
| `correo` | `EmailStr` | Formato RFC válido de email | *Requerido* | Correo del solicitante. Utilizado para control de cuotas y rate limiting. |
| `asignar` | `Optional[str]` | Nombre del técnico | `None` | Técnico o colaborador asignado a la resolución (ej: `"Facundo Bernard"`). |
| `columna` | `int` | `1 <= columna <= 4` | `1` | Ubicación en el tablero Kanban: `1`: TICKET, `2`: HITOS, `3`: TAREAS, `4`: TAREAS PERIÓDICAS. |
| `prioridad` | `PrioridadEnum` | `"baja" \| "media" \| "alta" \| "critica"` | `"media"` | Nivel de criticidad del ticket. |
| `estado` | `EstadoEnum` | `"abierto" \| "en_progreso" \| "resuelto" \| "cerrado"` | `"abierto"` | Estado en el flujo de resolución. |
| `leido` | `bool` | Booleano | `False` | Flag de lectura. Permite al frontend mostrar el badge `"NUEVO"` hasta que un operador lo abra. |
| `frecuencia` | `Optional[Frecuencia]` | Submodelo `Frecuencia` o `None` | `None` | Frecuencia de repetición cuando pertenece a la columna de Tareas Periódicas (`4`). |
| `imagenes` | `List[str]` | URLs relativas de archivos | `[]` | Lista de endpoints de imágenes adjuntas en MongoDB GridFS (`/api/v1/files/{file_id}`). |
| `fecha_creacion` | `datetime` | UTC timezone-aware | `now(UTC)` | Fecha y hora exacta de registro. |
| `fecha_edicion` | `Optional[datetime]` | UTC timezone-aware | `None` | Fecha y hora de la última modificación (actualizada automáticamente en cada actualización o cambio de imágenes). |

---

## 🧩 Submodelos y Enumeradores

### 1. `Frecuencia` (Subdocumento Embebido)
Define la periodicidad para tickets recurrentes o programados:

```python
class Frecuencia(BaseModel):
    numero: int = Field(default=1, ge=1, description="Intervalo numérico")
    periodo: Literal["Días", "Semanas", "Meses", "Años"] = Field(..., description="Período de repetición")
```

- **`numero`**: Entero estrictamente mayor o igual a 1 (ej: `1`, `2`, `15`).
- **`periodo`**: Uno de los cuatro valores admitidos con mayúscula inicial y tildes exactas: `"Días"`, `"Semanas"`, `"Meses"`, `"Años"`.

### 2. `PrioridadEnum`
```python
class PrioridadEnum(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"
```

### 3. `EstadoEnum`
```python
class EstadoEnum(str, Enum):
    ABIERTO = "abierto"
    EN_PROGRESO = "en_progreso"
    RESUELTO = "resuelto"
    CERRADO = "cerrado"
```

---

## 🗄️ Colecciones Relacionadas en MongoDB

Además de la colección principal `tickets`, el sistema interactúa con las siguientes colecciones gestionadas por MongoDB:

1. **`counters`**:
   - Almacena el contador atómico secuencial:
     ```json
     { "_id": "ticket_seq", "seq": 1001 }
     ```
   - Utilizado por `TicketService` mediante `find_one_and_update` con `$inc` atómico. Esto garantiza que ningún ticket colisione ni repita correlativos incluso ante eliminación previa de tickets.
2. **`fs.files` y `fs.chunks` (MongoDB GridFS)**:
   - Buckets donde se almacenan físicamente las imágenes adjuntas en fragmentos binarios de 255 KB, evitando el límite de 16 MB de los documentos BSON convencionales.

---

## 🔄 Inicialización en el Ciclo de Vida de FastAPI

En [`src/main.py`](file:///c:/Users/monti/Desktop/Coopya_sistemas/ticketscoopya_backend/src/main.py), los modelos se registran e inicializan durante el startup de la aplicación a través de Beanie:

```python
from .models.ticket_model import Ticket
from .config.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inicializa los índices de MongoDB automáticamente
    await init_db([Ticket])
    yield
```
