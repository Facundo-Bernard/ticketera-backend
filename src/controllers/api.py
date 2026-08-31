from fastapi import APIRouter
from .v1 import ticket_controller, file_controller, catalog_controller

router = APIRouter(prefix="/api/v1")

router.include_router(ticket_controller.router)
router.include_router(file_controller.router)
router.include_router(catalog_controller.router)
