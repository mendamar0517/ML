from fastapi import FastAPI
from schemas import ParseRequest, ParseResponse
from address_rules import normalize_address, parse_with_rules

app = FastAPI(title="Address Parser Service", version="1.0.0")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/parse", response_model=ParseResponse)
def parse(req: ParseRequest):
    raw = req.address_raw.strip()
    norm = normalize_address(raw)

    # address_rules.py-аас үр дүнгээ авна
    r = parse_with_rules(norm)

    return ParseResponse(
        city=str(r.get("CITY_PRED") or ""),
        sumname=str(r.get("SUMNAME_PRED") or ""),
        horooid=int(r.get("HOROOID_PRED") or 0),
        village=str(r.get("VILLAGE_PRED") or ""),
        bair=int(r.get("BAIR_PRED") or 0),
        korpus=str(r.get("KORPUS_PRED") or "0"),
        xaalga=int(r.get("XAALGA_PRED") or 0),
        formatted_address=str(r.get("FORMATTED_ADDRESS") or ""),  # Энэ key-г анхаар!
        confidence=float(r.get("CONFIDENCE") or 0.0),
        matched_pattern=str(r.get("MATCHED_PATTERN") or "none"),
        normalized=norm,
    )