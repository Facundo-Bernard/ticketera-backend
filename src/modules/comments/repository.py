from typing import List, Optional, Dict, Any
from datetime import datetime
from beanie import PydanticObjectId
from ...repositories.base_repository import BaseRepository
from ...core.date_utils import parse_date_filter
from .model import CommentBucket, CommentItem
from .schemas import CommentCreate, CommentUpdate

class CommentRepository(BaseRepository[CommentBucket, CommentCreate, CommentUpdate]):
    """
    Repositorio para el Patrón Bucket de Comentarios.
    Hereda de BaseRepository y añade operaciones de array de alto rendimiento ($push, $pull, $slice, $filter).
    """
    def __init__(self):
        super().__init__(model=CommentBucket)

    async def add_comment(
        self,
        ticket_id: PydanticObjectId,
        comment_in: CommentCreate
    ) -> CommentItem:
        """
        Inserta un nuevo comentario en el array 'comentarios' del bucket del ticket.
        Usa $push y $inc atómicos con upsert=True.
        """
        new_item = CommentItem(
            autor=comment_in.autor,
            mensaje=comment_in.mensaje
        )
        col = self.model.get_pymongo_collection()
        item_dict = new_item.model_dump()

        await col.update_one(
            {"ticket_id": ticket_id},
            {
                "$push": {
                    "comentarios": {
                        "$each": [item_dict],
                        "$sort": {"fecha_creacion": -1}
                    }
                },
                "$inc": {"total": 1}
            },
            upsert=True
        )
        return new_item

    async def get_comments(
        self,
        ticket_id: PydanticObjectId,
        filters: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 10
    ) -> List[CommentItem]:
        """
        Obtiene comentarios paginados (ej. de 10 en 10) usando proyección nativa $slice de MongoDB.
        Si se especifican filtros (autor, fechas), ejecuta una agregación con $filter nativo en el motor.
        """
        col = self.model.get_pymongo_collection()
        filters = filters or {}

        autor_filter = filters.get("autor")
        fecha_desde = parse_date_filter(filters.get("fecha_desde"), is_end_date=False)
        fecha_hasta = parse_date_filter(filters.get("fecha_hasta"), is_end_date=True)

        has_criteria = bool(autor_filter or fecha_desde or fecha_hasta)

        if not has_criteria:
            # Camino de ultra-alto rendimiento: proyección $slice directa de MongoDB
            doc = await col.find_one(
                {"ticket_id": ticket_id},
                projection={"comentarios": {"$slice": [skip, limit]}}
            )
            if not doc or "comentarios" not in doc:
                return []
            return [CommentItem(**c) for c in doc["comentarios"]]

        # Camino con filtros: Agregación con $filter y $slice en MongoDB
        conds = []
        if autor_filter:
            conds.append({
                "$regexMatch": {
                    "input": "$$c.autor",
                    "regex": autor_filter,
                    "options": "i"
                }
            })
        if fecha_desde:
            conds.append({"$gte": ["$$c.fecha_creacion", fecha_desde]})
        if fecha_hasta:
            conds.append({"$lte": ["$$c.fecha_creacion", fecha_hasta]})

        filter_expr = {"$and": conds} if len(conds) > 1 else conds[0]

        pipeline = [
            {"$match": {"ticket_id": ticket_id}},
            {
                "$project": {
                    "comentarios": {
                        "$slice": [
                            {
                                "$filter": {
                                    "input": "$comentarios",
                                    "as": "c",
                                    "cond": filter_expr
                                }
                            },
                            skip,
                            limit
                        ]
                    }
                }
            }
        ]

        cursor = await col.aggregate(pipeline)
        docs = await cursor.to_list(length=1)
        if not docs or "comentarios" not in docs[0]:
            return []
        return [CommentItem(**c) for c in docs[0]["comentarios"]]

    async def count_comments(
        self,
        ticket_id: PydanticObjectId,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Retorna la cantidad de comentarios. Sin filtros lee directamente el campo 'total' en O(1).
        Con filtros cuenta los elementos que satisfacen el filtro.
        """
        col = self.model.get_pymongo_collection()
        filters = filters or {}

        autor_filter = filters.get("autor")
        fecha_desde = parse_date_filter(filters.get("fecha_desde"), is_end_date=False)
        fecha_hasta = parse_date_filter(filters.get("fecha_hasta"), is_end_date=True)

        has_criteria = bool(autor_filter or fecha_desde or fecha_hasta)
        if not has_criteria:
            doc = await col.find_one({"ticket_id": ticket_id}, projection={"total": 1})
            return doc.get("total", 0) if doc else 0

        conds = []
        if autor_filter:
            conds.append({
                "$regexMatch": {
                    "input": "$$c.autor",
                    "regex": autor_filter,
                    "options": "i"
                }
            })
        if fecha_desde:
            conds.append({"$gte": ["$$c.fecha_creacion", fecha_desde]})
        if fecha_hasta:
            conds.append({"$lte": ["$$c.fecha_creacion", fecha_hasta]})

        filter_expr = {"$and": conds} if len(conds) > 1 else conds[0]

        pipeline = [
            {"$match": {"ticket_id": ticket_id}},
            {
                "$project": {
                    "total": {
                        "$size": {
                            "$filter": {
                                "input": "$comentarios",
                                "as": "c",
                                "cond": filter_expr
                            }
                        }
                    }
                }
            }
        ]
        cursor = await col.aggregate(pipeline)
        docs = await cursor.to_list(length=1)
        return docs[0]["total"] if docs else 0

    async def delete_comment(self, ticket_id: PydanticObjectId, comment_id: str) -> bool:
        """
        Elimina un comentario del array usando $pull y decrementa el 'total' en 1 de forma atómica.
        """
        col = self.model.get_pymongo_collection()
        res = await col.update_one(
            {"ticket_id": ticket_id, "comentarios.id": comment_id},
            {
                "$pull": {"comentarios": {"id": comment_id}},
                "$inc": {"total": -1}
            }
        )
        return res.modified_count > 0

    async def delete_by_ticket(self, ticket_id: PydanticObjectId) -> int:
        """Elimina el bucket completo de un ticket."""
        res = await self.model.find(self.model.ticket_id == ticket_id).delete()
        return res.deleted_count if res else 0
