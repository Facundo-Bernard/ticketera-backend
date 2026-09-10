# 🧠 Capa Core (`src/core/`)

La capa **Core** contiene las herramientas fundamentales, utilidades transversales, gestores en memoria y excepciones de dominio del sistema de tickets. Provee lógica de bajo acoplamiento que es consumida principalmente por la capa de **Servicios** y los **Controladores** de la API.

---

## 📂 Estructura del Directorio

```text
src/core/
├── date_utils.py           # Utilidades para parseo y normalización flexible de fechas en UTC
├── exceptions.py           # Excepciones base de dominio (NotFoundException, BadRequestException)
├── sse_manager.py          # Gestor de difusión en tiempo real vía Server-Sent Events (SSE)
├── ticket_lock_manager.py  # Gestor de concurrencia y bloqueo de edición con TTL (Time-To-Live)
└── README.md               # Este documento de arquitectura y especificación técnica
```

---

## 📄 Descripción Detallada de Módulos

### 1. 🔒 `ticket_lock_manager.py` — Gestor de Concurrencia y Bloqueos

#### Propósito:
Evita colisiones cuando múltiples operadores intentan editar o eliminar simultáneamente el mismo ticket en el tablero Kanban. Implementa un candado exclusivo en memoria con **expiración automática (TTL)** para garantizar que un ticket nunca quede bloqueado indefinidamente si el usuario cierra la pestaña o pierde conexión.

#### Arquitectura:
- **Almacenamiento**: Diccionario interno en memoria `_locks: Dict[str, LockInfo]`.
- **TTL por Defecto**: `180 segundos` (3 minutos).
- **Patrón**: Singleton exportado como `ticket_lock_manager`.

#### Modelo de Datos (`LockInfo`):
```python
class LockInfo(BaseModel):
    ticket_id: str         # ID del ticket en string
    usuario: str           # Correo o identificador del operador
    expira_en: datetime    # Timestamp UTC en el que expira el candado
```

#### Métodos Principales:
| Método | Firma | Descripción |
| :--- | :--- | :--- |
| `is_locked` | `is_locked(ticket_id: str) -> Optional[LockInfo]` | Retorna la info del bloqueo si está activo y vigente; si ya expiró, lo purga automáticamente y retorna `None`. |
| `acquire_lock` | `acquire_lock(ticket_id: str, usuario: str) -> Tuple[bool, Optional[LockInfo]]` | Intenta adquirir el bloqueo. Si ya pertenece al mismo usuario, renueva el TTL y retorna `(True, new_lock)`. Si pertenece a otro operador activo, retorna `(False, current_lock)`. |
| `release_lock` | `release_lock(ticket_id: str, usuario: Optional[str] = None) -> bool` | Libera el bloqueo. Si se especifica `usuario`, valida que coincida con el poseedor actual antes de eliminarlo. |
| `clear` | `clear() -> None` | Limpia todos los candados en memoria (utilizado principalmente para suites de pruebas unitarias). |

#### Ejemplo de Uso en Servicios/Controladores:
```python
from ..core.ticket_lock_manager import ticket_lock_manager

# Adquirir bloqueo
success, lock_info = ticket_lock_manager.acquire_lock("66d34b...", "operador@coopya.com")
if not success:
    raise HTTPException(status_code=409, detail=f"Bloqueado por {lock_info.usuario}")

# Verificar si se puede eliminar
if ticket_lock_manager.is_locked("66d34b..."):
    raise HTTPException(status_code=409, detail="No se puede eliminar mientras esté en edición")

# Liberar bloqueo al guardar o cancelar
ticket_lock_manager.release_lock("66d34b...")
```

---

### 2. 📡 `sse_manager.py` — Gestor en Tiempo Real (Server-Sent Events)

#### Propósito:
Permite la comunicación unidireccional en tiempo real desde el backend hacia todos los clientes web conectados (navegadores de operadores) sin la sobrecarga ni complejidad de WebSockets o Socket.IO.

#### Arquitectura:
- **Canal**: Utiliza colas asíncronas nativas de Python (`asyncio.Queue`).
- **Escalabilidad Ligera**: Cada conexión activa a `GET /api/v1/tickets/stream` registra su propia cola. Al emitir un evento, se distribuye asíncronamente a todas las colas activas.
- **Patrón**: Singleton exportado como `sse_manager`.

#### Métodos Principales:
| Método | Firma | Descripción |
| :--- | :--- | :--- |
| `subscribe` | `async def subscribe() -> asyncio.Queue` | Crea una nueva cola `asyncio.Queue` y la registra en el conjunto de listeners activos. |
| `unsubscribe` | `def unsubscribe(queue: asyncio.Queue) -> None` | Desregistra la cola cuando el cliente cierra la conexión o se desconecta. |
| `broadcast` | `async def broadcast(event: str, data: Dict[str, Any]) -> None` | Difunde un mensaje a todas las colas conectadas con formato `{"event": event, "data": data}`. |

#### Eventos Estandarizados Emitidos:
- **`nuevo_ticket`**: Al crear un ticket (`POST /tickets/`).
- **`ticket_actualizado`**: Al modificar campos (`PATCH /tickets/{id}`), marcar como leído o alterar adjuntos.
- **`ticket_eliminado`**: Al borrar un ticket (`DELETE /tickets/{id}`).
- **`ticket_bloqueado`**: Al iniciar edición exclusiva (`POST /tickets/{id}/bloquear`).
- **`ticket_desbloqueado`**: Al guardar cambios o cancelar edición (`POST /tickets/{id}/desbloquear`).

#### Ejemplo de Uso:
```python
from ..core.sse_manager import sse_manager

# Difundir evento a todas las pantallas
await sse_manager.broadcast("ticket_actualizado", ticket_dict)
```

---

### 3. 🗓️ `date_utils.py` — Parseo y Normalización de Fechas

#### Propósito:
Ofrece una función robusta y flexible para parsear fechas de consulta provenientes de los query parameters (`fecha_desde` y `fecha_hasta`) en múltiples formatos y normalizarlas automáticamente con zona horaria **UTC**.

#### Formatos Soportados:
- **ISO 8601**: `2026-08-31`, `2026-08-31T14:30:00Z`, etc.
- **Formato Estándar**: `YYYY-MM-DD` o `YYYY/MM/DD`.
- **Formato Latino / Europeo**: `DD-MM-YYYY` o `DD/MM/YYYY`.
- **Formatos con Hora**: `YYYY-MM-DD HH:MM:SS`, `DD/MM/YYYY HH:MM`, etc.

#### Función Principal:
```python
def parse_date_filter(
    date_val: Optional[Union[str, datetime, date]], 
    is_end_date: bool = False
) -> Optional[datetime]
```

- **Si `is_end_date=False` (`fecha_desde`)**:
  Autocompleta automáticamente la hora al **primer microsegundo del día** (`00:00:00.000000 UTC`).
- **Si `is_end_date=True` (`fecha_hasta`)**:
  Autocompleta automáticamente la hora al **último microsegundo del día** (`23:59:59.999999 UTC`).

#### Ejemplo de Uso:
```python
from ..core.date_utils import parse_date_filter

# Convierte "15/08/2026" en 2026-08-15 00:00:00+00:00
desde_utc = parse_date_filter("15/08/2026", is_end_date=False)

# Convierte "2026-08-31" en 2026-08-31 23:59:59.999999+00:00
hasta_utc = parse_date_filter("2026-08-31", is_end_date=True)
```

---

### 4. ⚠️ `exceptions.py` — Excepciones de Dominio

#### Propósito:
Define excepciones semánticas propias del negocio, desacopladas del protocolo HTTP de FastAPI.

```python
class NotFoundException(Exception):
    def __init__(self, message: str):
        self.message = message

class BadRequestException(Exception):
    def __init__(self, message: str):
        self.message = message
```

#### Manejo Centralizado en `src/main.py`:
FastAPI intercepta estas excepciones a través de decoradores `@app.exception_handler`:
- `NotFoundException` → Respuesta JSON con código **`404 Not Found`**:
  ```json
  { "error": "Not Found", "message": "Ticket con id ... no encontrado" }
  ```
- `BadRequestException` → Respuesta JSON con código **`400 Bad Request`**:
  ```json
  { "error": "Bad Request", "message": "Formato de frecuencia inválido: ..." }
  ```
