# Módulo de Autenticación (`src/modules/auth`)

Módulo autónomo (*Package by Feature*) responsable de la gestión de usuarios, seguridad de contraseñas y emisión/validación de **JSON Web Tokens (JWT)** para la API de **Coopya Sistemas**.

---

## 1. Responsabilidad y Arquitectura

- **Colección dedicada en MongoDB**: `usuarios`.
- **Criptografía**: Hashing seguro mediante `bcrypt` con salt aleatorio.
- **Firma de Tokens**: Tokens JWT con algoritmo `HS256` y expiración configurable (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Autenticación Stateless**: Los endpoints protegidos validan la firma criptográfica del encabezado HTTP `Authorization: Bearer <token>`.
- **Control de Roles**: Soporte nativo para roles (`operador` y `admin`).

---

## 2. Estructura de Archivos

```text
src/modules/auth/
├── __init__.py           # Exportaciones del módulo (User, auth_router, dependencies)
├── model.py              # Documento Beanie: User (colección 'usuarios')
├── schemas.py            # Esquemas Pydantic: UserRegister, UserLogin, UserResponse, TokenResponse
├── repository.py         # Repositorio de usuarios con métodos por email
├── service.py            # Lógica de registro, verificación de credenciales y generación de JWT
├── security.py           # Utilidades criptográficas (bcrypt y PyJWT)
├── dependencies.py       # Dependencias FastAPI: get_current_user y get_current_admin
├── controller.py         # Endpoints FastAPI (/api/v1/auth)
└── README.md             # Esta documentación
```

---

## 3. Endpoints de la API

Montados bajo `/api/v1/auth`:

| Método | Endpoint | Estado HTTP | Auth Requerida | Descripción |
| :--- | :--- | :---: | :---: | :--- |
| `POST` | `/api/v1/auth/login` | `200 OK` | No | Autentica con email y contraseña, retornando el Bearer JWT y perfil. |
| `GET` | `/api/v1/auth/me` | `200 OK` | **Bearer Token** | Retorna los datos del usuario logueado actualmente. |
| *(POST)* | *(`/api/v1/auth/register`)* | - | - | *(Deshabilitado/comentado temporalmente)* |

---

## 4. Ejemplos de Peticiones

### A. Inicio de Sesión (`POST /api/v1/auth/login`)

```json
{
  "email": "operador@coopya.com",
  "password": "Password123!"
}
```

**Respuesta (`200 OK`):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": "66f1234567890abcdef12345",
    "email": "operador@coopya.com",
    "nombre": "Juan Pérez",
    "rol": "operador",
    "activo": true,
    "fechaCreacion": "2026-09-23T10:00:00Z",
    "ultimoLogin": "2026-09-23T10:30:00Z"
  }
}
```

### B. Consumo de Endpoints Protegidos en Frontend / Dashboard

En cada petición a endpoints protegidos (como `GET /api/v1/candidatos` o `DELETE /api/v1/candidatos/{id}`), enviar el encabezado:

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## 5. Usuario Inicial y Expiración Prolongada

- **Usuario Administrador Genérico**: Se crea automáticamente al iniciar la API si no existe (idempotente):
  - **Email:** `admin@coopya.com`
  - **Contraseña:** `admin`
  - **Rol:** `admin`
- **Expiración de Tokens:** Configurada por defecto a **1 año** (`365 días` / `525.600 minutos`) en `settings.ACCESS_TOKEN_EXPIRE_MINUTES` para facilitar sesiones prolongadas en el dashboard administrativo sin necesidad de re-autenticación constante.
