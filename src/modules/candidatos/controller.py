from typing import List
from fastapi import APIRouter, Depends, Query, status
from beanie import PydanticObjectId
from .schemas import CandidatoCreate, CandidatoResponse
from .service import CandidatoService

router = APIRouter(prefix="/candidatos", tags=["Candidatos (Puente Temporal)"])

@router.post(
    "",
    response_model=CandidatoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo candidato"
)
async def create_candidato(
    candidato_in: CandidatoCreate,
    service: CandidatoService = Depends()
):
    """
    Registra los datos personales, laborales y producto crediticio de un candidato postulante.
    Retorna el documento persistido con su ID único generado.
    """
    return await service.register_candidato(candidato_in)

@router.get(
    "/{id}",
    response_model=CandidatoResponse,
    summary="Obtener un candidato por ID"
)
async def get_candidato(
    id: PydanticObjectId,
    service: CandidatoService = Depends()
):
    """
    Busca y retorna la información de un candidato a partir de su ID de MongoDB.
    """
    return await service.get_candidato(id)

@router.get(
    "",
    response_model=List[CandidatoResponse],
    summary="Listar candidatos registrados"
)
async def list_candidatos(
    skip: int = Query(0, ge=0, description="Registros a omitir para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de candidatos a retornar"),
    service: CandidatoService = Depends()
):
    """
    Retorna el listado de candidatos registrados en el sistema ordenados por fecha de creación descendente.
    """
    return await service.list_candidatos(skip=skip, limit=limit)
