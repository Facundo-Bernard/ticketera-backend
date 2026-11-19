from enum import Enum
import json
from typing import Any, Optional, List, Literal
from datetime import datetime, timezone
from beanie import Document, Indexed
from pydantic import BaseModel, Field, EmailStr, field_validator
from pymongo import ASCENDING, DESCENDING, IndexModel


def normalize_asignados(value: Any) -> List[str]:
    """Normaliza asignados legados (None, string CSV/JSON) o listas a una lista deduplicada."""
    if value is None:
        return []
    raw_items: List[Any] = []
    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return []
        if trimmed.startswith("[") and trimmed.endswith("]"):
            try:
                parsed = json.loads(trimmed)
                if isinstance(parsed, list):
                    raw_items = parsed
                else:
                    raw_items = [trimmed]
            except Exception:
                raw_items = trimmed.split(",")
        else:
            raw_items = trimmed.split(",")
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            raw_items.extend(normalize_asignados(item))
    else:
        raw_items = [str(value)]

    result: List[str] = []
    seen = set()
    for item in raw_items:
        clean = str(item).strip()
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)
    return result


class Frecuencia(BaseModel):
    numero: int = Field(default=1, ge=1, description="Intervalo numérico")
    periodo: Literal["Días", "Semanas", "Meses", "Años"] = Field(..., description="Período de repetición")

class PrioridadEnum(str, Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"

class EstadoEnum(str, Enum):
    ABIERTO = "abierto"
    EN_PROGRESO = "en_progreso"
    RESUELTO = "resuelto"
    CERRADO = "cerrado"

class Ticket(Document):
    titulo: str = Field(..., min_length=3, max_length=150)
    descripcion: str
    imagenes: List[str] = Field(default_factory=list)
    asignar: List[str] = Field(default_factory=list, description="Lista de técnicos/operadores asignados")
    fecha_creacion: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fecha_edicion: Optional[datetime] = Field(default=None)
    identificador: Indexed(str, unique=True, sparse=True)
    correo: EmailStr
    prioridad: PrioridadEnum = Field(default=PrioridadEnum.MEDIA)
    estado: EstadoEnum = Field(default=EstadoEnum.ABIERTO)
    columna: int = Field(default=1, ge=1, le=4, description="ID numérico de la columna (1: Ticket, 2: Hitos, 3: Tareas, 4: Tareas periódicas)")
    leido: bool = Field(default=False, description="Indica si el ticket ya fue abierto/leído por el equipo")
    frecuencia: Optional[Frecuencia] = Field(default=None, description="Frecuencia periódica de repetición si aplica")

    @field_validator("asignar", mode="before")
    @classmethod
    def _validate_asignar(cls, v: Any) -> List[str]:
        return normalize_asignados(v)

    class Settings:
        name = "tickets"
        indexes = [
            IndexModel([("columna", ASCENDING), ("estado", ASCENDING), ("fecha_creacion", DESCENDING)]),
            IndexModel([("correo", ASCENDING), ("fecha_creacion", DESCENDING)]),
            IndexModel([("fecha_creacion", DESCENDING)]),
        ]

