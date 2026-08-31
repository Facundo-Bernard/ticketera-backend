from pydantic import BaseModel

class OptionItem(BaseModel):
    value: str
    label: str

class AsignableItem(BaseModel):
    id: str
    nombre: str
