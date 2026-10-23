import re
from typing import List, Dict, Any, Tuple
from .base_repository import BaseRepository
from ..models.ticket_model import Ticket
from ..schemas.ticket_schema import TicketCreate, TicketUpdate
from ..core.date_utils import parse_date_filter


class TicketRepository(BaseRepository[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(model=Ticket)

    def _build_query(self, filters: Dict[str, Any]) -> dict:
        """Construye el query MongoDB a partir del diccionario de filtros."""
        query = {}

        if filters.get("estado"):
            if isinstance(filters["estado"], list):
                query["estado"] = {"$in": filters["estado"]}
            else:
                query["estado"] = filters["estado"]
        elif filters.get("estado_excluir"):
            # Excluir estados especificos (ej: resuelto, cerrado para el tablero activo)
            query["estado"] = {"$nin": filters["estado_excluir"]}

        if filters.get("prioridad"):
            query["prioridad"] = filters["prioridad"]

        if filters.get("columna"):
            query["columna"] = filters["columna"]

        if "leido" in filters and filters["leido"] is not None:
            query["leido"] = filters["leido"]

        if filters.get("asignar"):
            safe_asignar = re.escape(str(filters["asignar"]).strip())
            query["asignar"] = {"$regex": safe_asignar, "$options": "i"}

        # Filtro de busqueda libre por titulo o descripcion (escapado contra ReDoS)
        if filters.get("q"):
            safe_q = re.escape(str(filters["q"]).strip())
            query["$or"] = [
                {"titulo": {"$regex": safe_q, "$options": "i"}},
                {"descripcion": {"$regex": safe_q, "$options": "i"}},
            ]

        fecha_desde_parsed = parse_date_filter(filters.get("fecha_desde"), is_end_date=False)
        fecha_hasta_parsed = parse_date_filter(filters.get("fecha_hasta"), is_end_date=True)

        if fecha_desde_parsed or fecha_hasta_parsed:
            fecha_query = {}
            if fecha_desde_parsed:
                fecha_query["$gte"] = fecha_desde_parsed
            if fecha_hasta_parsed:
                fecha_query["$lte"] = fecha_hasta_parsed
            query["fecha_creacion"] = fecha_query

        return query

    async def get_filtered(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 50,
    ) -> List[Ticket]:
        query = self._build_query(filters)
        return await self.model.find(query).sort("-fecha_creacion").skip(skip).limit(limit).to_list()

    async def count_filtered(self, filters: Dict[str, Any]) -> int:
        """Cuenta los documentos que coinciden con los filtros (sin paginacion)."""
        query = self._build_query(filters)
        return await self.model.find(query).count()

    async def get_paged(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[int, List[Ticket]]:
        """Devuelve (total, items) ordenados del mas reciente al mas antiguo."""
        query = self._build_query(filters)
        base = self.model.find(query)
        total = await base.count()
        items = await base.sort("-fecha_creacion").skip(skip).limit(limit).to_list()
        return total, items
