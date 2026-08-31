from typing import List, Dict, Any
from .base_repository import BaseRepository
from ..models.ticket_model import Ticket
from ..schemas.ticket_schema import TicketCreate, TicketUpdate

class TicketRepository(BaseRepository[Ticket, TicketCreate, TicketUpdate]):
    def __init__(self):
        super().__init__(model=Ticket)

    async def get_filtered(
        self,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[Ticket]:
        query = {}
        
        if filters.get("estado"):
            query["estado"] = filters["estado"]
            
        if filters.get("prioridad"):
            query["prioridad"] = filters["prioridad"]
            
        if filters.get("asignar"):
            query["asignar"] = {"$regex": filters["asignar"], "$options": "i"}
            
        fecha_desde = filters.get("fecha_desde")
        fecha_hasta = filters.get("fecha_hasta")
        if fecha_desde or fecha_hasta:
            fecha_query = {}
            if fecha_desde:
                fecha_query["$gte"] = fecha_desde
            if fecha_hasta:
                fecha_query["$lte"] = fecha_hasta
            query["fecha_creacion"] = fecha_query

        return await self.model.find(query).sort("-fecha_creacion").skip(skip).limit(limit).to_list()
