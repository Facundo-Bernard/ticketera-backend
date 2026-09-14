# ⚙️ Capa de Servicios (`src/services/`)

La capa de **Servicios** concentra la **Lógica de Negocio**, reglas de dominio, orquestación transaccional con **Rollback automático**, almacenamiento binario en streams y políticas de seguridad y cuotas de la aplicación.

---

## 📂 Estructura y Dominios Lógicos

Dada la envergadura y criticidad de las operaciones, la capa de servicios se divide en **4 Dominios Lógicos**:

```text
src/services/
├── ticket_service.py       # [DOMINIO 1] Ciclo de Vida de Tickets & Orquestación con Rollback
├── gridfs_service.py       # [DOMINIO 2] Almacenamiento Binario en Streams (MongoDB GridFS)
├── rate_limit_service.py   # [DOMINIO 3] Seguridad, Anti-Spam y Cuotas por Correo
├── catalog_service.py      # [DOMINIO 4] Catálogos y Metadatos del Sistema
└── README.md               # Este documento de arquitectura y especificación técnica
```

---

## 🗺️ Mapa de Interacción y Dependencias

```mermaid
graph TD
    Controller[Controlador / API Endpoint] --> TicketService[TicketService (Orquestador)]
    TicketService --> RateLimit[RateLimitService]
    TicketService --> GridFS[GridFSService]
    TicketService --> Repo[TicketRepository]
    TicketService --> SSE[SSEManager]
    TicketService --> LockMgr[TicketLockManager]
    Controller --> CatalogService[CatalogService]
```

---

## 🎫 DOMINIO 1: Ciclo de Vida de Tickets & Orquestación con Rollback (`ticket_service.py`)

Es el servicio orquestador principal. Coordina la base de datos documental, el almacenamiento binario de archivos, la seguridad anti-spam, los bloqueos concurrentes y las transmisiones en tiempo real.

### 1. Inyección de Dependencias
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

---

### 2. Generador Atómico de Identificadores (`_generate_next_identifier`)
Genera correlativos legibles únicos (ej: `"TCK-1001"`, `"TCK-1002"`) de forma 100% atómica y thread-safe.

- **Mecanismo**: Utiliza la colección dedicada `counters` en MongoDB mediante el comando `find_one_and_update` con `$inc: {"seq": 1}` y `return_document=ReturnDocument.AFTER`.
- **Auto-Sincronización**: En el primer arranque, inspecciona si ya existen tickets en la base de datos para arrancar desde el número más alto existente o desde `1000`.
- **Inmunidad ante Eliminaciones**: Si se elimina el ticket `TCK-1005`, el siguiente ticket creado será `TCK-1006`. Nunca hay reciclaje de códigos ni colisiones por condiciones de carrera concurrentes.

---

### 3. Creación Compuesta con Rollback Automático (`create_ticket_with_rollback`)
Orquesta la subida física de imágenes a GridFS junto a la inserción del documento en MongoDB bajo una transacción lógica con rollback garantizado:

```text
[Cliente] POST /api/v1/tickets/ (FormData: texto + imágenes)
   │
   ├─► 1. RateLimitService: Valida cuota diaria y cooldown (Lanza 400 si supera límite)
   │
   ├─► 2. GridFSService: Sube cada imagen física a GridFS y recolecta sus ObjectIDs
   │
   ├─► 3. TicketService: Genera 'TCK-XXXX' e inserta documento Ticket en MongoDB
   │
   ├─► 4. SSEManager: Transmite evento 'nuevo_ticket' a todas las pantallas activas
   │
   ▼
[ÉXITO: 201 Created]

   └──► [SI OCURRE ERROR EN CUALQUIER PUNTO]:
           ├── Purga física de todas las fotos subidas a GridFS en este intento
           ├── Borrado del documento Ticket si llegó a crearse en MongoDB
           └── Re-lanza la excepción original hacia el cliente
```

---

### 4. Actualización Parcial (`update_ticket`)
- Actualiza campos con `TicketUpdate` (excluyendo campos no enviados).
- **Liberación de Candado**: Si el ticket estaba en edición exclusiva, libera automáticamente el lock en `TicketLockManager`.
- **Broadcasting Dual**: Emite `ticket_actualizado` con el nuevo estado del ticket y `ticket_desbloqueado` a todas las pantallas.

---

### 5. Lectura y Visualización (`mark_as_read`)
- Cambia el flag `ticket.leido = True`.
- Emite el evento `ticket_actualizado` para que todos los operadores conectados vean que el badge `"NUEVO"` desaparece en tiempo real sin recargar.

---

### 6. Eliminación Segura y Protección Concurrente (`delete_ticket`)
- **Barrera de Seguridad**: Antes de borrar nada, consulta `ticket_lock_manager.is_locked(str(id))`. Si otro operador lo está editando, **aborta arrojando `HTTP 409 Conflict`** con el nombre del editor en la cabecera `X-Locked-By`.
- **Limpieza en Cascada**: Si no está bloqueado, itera sobre `ticket.imagenes`, extrae los IDs de GridFS y los elimina físicamente del bucket.
- **Borrado en MongoDB**: Elimina el documento de la colección.
- **Difusión SSE**: Emite `ticket_eliminado` con `{ "id": ..., "identificador": ... }`.

---

### 7. Gestión Granular de Imágenes (`add_images_to_ticket` y `remove_image_from_ticket`)
- Permite anexar fotos posteriores o eliminar fotos individuales.
- Al eliminar una foto, no solo la quita del array `imagenes` del ticket, sino que purga físicamente el binario de GridFS para evitar archivos huérfanos.
- Emite `ticket_actualizado` para reflejar las nuevas fotos en el visor.

---

## 🖼️ DOMINIO 2: Almacenamiento Binario en Streams (`gridfs_service.py`)

Gestiona el almacenamiento binario no estructurado en **MongoDB GridFS**, superando el límite de 16 MB por documento BSON al dividir los archivos en fragmentos (*chunks*) de 255 KB.

### 1. Bucket Asíncrono (`AsyncIOMotorGridFSBucket`)
Inicializa de forma diferida (*lazy loading*) un bucket conectado a la base de datos de MongoDB:
```python
db = self._client[settings.MONGO_DB_NAME]
self._bucket = AsyncIOMotorGridFSBucket(db)
```

### 2. Validación Rigurosa de Archivos (`_validate_file`)
Garantiza que solo se suban formatos válidos de imágenes y documentos:
- **Imágenes Permitidas**: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.avif`, `.bmp`, `.svg`.
- **Documentos Permitidos**:
  - **PDF**: `.pdf` (`application/pdf`)
  - **CSV**: `.csv` (`text/csv`, `application/csv`)
  - **Excel**: `.xlsx`, `.xls` (`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/vnd.ms-excel`)
  - **Texto**: `.txt` (`text/plain`)
- **Límite de Tamaño**: Máximo **25 MB** por archivo.
- **Detección Inteligente**: Si el cliente envía `application/octet-stream`, infiere el content-type real mediante `MIME_BY_EXTENSION` y `mimetypes.guess_type`.
- Si el formato no es válido o supera el límite de 25 MB, arroja `BadRequestException` (`400 Bad Request`).

### 3. Operaciones Principales:
| Método | Firma | Descripción |
| :--- | :--- | :--- |
| `upload_file` | `async def upload_file(file: UploadFile) -> str` | Abre un stream de subida asíncrono (`open_upload_stream`), escribe los bytes y retorna el `ObjectId` en string. |
| `upload_files` | `async def upload_files(files: List[UploadFile]) -> List[str]` | Sube una lista de archivos y retorna el listado de IDs generados. |
| `get_file_stream` | `async def get_file_stream(file_id: str) -> Tuple[AsyncIOMotorGridOut, str, str]` | Abre un stream de descarga (`open_download_stream`) sin cargar todo el archivo en la memoria RAM del servidor. Retorna el stream, el content-type y el nombre del archivo. |
| `delete_file` | `async def delete_file(file_id: str) -> None` | Elimina permanentemente el archivo y todos sus chunks asociados en `fs.files` y `fs.chunks`. |

---

## 🛡️ DOMINIO 3: Seguridad, Anti-Spam y Cuotas (`rate_limit_service.py`)

Protege la API de ataques de denegación de servicio (DoS), saturación de almacenamiento y spam por correos automatizados.

### Políticas de Seguridad Implementadas:

```python
class RateLimitService:
    def __init__(self):
        self.max_daily_tickets: int = settings.MAX_DAILY_TICKETS_PER_EMAIL       # Default: 8
        self.cooldown_seconds: int = settings.TICKET_CREATION_COOLDOWN_SECONDS   # Default: 60s
```

#### A. Whitelist de Administradores (`ADMIN_EMAILS`)
Los correos configurados en la variable `ADMIN_EMAILS` del entorno (ej: `nmonticoopya@gmail.com`, `nfernandezcoopya@gmail.com`, `fbernard@coopya.com.ar`):
- Quedan **100% exentos** de todas las validaciones de rate limit.
- Pueden crear tickets ilimitados sin esperar cooldown.

#### B. Cooldown Anti-Spam (60 Segundos)
- Busca el último ticket creado por el correo solicitante.
- Si la diferencia de tiempo respecto a `datetime.now(timezone.utc)` es menor a `60 segundos`, rechaza la solicitud con `BadRequestException`:
  > *"Por favor espera X segundos antes de enviar otro ticket (Anti-Spam)."*

#### C. Límite Diario en Ventana Móvil (8 Tickets / 24 Horas)
- Cuenta cuántos tickets ha registrado el correo en la ventana de tiempo móvil `[ahora - 24 horas, ahora]`.
- Si el conteo es `>= 8`, bloquea la creación arrojando `BadRequestException`:
  > *"Has alcanzado el límite máximo diario de 8 tickets para el correo '...'."*

---

## 🧱 DOMINIO 4: Catálogos y Opciones Estáticas (`catalog_service.py`)

Provee las listas de opciones estándar en formato `OptionItem` (`value` y `label`) para alimentar directamente los componentes de selección del frontend.

### Métodos Disponibles:

#### 1. `get_estados() -> List[OptionItem]`
Mapea los valores técnicos de `EstadoEnum` a etiquetas amigables:
- `abierto` → `"Abierto"`
- `en_progreso` → `"En Progreso"`
- `resuelto` → `"Resuelto"`
- `cerrado` → `"Cerrado"`

#### 2. `get_prioridades() -> List[OptionItem]`
Mapea `PrioridadEnum`:
- `baja` → `"Baja"`
- `media` → `"Media"`
- `alta` → `"Alta"`
- `critica` → `"Crítica"`

#### 3. `get_asignables() -> List[OptionItem]`
Lista los técnicos oficiales de la mesa de soporte para asignación:
```json
[
  { "value": "facundo_bernard", "label": "Facundo Bernard" },
  { "value": "nicolas_fernandez", "label": "Nicolas Fernandez" },
  { "value": "nahuel_monti", "label": "Nahuel Monti" }
]
```
