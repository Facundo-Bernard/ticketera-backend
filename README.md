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

## 📌 Catálogo de Endpoints API (`/api/v1`)

### Tickets (`/api/v1/tickets`)
- **`POST /api/v1/tickets/`**: Crear ticket (acepta texto + múltiples imágenes opcionales con **Rollback automático en Backend** si algo falla).
- **`GET /api/v1/tickets/`**: Listar tickets con filtros opcionales (`fecha_desde`, `fecha_hasta`, `estado`, `prioridad`, `asignar`, `skip`, `limit`).
- **`GET /api/v1/tickets/{id}`**: Obtener el detalle de un ticket por ID.
- **`PATCH /api/v1/tickets/{id}`**: Actualización parcial de campos de texto en JSON.
- **`DELETE /api/v1/tickets/{id}`**: Eliminar ticket y **todas sus imágenes asociadas de GridFS en cascada**.
- **`POST /api/v1/tickets/{id}/images`**: Adjuntar imágenes adicionales a un ticket existente.
- **`DELETE /api/v1/tickets/{id}/images/{file_id}`**: Eliminar una imagen puntual del ticket y borrarla de GridFS.

### Archivos (`/api/v1/files`)
- **`GET /api/v1/files/{file_id}`**: Stream binario y descarga/visualización de imágenes desde GridFS.

---

## 🧪 Ejecución de Pruebas Automatizadas

Para correr toda la suite de pruebas unitarias y de integración:
```bash
pytest -v
```
