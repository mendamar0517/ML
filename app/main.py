from fastapi import FastAPI
from .schemas import ParseRequest, ParseResponse
from .address_rules import normalize_address, parse_with_rules

app = FastAPI(title="Address Parser Service", version="1.0.0")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/parse", response_model=ParseResponse)
def parse(req: ParseRequest):
    raw = req.address_raw.strip()
    norm = normalize_address(raw)
    r = parse_with_rules(norm)

    return ParseResponse(
        sumname=r.get("SUMNAME_PRED") or "",
        horooid=int(r.get("HOROOID_PRED") or 0),
        bair=int(r.get("BAIR_PRED") or 0),
        korpus=str(r.get("KORPUS_PRED") or "0"),
        xaalga=int(r.get("XAALGA_PRED") or 0),
        confidence=float(r.get("CONFIDENCE") or 0.0),
        matched_pattern=r.get("MATCHED_PATTERN") or "none",
        normalized=norm,
    )
