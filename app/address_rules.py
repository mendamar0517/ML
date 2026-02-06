# -*- coding: utf-8 -*-
import re
import unicodedata
from difflib import SequenceMatcher

UNIT_WORD = r"(?:ТООТ|Т|№|NO\.?|NO|ТОТ|ТОО|ТООТ\.?|TOOT|TOOT\.?)"
SEP_CHARS = r'[.\\\/\-#\$\^&\*\?`~:;<>|]'

CANON_DISTRICTS = {
    "БАЯНЗҮРХ": [
        "БАЯНЗҮРХ", "БАНЗҮР", "БАЯНЗҮР", "БЗД", "БЗ", "БАНЗҮРХ", "БАЯНЗУРХ", "БАЯНЗҮРХД",
        "BAYANZURKH", "BAYNZURKH", "BAYNZURH", "BAYANZURH", "BAYANZUR", "BZD", "BZ"
    ],
    "БАЯНГОЛ": [
        "БАЯНГОЛ", "БАНГОЛ", "БЯНГОЛ", "БГД", "БГ",
        "BAYANGOL", "BAYNGOL", "BYANGOL", "BGD", "BG"
    ],
    "СҮХБААТАР": [
        "СҮХБААТАР","СҮХБАТАА", "СҮХБАТАР", "СБД", "СБ", "СУХБААТАР",
        "SUKHBAATAR","SUKHBATAR","SUHBATAR", "SUHBAATAR", "SBD", "SB"
    ],
    "ЧИНГЭЛТЭЙ": [
        "ЧИНГЭЛТЭЙ", "ЧИНГИЛТЭЙ", "ЧЭНГЭЛТЭЙ", "ЧИНГЭЛТЙ", "ЧИНГИЛТЭ", "ЧИНГЭЛТЭ", "ЧД", "Ч",
        "CHINGELTEI", "CINGELTEI", "CHINGELTE", "CHINGILTEI", "CHINGELTEY", "CHD", "CH"
    ],
    "СОНГИНОХАЙРХАН": [
        "СОНГИНОХАЙРХАН","СОНГНОХАЙРХАН","СОНГИНОХАРХАН", "СОНГИНХАЙРХАН", "СХД", "СХ",
        "SONGINOKHAIRKHAN", "SONGINKHAIRKHAN", "SONGINHAIRHAN", "SONGNOKHAIRKHAN", "SONGNOHAIRHAN", "SONGINOHAIRHAN", "SKHD", "SHD"
    ],
    "ХАН-УУЛ": [
        "ХАН-УУЛ", "ХУД", "ХУ", "ХАН УУЛ", "ХАНУУЛ", "ХАНУЛ",
        "KHAN-UUL", "KHANUUL", "HAN-UUL", "HANUUL", "HUD"
    ],
    "НАЛАЙХ": [
        "НАЛАЙХ", "НАЛАХ", "НД", "Н",
        "NALAIKH","NALAH", "NALAIH", "ND"
    ],
    "БАГАНУУР": [
        "БАГАНУУР", "БАГНУУР", "БАГНУР", "БНД", "БН",
        "BAGANUUR","BAGNUUR","BAGNUR", "BAGANUR", "BND"
    ],
    "БАГАХАНГАЙ": [
        "БАГАХАНГАЙ", "БАГХАНГАЙ", "БАГАХАНГА", "БХД", "БХ",
        "BAGAKHANGAI","BAGKHANGAI","BAGAKHANGA","BAGHANGAI", "BAGAHANGAI", "BHD"
    ],
}

DISTRICT_MIN_SCORE = 0.85


def normalize_address(text: str) -> str:
    if not text:
        return ""
    s = str(text).upper().strip()
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[，,]+", " ", s)

    # "56Т" -> "56 Т" , "56ТООТ" -> "56 ТООТ" (тоот наалдах)
    s = re.sub(rf"(\d+)\s*({UNIT_WORD})\b", r"\1 \2", s)

    s = re.sub(r"\s+", " ", s).strip()
    return s


def _find_district(text: str):
    t = text.upper()

    # exact
    for canon, aliases in CANON_DISTRICTS.items():
        for a in aliases:
            if re.search(rf"\b{re.escape(a)}\b", t):
                return canon

    # fuzzy
    best, best_score = None, 0.0
    for w in t.split():
        w2 = re.sub(r"[^\w]", "", w)
        if len(w2) < 2:
            continue
        for canon, aliases in CANON_DISTRICTS.items():
            for a in aliases:
                sc = SequenceMatcher(None, w2, a).ratio()
                if sc > best_score and sc >= DISTRICT_MIN_SCORE:
                    best, best_score = canon, sc
    return best


def _find_horoo(text: str, district: str):
    # 3-Р ХОРОО / 3 KHOROO / 3 H / 3Х
    m = re.search(r"(\d{1,2})\s*(?:-Р|-R)?\s*(?:ХОРОО|HOROO|KHOROO|Х|H)\b", text, re.I)
    if m:
        return int(m.group(1))

    m = re.search(r"\b(\d{1,2})\s*(?:Х|H)\b", text, re.I)
    if m:
        return int(m.group(1))

    # district-ийн дараах тоо
    if district:
        for a in CANON_DISTRICTS.get(district, []) + [district]:
            m = re.search(rf"{re.escape(a)}\s*(\d{{1,2}})\b", text, re.I)
            if m:
                return int(m.group(1))
    return 0


def _find_building_block_fallback(text: str):
    # 44 50 ТООТ
    m = re.search(rf"\b(\d{{1,5}})\s+(\d{{1,4}})\s*(?:{UNIT_WORD})?\b", text)
    if m:
        return int(m.group(1)), "0", int(m.group(2)), "bair xaalga"

    # зөвхөн тоот
    m = re.search(rf"(?:\b{UNIT_WORD}\b\s*(\d{{1,4}})\b|\b(\d{{1,4}})\s*{UNIT_WORD}\b)", text)
    if m:
        num = m.group(1) or m.group(2)
        return 0, "0", int(num), "xaalga only"

    return 0, "0", 0, "none"


def parse_with_rules(text: str):
    norm = normalize_address(text)
    sumname = _find_district(norm) or ""
    horooid = _find_horoo(norm, sumname)

    content = norm

    # --- remove horoo phrase + horoo number ---
    if horooid > 0:
        for hp in [
            rf"\b{horooid}\s*(?:-Р|-R)?\s*(?:ХОРОО|HOROO|KHOROO|Х|H)\b",
            rf"\b{horooid}(?:Х|H)\b",
        ]:
            content = re.sub(hp, " ", content, flags=re.I)
        content = re.sub(rf"\b{horooid}\b", " ", content)

    # --- remove city + district aliases ---
    skip = ["УЛААНБААТАР", "ULAANBAATAR", "UB", "ХОТ", "HOT", sumname]
    skip += CANON_DISTRICTS.get(sumname, [])
    for k in skip:
        if k:
            content = re.sub(rf"\b{re.escape(k)}\b", " ", content, flags=re.I)

    content = re.sub(r"\s+", " ", content).strip()

    # blocks: digit орсон token-ууд
    blocks = [b for b in content.split() if re.search(r"\d", b)]

    bair, korpus, xaalga = 0, "0", 0
    matched_pattern = "none"

    # ======================================================
    # ✅ SPECIAL RULE (10-9) зөвхөн ганцхан блок үед!
    #   Ж: "... 3 10-9"  -> blocks = ["10-9"]
    #   Харин "... 3 10/5 59" -> blocks = ["10/5","59"] => ЭНД special rule АЖИЛЛАХ ЁСГҮЙ
    # ======================================================
    if horooid > 0 and len(blocks) == 1:
        m = re.match(r"^\s*(\d{1,5})\s*[-./]\s*(\d{1,4})\s*$", blocks[0])
        if m:
            bair = int(m.group(1))
            korpus = "0"
            xaalga = int(m.group(2))
            matched_pattern = "bair-xaalga-no-korpus"
            return {
                "SUMNAME_PRED": sumname,
                "HOROOID_PRED": horooid,
                "BAIR_PRED": bair,
                "KORPUS_PRED": korpus,
                "XAALGA_PRED": xaalga,
                "CONFIDENCE": 0.97,
                "MATCHED_PATTERN": matched_pattern,
            }

    # ======================================================
    # STRICT CONTENT BLOCKS:
    #   "10/5 59" => bair=10 korpus=5 xaalga=59
    #   "10 59"   => bair=10 korpus=0 xaalga=59
    # ======================================================
    if len(blocks) >= 2:
        first = blocks[0]     # "10/5" эсвэл "10"
        last = blocks[-1]     # "59" гэх мэт

        m = re.match(r"^(\d+)", first)
        if m:
            bair = int(m.group(1))
            rem = first[len(str(bair)):]  # "/5" ".A" гэх мэт

            # korpus дээр тэмдэг хадгалахгүй: "/5" -> "5"
            korpus = re.sub(r"[^0-9А-ЯӨҮЁA-Z]", "", rem) or "0"

            m2 = re.search(r"\d+", last)
            if m2:
                xaalga = int(m2.group())
                matched_pattern = "strict_content_blocks"

    # ======================================================
    # FALLBACK
    # ======================================================
    if matched_pattern == "none":
        bair, korpus, xaalga, matched_pattern = _find_building_block_fallback(content)

    conf = 0.98 if (bair > 0 and xaalga > 0) else 0.0

    return {
        "SUMNAME_PRED": sumname,
        "HOROOID_PRED": horooid,
        "BAIR_PRED": bair,
        "KORPUS_PRED": korpus if korpus else "0",
        "XAALGA_PRED": xaalga,
        "CONFIDENCE": conf,
        "MATCHED_PATTERN": matched_pattern,
    }
