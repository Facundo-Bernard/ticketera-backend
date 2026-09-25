from fastapi import APIRouter
from .v1 import ticket_controller, file_controller, catalog_controller
from ..modules.comments import comments_router
from ..modules.candidatos import candidatos_router
from ..modules.auth import auth_router
from ..modules.notifications import notifications_router

router = APIRouter(prefix="/api/v1")

router.include_router(ticket_controller.router)
router.include_router(file_controller.router)
router.include_router(catalog_controller.router)
router.include_router(comments_router)
router.include_router(candidatos_router)
router.include_router(auth_router)
router.include_router(notifications_router)

