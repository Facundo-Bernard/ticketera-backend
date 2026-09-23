from .model import Candidato, ProductoSeleccionado
from .schemas import CandidatoCreate, CandidatoResponse, ProductoSeleccionadoSchema
from .repository import CandidatoRepository
from .service import CandidatoService
from .controller import router as candidatos_router

__all__ = [
    "Candidato",
    "ProductoSeleccionado",
    "CandidatoCreate",
    "CandidatoResponse",
    "ProductoSeleccionadoSchema",
    "CandidatoRepository",
    "CandidatoService",
    "candidatos_router"
]
