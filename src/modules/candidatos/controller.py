from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Form, File, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from beanie import PydanticObjectId
from ...core.exceptions import BadRequestException
from .schemas import CandidatoCreate, CandidatoResponse
from .service import CandidatoService
from ..auth import get_current_user, User

router = APIRouter(prefix="/candidatos", tags=["Candidatos (Puente Temporal)"])

EXAMPLE_CANDIDATO_JSON = (
    '{\n'
    '  "nombreCompleto": "María González",\n'
    '  "dni": "30123456",\n'
    '  "email": "maria@email.com",\n'
    '  "telefono": "+54 11 5555-5555",\n'
    '  "direccion": "Av. Corrientes 1234, CABA",\n'
    '  "genero": "female",\n'
    '  "edad": 42,\n'
    '  "situacionLaboral": "graciable",\n'
    '  "ingresoMensual": 400000,\n'
    '  "moneda": "ARS",\n'
    '  "bancosSeleccionados": ["nacion", "provincia"],\n'
    '  "productoSeleccionado": {\n'
    '    "familia": "Asistodo",\n'
    '    "plan": "1",\n'
    '    "monto": 400000,\n'
    '    "plazoMeses": 12\n'
    '  },\n'
    '  "origen": "web"\n'
    '}'
)

@router.post(
    "",
    response_model=CandidatoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo candidato con papelería opcional (Público)"
)
@router.post(
    "/",
    response_model=CandidatoResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
async def create_candidato(
    data: str = Form(
        ...,
        description="JSON string con los datos personales y crediticios del candidato",
        examples=[EXAMPLE_CANDIDATO_JSON]
    ),
    papeleria: Optional[UploadFile] = File(
        None,
        description="Archivo de papelería en formato PDF o imagen (máx 25 MB)"
    ),
    service: CandidatoService = Depends()
):
    """
    Registra los datos de un candidato y, opcionalmente, almacena su archivo de papelería en GridFS
    bajo el bucket exclusivo 'candidatos_papeleria'.
    Endpoint público disponible para formularios web y landing pages.
    """
    try:
        candidato_in = CandidatoCreate.model_validate_json(data)
    except ValidationError as e:
        raise RequestValidationError(e.errors())
    except Exception as e:
        raise BadRequestException(f"El campo 'data' contiene un JSON con formato inválido: {str(e)}")

    return await service.register_candidato(candidato_in, papeleria)

@router.get(
    "/papeleria/{file_id}",
    summary="Descargar o previsualizar un archivo de papelería por su File ID (Dashboard)"
)
async def get_candidato_papeleria(
    file_id: str,
    service: CandidatoService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Descarga o previsualiza inline en el navegador el archivo de papelería (PDF o imagen)
    almacenado en GridFS bajo el bucket 'candidatos_papeleria' a partir de su file_id único.
    Requiere autenticación con Bearer Token.
    """
    grid_out, content_type, filename = await service.get_papeleria_stream(file_id)
    return StreamingResponse(
        grid_out,
        media_type=content_type,
        headers={
            "Content-Disposition": f'inline; filename="{filename}"'
        }
    )

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
@router.get(
    "/",
    response_model=List[CandidatoResponse],
    include_in_schema=False
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
    Elimina un candidato registrado a partir de su ID de MongoDB y purga en cascada
    su papelería en GridFS (bucket 'candidatos_papeleria').
    Requiere autenticación de operador o administrador (Bearer Token).
    """
    await service.delete_candidato(id)
