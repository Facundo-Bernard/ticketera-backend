# 📋 Capa de Esquemas y DTOs (`src/schemas/`)

La capa de **Esquemas** define los Contratos de Interfaz (DTOs - *Data Transfer Objects*) utilizados para validar, serializar y documentar el intercambio de datos entre los clientes (Frontend) y la API, utilizando **[Pydantic v2](https://docs.pydantic.dev/)**.

---

## 📂 Estructura del Directorio

```text
src/schemas/
├── catalog_schema.py       # Esquema estándar para opciones de catálogos (selects/dropdowns)
├── ticket_schema.py        # Esquemas de entrada, actualización, filtros y respuesta de tickets
└── README.md               # Este documento de arquitectura y especificación técnica
```

---

## 🎯 Principio de Diseño: Desacoplamiento de Modelos

En este sistema, los documentos de base de datos (`src/models/`) **nunca se exponen directamente al cliente**. Esta separación ofrece múltiples ventajas:

1. **Seguridad y Encapsulamiento**: Control estricto de qué campos son de solo lectura, cuáles se pueden crear y cuáles se pueden modificar.
2. **Validaciones en Entrada**: Pydantic v2 valida tipos, rangos, longitudes y formatos de email antes de que cualquier dato llegue a la capa de servicios o base de datos.
3. **Serialización Estandarizada**: Formatea fechas en UTC con sufijo `Z` y transforma IDs de MongoDB (`PydanticObjectId`) a strings limpios compatibles con JSON.

---

## 📄 Descripción Detallada de Módulos

### 1. 🧱 `catalog_schema.py` — Esquemas de Catálogos

Diseñado para alimentar componentes `<select>`, dropdowns y autocompletes en React.

```python
class OptionItem(BaseModel):
    value: str
    label: str
```

#### Endpoints que lo utilizan:
- `GET /api/v1/catalogs/estados`
- `GET /api/v1/catalogs/prioridades`
- `GET /api/v1/catalogs/asignables`

#### Ejemplo de Salida JSON:
```json
[
  { "value": "facundo_bernard", "label": "Facundo Bernard" },
  { "value": "nicolas_fernandez", "label": "Nicolas Fernandez" },
  { "value": "nahuel_monti", "label": "Nahuel Monti" }
]
```

---

### 2. 🎫 `ticket_schema.py` — Esquemas del Dominio de Tickets

#### A. `TicketCreate` (Entrada para Creación)
Utilizado para validar el formulario de alta en `POST /api/v1/tickets/`:

```python
class TicketCreate(BaseModel):
    titulo: str = Field(..., min_length=3, max_length=150)
    descripcion: str = Field(...)
    correo: EmailStr = Field(...)
    prioridad: Optional[PrioridadEnum] = Field(default=PrioridadEnum.MEDIA)
    asignar: Optional[str] = Field(default=None)
    imagenes: Optional[List[str]] = Field(default_factory=list)
    columna: Optional[int] = Field(default=1, ge=1, le=4)
    frecuencia: Optional[Frecuencia] = Field(default=None)
```

- **`titulo`**: Obligatorio, longitud entre 3 y 150 caracteres.
- **`correo`**: Obligatorio, formato RFC de correo electrónico válido.
- **`columna`**: Entero entre 1 y 4 (por defecto `1`).
- **`frecuencia`**: Submodelo `Frecuencia` opcional para tareas periódicas.

---

#### B. `TicketUpdate` (Entrada para Modificación Parcial)
Utilizado en `PATCH /api/v1/tickets/{id}`. Todos los campos son opcionales; solo se persisten aquellos enviados en el cuerpo JSON:

```python
class TicketUpdate(BaseModel):
    titulo: Optional[str] = Field(None, min_length=3, max_length=150)
    descripcion: Optional[str] = None
    correo: Optional[EmailStr] = None
    prioridad: Optional[PrioridadEnum] = None
    estado: Optional[EstadoEnum] = None
    asignar: Optional[str] = None
    imagenes: Optional[List[str]] = None
    columna: Optional[int] = Field(None, ge=1, le=4)
    leido: Optional[bool] = Field(None)
    frecuencia: Optional[Frecuencia] = Field(None)
```

---

#### C. `TicketFilter` (Filtros de Búsqueda y Paginación)
Estructura interna que agrupa los parámetros de consulta de `GET /api/v1/tickets/`:

```python
class TicketFilter(BaseModel):
    fecha_desde: Optional[Union[datetime, str]] = None
    fecha_hasta: Optional[Union[datetime, str]] = None
    estado: Optional[EstadoEnum] = None
    prioridad: Optional[PrioridadEnum] = None
    asignar: Optional[str] = None
    columna: Optional[int] = Field(None, ge=1, le=4)
    leido: Optional[bool] = Field(None)
```

---

#### D. `TicketResponse` (Contrato Canónico de Salida)
Esquema único devuelto por todos los endpoints de lectura, creación, actualización y eventos SSE (`nuevo_ticket`, `ticket_actualizado`):

```python
class TicketResponse(BaseModel):
    id: PydanticObjectId
    identificador: str
    titulo: str
    descripcion: str
    correo: EmailStr
    prioridad: PrioridadEnum
    estado: EstadoEnum
    asignar: Optional[str]
    imagenes: List[str]
    fecha_creacion: datetime
    fecha_edicion: Optional[datetime]
    columna: int = Field(default=1)
    leido: bool = Field(default=False)
    frecuencia: Optional[Frecuencia] = None

    @field_serializer("fecha_creacion", "fecha_edicion", when_used="json")
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
```

#### Características Clave de `TicketResponse`:
1. **`from_attributes=True`**: Permite inicializar el DTO directamente desde una instancia del Documento de Beanie (`TicketResponse.model_validate(saved_ticket)`).
2. **Serializador ISO UTC (`serialize_datetime`)**: Normaliza las fechas a formato estándar ISO con terminación `"Z"` (ej: `2026-08-31T18:24:39.123456Z`), evitando desajustes de zona horaria en clientes web.
3. **Mapeo de ObjectId**: Convierte el `_id` de MongoDB a un string serializable en el campo `id`.

---

## 🔄 Comparativa de Esquemas del Dominio

| Campo | `TicketCreate` | `TicketUpdate` | `TicketResponse` |
| :--- | :---: | :---: | :---: |
| `id` | ❌ *No permitido* | ❌ *No permitido* | ✅ *Obligatorio* |
| `identificador` | ❌ *Generado en backend* | ❌ *Inmutable* | ✅ *Obligatorio* |
| `titulo` | ✅ *Obligatorio (3-150)* | 🟡 *Opcional (3-150)* | ✅ *Obligatorio* |
| `descripcion` | ✅ *Obligatorio* | 🟡 *Opcional* | ✅ *Obligatorio* |
| `correo` | ✅ *Obligatorio (email)* | 🟡 *Opcional (email)* | ✅ *Obligatorio* |
| `prioridad` | 🟡 *Opcional (default: media)* | 🟡 *Opcional* | ✅ *Obligatorio* |
| `estado` | ❌ *Default abierto* | 🟡 *Opcional* | ✅ *Obligatorio* |
| `columna` | 🟡 *Opcional (default: 1)* | 🟡 *Opcional (1-4)* | ✅ *Obligatorio* |
| `leido` | ❌ *Default false* | 🟡 *Opcional* | ✅ *Obligatorio* |
| `frecuencia` | 🟡 *Opcional* | 🟡 *Opcional* | 🟡 *Nullable* |
| `imagenes` | 🟡 *Opcional* | 🟡 *Opcional* | ✅ *Obligatorio (`[]`)* |
| `fecha_creacion` | ❌ *Generado en backend* | ❌ *Inmutable* | ✅ *Obligatorio* |
| `fecha_edicion` | ❌ *No permitido* | ❌ *Actualizado en backend* | 🟡 *Nullable* |
