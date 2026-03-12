from pydantic import BaseModel, Field

class ParseRequest(BaseModel):
    address_raw: str = Field(..., min_length=1)

class ParseResponse(BaseModel):
    city: str = ""
    sumname: str = ""
    horooid: int = 0
    village: str = ""
    bair: int = 0
    korpus: str = "0"
    xaalga: int = 0
    formatted_address: str = ""  # Албан ёсны хэлбэр
    confidence: float = 0.0
    matched_pattern: str = "none"
    normalized: str = ""