from pydantic import BaseModel, Field

class ParseRequest(BaseModel):
    address_raw: str = Field(..., min_length=1)

class ParseResponse(BaseModel):
    sumname: str = ""
    horooid: int = 0
    bair: int = 0
    korpus: str = "0"
    xaalga: int = 0
    confidence: float = 0.0
    matched_pattern: str = "none"
    normalized: str = ""
