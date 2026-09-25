from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager

from .config.settings import settings
from .config.database import init_db
from .models.ticket_model import Ticket
from .modules.comments.model import CommentBucket
from .modules.candidatos.model import Candidato
from .modules.auth import User, seed_default_admin
from .modules.notifications import PushSubscription
from .controllers import api, health_controller
from .core.exceptions import NotFoundException, BadRequestException, UnauthorizedException, ForbiddenException

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db([Ticket, CommentBucket, Candidato, User, PushSubscription])
    await seed_default_admin()
    yield
    # Shutdown
    pass

app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version="1.0.0",
        description="API para Sistema de Tickets",
        routes=app.routes,
    )
    # Normalizar campos de archivos para que Swagger UI renderice el selector de archivos
    def fix_binary_format(d):
        if isinstance(d, dict):
            if d.get("contentMediaType") == "application/octet-stream":
                d["format"] = "binary"
                del d["contentMediaType"]
            for v in d.values():
                fix_binary_format(v)
        elif isinstance(d, list):
            for item in d:
                fix_binary_format(item)

    fix_binary_format(openapi_schema)
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Type", "Content-Length"],
)

# Exception Handlers
@app.exception_handler(NotFoundException)
async def not_found_exception_handler(request: Request, exc: NotFoundException):
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "message": exc.message},
    )

@app.exception_handler(BadRequestException)
async def bad_request_exception_handler(request: Request, exc: BadRequestException):
    return JSONResponse(
        status_code=400,
        content={"error": "Bad Request", "message": exc.message},
    )

@app.exception_handler(UnauthorizedException)
async def unauthorized_exception_handler(request: Request, exc: UnauthorizedException):
    return JSONResponse(
        status_code=401,
        content={"error": "Unauthorized", "message": exc.message},
        headers={"WWW-Authenticate": "Bearer"},
    )

@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(request: Request, exc: ForbiddenException):
    return JSONResponse(
        status_code=403,
        content={"error": "Forbidden", "message": exc.message},
    )

# Routers
app.include_router(health_controller.router)
app.include_router(api.router)

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse("index.html")
