from pydantic import BaseModel

class OptionItem(BaseModel):
    value: str
    label: str
