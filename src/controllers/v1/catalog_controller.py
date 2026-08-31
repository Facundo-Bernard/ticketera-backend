from fastapi import APIRouter, Depends
from typing import List
from ...schemas.catalog_schema import OptionItem, AsignableItem
from ...services.catalog_service import CatalogService

router = APIRouter(prefix="/catalogs", tags=["Catálogos"])

@router.get("/estados", response_model=List[OptionItem], summary="Obtener lista de estados válidos de tickets")
def get_estados(service: CatalogService = Depends()):
    return service.get_estados()

@router.get("/prioridades", response_model=List[OptionItem], summary="Obtener lista de prioridades válidas de tickets")
def get_prioridades(service: CatalogService = Depends()):
    return service.get_prioridades()

@router.get("/asignables", response_model=List[AsignableItem], summary="Obtener lista de técnicos/áreas asignables")
async def get_asignables(service: CatalogService = Depends()):
    return await service.get_asignables()
