import logging
from typing import List
from ..schemas.catalog_schema import OptionItem
from ..models.ticket_model import PrioridadEnum, EstadoEnum
from ..modules.auth.model import User

logger = logging.getLogger(__name__)

DEFAULT_ASIGNABLES = [
    OptionItem(value="facundo_bernard", label="Facundo Bernard"),
    OptionItem(value="nicolas_fernandez", label="Nicolas Fernandez"),
    OptionItem(value="nahuel_monti", label="Nahuel Monti"),
]

class CatalogService:
    def get_estados(self) -> List[OptionItem]:
        estado_labels = {
            EstadoEnum.ABIERTO: "Abierto",
            EstadoEnum.EN_PROGRESO: "En Progreso",
            EstadoEnum.RESUELTO: "Resuelto",
            EstadoEnum.CERRADO: "Cerrado"
        }
        return [
            OptionItem(value=e.value, label=estado_labels.get(e, e.value.replace("_", " ").title()))
            for e in EstadoEnum
        ]

    def get_prioridades(self) -> List[OptionItem]:
        prioridad_labels = {
            PrioridadEnum.BAJA: "Baja",
            PrioridadEnum.MEDIA: "Media",
            PrioridadEnum.ALTA: "Alta",
            PrioridadEnum.CRITICA: "Crítica"
        }
        return [
            OptionItem(value=p.value, label=prioridad_labels.get(p, p.value.title()))
            for p in PrioridadEnum
        ]

    async def get_asignables(self) -> List[OptionItem]:
        """Devuelve técnicos asignables combinando usuarios activos de MongoDB y los por defecto."""
        result: List[OptionItem] = list(DEFAULT_ASIGNABLES)
        seen_labels = {item.label.strip().lower() for item in result}

        try:
            active_users = await User.find(User.activo == True).to_list()  # noqa: E712
            for u in active_users:
                clean_name = (u.nombre or "").strip()
                if not clean_name or clean_name.lower() == "administrador general":
                    continue
                if clean_name.lower() not in seen_labels:
                    seen_labels.add(clean_name.lower())
                    slug = clean_name.lower().replace(" ", "_")
                    result.append(OptionItem(value=slug, label=clean_name))
        except Exception as exc:
            logger.warning(f"No se pudieron consultar usuarios asignables desde MongoDB: {exc}")

        return result

