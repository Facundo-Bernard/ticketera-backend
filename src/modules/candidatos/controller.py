from typing import List
from fastapi import APIRouter, Depends, Query, status
from beanie import PydanticObjectId
from .schemas import CandidatoCreate, CandidatoResponse
from .service import CandidatoService
from ..auth import get_current_user, User

router = APIRouter(prefix="/candidatos", tags=["Candidatos (Puente Temporal)"])

@router.post(
    "",
    response_model=CandidatoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo candidato (Público)"
)
async def create_candidato(
    candidato_in: CandidatoCreate,
    service: CandidatoService = Depends()
):
    """
    Registra los datos personales, laborales y producto crediticio de un candidato postulante.
    Endpoint público disponible para formularios web y landing pages.
    Retorna el documento persistido con su ID único generado.
    """
    return await service.register_candidato(candidato_in)

@router.get(
    "/{id}",
    response_model=CandidatoResponse,
    summary="Obtener un candidato por ID (Dashboard)"
)
async def get_candidato(
    id: PydanticObjectId,
    service: CandidatoService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Busca y retorna la información de un candidato a partir de su ID de MongoDB.
    Requiere autenticación de operador o administrador (Bearer Token).
    """
    return await service.get_candidato(id)

@router.get(
    "",
    response_model=List[CandidatoResponse],
    summary="Listar candidatos registrados (Dashboard)"
)
async def list_candidatos(
    skip: int = Query(0, ge=0, description="Registros a omitir para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de candidatos a retornar"),
    service: CandidatoService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Retorna el listado de candidatos registrados en el sistema ordenados por fecha de creación descendente.
    Requiere autenticación de operador o administrador (Bearer Token).
    """
    return await service.list_candidatos(skip=skip, limit=limit)

@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un candidato por ID (Dashboard)"
)
async def delete_candidato(
    id: PydanticObjectId,
    service: CandidatoService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Elimina un candidato registrado a partir de su ID de MongoDB.
    Requiere autenticación de operador o administrador (Bearer Token).
    """
    await service.delete_candidato(id)

