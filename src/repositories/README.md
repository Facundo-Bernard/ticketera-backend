# 🗄️ Capa de Repositorios (`src/repositories/`)

La capa de **Repositorios** implementa el **Patrón Repositorio (*Repository Pattern*)**, aislando por completo la capa de servicios de los detalles de acceso a la base de datos **MongoDB** y la sintaxis del ODM **Beanie**.

---

## 📂 Estructura del Directorio

```text
src/repositories/
├── base_repository.py      # Repositorio genérico con operaciones CRUD reutilizables
├── ticket_repository.py    # Repositorio especializado para el modelo Ticket y consultas avanzadas
└── README.md               # Este documento de arquitectura y especificación técnica
```

---

## 🎯 Objetivos y Principios de Diseño

1. **Abstracción de Persistencia**: La capa de servicios (`src/services/`) desconoce si los datos provienen de MongoDB, memoria o un motor relacional. Consume métodos limpios como `.get(id)`, `.get_all()`, `.update()`, etc.
2. **Reutilización mediante Genéricos**: `BaseRepository` utiliza tipos genéricos de Python (`typing.Generic` y `TypeVar`), permitiendo que cualquier nuevo modelo herede automáticamente operaciones CRUD completas y tipadas.
3. **Optimización de Consultas**: Centraliza la construcción de queries BSON de MongoDB, proyecciones, ordenamientos e indexaciones.

---

## 📄 Descripción Detallada de Módulos

### 1. 🧱 `base_repository.py` — Repositorio Genérico Base

Define la clase abstracta genérica:

```python
class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model
```

Donde:
- `ModelType` está acotado a un Documento de Beanie (`bound=Document`).
- `CreateSchemaType` y `UpdateSchemaType` están acotados a modelos Pydantic (`bound=BaseModel`).

#### Métodos CRUD Disponibles:

| Método | Firma | Descripción |
| :--- | :--- | :--- |
| `get` | `async def get(id: PydanticObjectId) -> Optional[ModelType]` | Busca un documento por su `_id` de MongoDB. Retorna `None` si no existe. |
| `get_all` | `async def get_all(skip: int = 0, limit: int = 100) -> List[ModelType]` | Obtiene una lista paginada de todos los documentos de la colección. |
| `create` | `async def create(obj_in: CreateSchemaType) -> ModelType` | Instancia el modelo con `obj_in.model_dump()` y lo inserta en MongoDB. |
| `count` | `async def count() -> int` | Retorna la cantidad total de documentos en la colección. |
| `update` | `async def update(id: PydanticObjectId, obj_in: UpdateSchemaType) -> Optional[ModelType]` | Aplica cambios parciales excluyendo campos no enviados (`exclude_unset=True`) y actualiza automáticamente `fecha_edicion` en UTC. |
| `delete` | `async def delete(id: PydanticObjectId) -> bool` | Elimina el documento físicamente de MongoDB. Retorna `True` si se eliminó, `False` si no se encontró. |

---

### 2. 🎫 `ticket_repository.py` — Repositorio de Tickets

Especializa a `BaseRepository` para la entidad `Ticket`:

```python
class TicketRepository(BaseRepository[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(model=Ticket)
```

Hereda todos los métodos CRUD de `BaseRepository` y añade el motor de búsqueda y filtrado dinámico para la API:

#### Método `get_filtered`:
```python
async def get_filtered(
    self,
    filters: Dict[str, Any],
    skip: int = 0,
    limit: int = 100
) -> List[Ticket]
```

#### Capacidades del Query Builder Dinámico:
1. **Filtro por Estado (`estado`)**: Búsqueda exacta (`"abierto"`, `"en_progreso"`, `"resuelto"`, `"cerrado"`).
2. **Filtro por Prioridad (`prioridad`)**: Búsqueda exacta (`"baja"`, `"media"`, `"alta"`, `"critica"`).
3. **Filtro por Columna (`columna`)**: Coincidencia exacta de ID numérico (`1, 2, 3, 4`).
4. **Filtro por Estado de Lectura (`leido`)**: Booleano (`true` o `false`). Permite listar únicamente tickets nuevos pendientes de revisión.
5. **Búsqueda Parcial de Responsable (`asignar`)**: Utiliza `$regex` insensible a mayúsculas/minúsculas (`$options: "i"`). Por ejemplo, `"facundo"` encuentra `"Facundo Bernard"`.
6. **Rango de Fechas Inteligente (`fecha_desde` y `fecha_hasta`)**:
   - Integra `parse_date_filter` del Core.
   - Aplica `$gte` (mayor o igual a las `00:00:00.000000 UTC` de `fecha_desde`).
   - Aplica `$lte` (menor o igual a las `23:59:59.999999 UTC` de `fecha_hasta`).
7. **Ordenamiento**: Aplica `.sort("-fecha_creacion")` para que las tarjetas más recientes siempre aparezcan en la parte superior del tablero.
8. **Paginación Eficiente**: Aplica `.skip(skip).limit(limit)` a nivel de base de datos antes de materializar la lista en memoria.

---

## 💡 Inyección de Dependencias en FastAPI

`TicketRepository` se inyecta de forma limpia y transparente en la capa de Servicios a través del sistema de dependencias de FastAPI (`Depends`):

```python
class TicketService:
    def __init__(
        self,
        repository: TicketRepository = Depends(),
        rate_limit_service: RateLimitService = Depends()
    ):
        self.repository = repository
        self.rate_limit_service = rate_limit_service
```

Esto facilita el reemplazo por repositorios mock en pruebas unitarias sin necesidad de levantar bases de datos reales.
