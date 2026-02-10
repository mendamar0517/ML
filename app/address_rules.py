# -*- coding: utf-8 -*-
"""
Address parsing rules (Mongolia / UB districts) - production-ready improvements:
- Regex precompile (performance)
- alias -> canon map (fast exact match)
- Fuzzy only as last resort
- Better horoo detection (кирилл/латин, 3х, 3-р, 3 horoo, district+number)
- Better building parsing:
    * KEYWORD priority (supports variants):
        - "2 BAIR 4 KORPUS 67 TOOT" => bair=2 korpus=4 xaalga=67
        - "BAIR 2 KORPUS 3 TOOT 56" => bair=2 korpus=3 xaalga=56
        - "BAIR 2 3 KORPUS 56"      => bair=2 korpus=3 xaalga=56 (door without TOOT)
        - "KORPUS 3 56"             => korpus=3 xaalga=56 (bair=0)
    * "10/5 59" => bair=10 korpus=5 xaalga=59
    * "10 59"   => bair=10 korpus=0 xaalga=59
    * "10-9" (single token after horoo) => bair=10 korpus=0 xaalga=9
    * "44 50 ТООТ" => bair=44 korpus=0 xaalga=50
- Korpus keeps only [0-9A-ZА-ЯӨҮЁ] (no '/', '.', etc)
- Range validation + confidence adjustment
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, Tuple, List, Optional

RULES_VERSION = "2026-02-10.4"

# =========================
# Constants
# =========================
UNIT_WORD = r"(?:ТООТ|ТОТ|ТОО|Т|№|NO\.?|NO|TOOT|TOOT\.?)"
SEP_CHARS = r'[.\\\/\-#\$\^&\*\?`~:;<>|]'

DISTRICT_MIN_SCORE = 0.85

CANON_DISTRICTS = {
    "БАЯНЗҮРХ": [
        "БАЯНЗҮРХ", "БАНЗҮР", "БАЯНЗҮР", "БЗД", "БЗ", "БАНЗҮРХ", "БАЯНЗУРХ", "БАЯНЗҮРХД",
        "BAYANZURKH", "BAYNZURKH", "BAYNZURH", "BAYANZURH", "BAYANZUR", "BZD", "BZ", "BANZUR"
    ],
    "БАЯНГОЛ": [
        "БАЯНГОЛ", "БАНГОЛ", "БЯНГОЛ", "БГД", "БГ",
        "BAYANGOL", "BAYNGOL", "BYANGOL", "BGD", "BG"
    ],
    "СҮХБААТАР": [
        "СҮХБААТАР", "СҮХБАТАА", "СҮХБАТАР", "СБД", "СБ", "СУХБААТАР",
        "SUKHBAATAR", "SUKHBATAR", "SUHBATAR", "SUHBAATAR", "SBD", "SB"
    ],
    "ЧИНГЭЛТЭЙ": [
        "ЧИНГЭЛТЭЙ", "ЧИНГИЛТЭЙ", "ЧЭНГЭЛТЭЙ", "ЧИНГЭЛТЙ", "ЧИНГИЛТЭ", "ЧИНГЭЛТЭ", "ЧД", "Ч",
        "CHINGELTEI", "CINGELTEI", "CHINGELTE", "CHINGILTEI", "CHINGELTEY", "CHD", "CH"
    ],
    "СОНГИНОХАЙРХАН": [
        "СОНГИНОХАЙРХАН", "СОНГНОХАЙРХАН", "СОНГИНОХАРХАН", "СОНГИНХАЙРХАН", "СХД", "СХ",
        "SONGINOKHAIRKHAN", "SONGINKHAIRKHAN", "SONGINHAIRHAN", "SONGNOKHAIRKHAN",
        "SONGNOHAIRHAN", "SONGINOHAIRHAN", "SKHD", "SHD"
    ],
    "ХАН-УУЛ": [
        "ХАН-УУЛ", "ХУД", "ХУ", "ХАН УУЛ", "ХАНУУЛ", "ХАНУЛ",
        "KHAN-UUL", "KHANUUL", "HAN-UUL", "HANUUL", "HUD", "HANUL", "KHANUL"
    ],
    "НАЛАЙХ": [
        "НАЛАЙХ", "НАЛАХ", "НД", "Н",
        "NALAIKH", "NALAH", "NALAIH", "ND"
    ],
    "БАГАНУУР": [
        "БАГАНУУР", "БАГНУУР", "БАГНУР", "БНД", "БН",
        "BAGANUUR", "BAGNUUR", "BAGNUR", "BAGANUR", "BND"
    ],
    "БАГАХАНГАЙ": [
        "БАГАХАНГАЙ", "БАГХАНГАЙ", "БАГАХАНГА", "БХД", "БХ",
        "BAGAKHANGAI", "BAGKHANGAI", "BAGAKHANGA", "BAGHANGAI", "BAGAHANGAI", "BHD"
    ],
}

# =========================
# Precompiled regex
# =========================
RE_SPACES = re.compile(r"\s+")
RE_COMMAS = re.compile(r"[，,]+")
RE_UNIT_GLUE = re.compile(rf"(\d+)\s*({UNIT_WORD})\b", re.I)

# horoo patterns
RE_HOROO_CLASSIC = re.compile(r"(\d{1,2})\s*(?:-Р|-R)?\s*(?:ХОРОО|HOROO|KHOROO)\b", re.I)
RE_HOROO_SHORT = re.compile(r"\b(\d{1,2})\s*(?:Х|H)\b", re.I)  # 3Х, 3H

# building patterns (fallback)
RE_BAIR_KORPUS_XAALGA = re.compile(rf"\b(\d{{1,5}})({SEP_CHARS})([А-ЯӨҮЁA-Z]|\d{{1,2}})\s+(\d{{1,4}})\b")
RE_BAIR_LETTER_XAALGA = re.compile(rf"\b(\d{{1,5}})([А-ЯӨҮЁA-Z])\s+(\d{{1,4}})\b")
RE_BAIR_XAALGA = re.compile(rf"\b(\d{{1,5}})\s+(\d{{1,4}})\s*(?:{UNIT_WORD})?\b", re.I)
RE_XAALGA_ONLY = re.compile(rf"(?:\b{UNIT_WORD}\b\s*(\d{{1,4}})\b|\b(\d{{1,4}})\s*{UNIT_WORD}\b)", re.I)

# "10-9" / "10/9" / "10.9" single-token building w/o korpus (use when appropriate)
RE_BAIR_XAALGA_TOKEN = re.compile(r"^\s*(\d{1,5})\s*[-./]\s*(\d{1,4})\s*$")

# tokenization
RE_WORDS = re.compile(r"[A-ZА-ЯӨҮЁ0-9]+", re.I)

# glue: "2bair" -> "2 BAIR", "67toot" -> "67 TOOT"
RE_NUM_KEYWORD_GLUE = re.compile(
    r"\b(\d+)\s*(BAIR|БАЙР|KORPUS|КОРПУС|CORPUS|TOOT|ТООТ|ТОТ|ТОО|Т|№|NO\.?|NO)\b",
    re.I
)
# glue: "toot67" -> "TOOT 67"
RE_KEYWORD_NUM_GLUE = re.compile(
    r"\b(BAIR|БАЙР|KORPUS|КОРПУС|CORPUS|TOOT|ТООТ|ТОТ|ТОО|Т|№|NO\.?|NO)\s*(\d+)\b",
    re.I
)

# ✅ keyword parsing: number-before-keyword
RE_BAIR_WORD = re.compile(r"\b(\d{1,5})\s*(?:БАЙР|BAIR)\b", re.I)
RE_KORPUS_WORD = re.compile(r"\b(\d{1,5})\s*(?:КОРПУС|KORPUS|CORPUS)\b", re.I)
RE_TOOT_WORD = re.compile(rf"\b(\d{{1,5}})\s*(?:{UNIT_WORD})\b", re.I)

# ✅ keyword parsing: keyword-before-number (NEW)
RE_BAIR_WORD_REV = re.compile(r"\b(?:БАЙР|BAIR)\s*(\d{1,5})\b", re.I)
RE_KORPUS_WORD_REV = re.compile(r"\b(?:КОРПУС|KORPUS|CORPUS)\s*(\d{1,5})\b", re.I)
RE_TOOT_WORD_REV = re.compile(rf"\b(?:{UNIT_WORD})\s*(\d{{1,5}})\b", re.I)

# special: "KORPUS 3 56" => korpus=3, door=56
RE_KORPUS_AND_DOOR = re.compile(r"\b(?:КОРПУС|KORPUS|CORPUS)\s*(\d{1,5})\s+(\d{1,5})\b", re.I)
# implicit: "3 BAIR 4 56" => bair=3, korpus=4, door=56
RE_BAIR_IMPLICIT_KORPUS_DOOR = re.compile(r"\b(\d{1,5})\s*(?:БАЙР|BAIR)\b\s+(\d{1,5})\s+(\d{1,5})\b", re.I)
# reverse: "BAIR 3 4 56"
RE_BAIR_IMPLICIT_KORPUS_DOOR_REV = re.compile(r"\b(?:БАЙР|BAIR)\s*(\d{1,5})\s+(\d{1,5})\s+(\d{1,5})\b", re.I)


# =========================
# Alias map (fast exact)
# =========================
_ALIAS_TO_CANON: Dict[str, str] = {}
for canon, aliases in CANON_DISTRICTS.items():
    for a in aliases + [canon]:
        a2 = (a or "").strip().upper()
        if a2:
            _ALIAS_TO_CANON[a2] = canon


# =========================
# Helpers
# =========================
def _nfkc_upper(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return s.upper().strip()

def _clean_token_for_lookup(tok: str) -> str:
    return re.sub(r"[^\wА-ЯӨҮЁ]", "", tok.upper(), flags=re.I)

def _korpus_clean(rem: str) -> str:
    k = re.sub(r"[^0-9А-ЯӨҮЁA-Z]", "", rem or "")
    return k if k else "0"

def _clamp_ranges(horoo: int, bair: int, xaalga: int) -> Tuple[int, int, int, List[str]]:
    warnings: List[str] = []
    if horoo and not (1 <= horoo <= 99):
        warnings.append("horoo_out_of_range")
        horoo = 0
    if bair and not (1 <= bair <= 99999):
        warnings.append("bair_out_of_range")
        bair = 0
    if xaalga and not (1 <= xaalga <= 99999):
        warnings.append("xaalga_out_of_range")
        xaalga = 0
    return horoo, bair, xaalga, warnings


# =========================
# Normalization
# =========================
def normalize_address(text: str) -> str:
    if not text:
        return ""
    s = _nfkc_upper(str(text))
    s = s.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    s = RE_COMMAS.sub(" ", s)

    # "2BAIR" -> "2 BAIR", "67TOOT" -> "67 TOOT"
    s = RE_NUM_KEYWORD_GLUE.sub(r"\1 \2", s)
    # "TOOT67" -> "TOOT 67"
    s = RE_KEYWORD_NUM_GLUE.sub(r"\1 \2", s)

    # "56ТООТ" -> "56 ТООТ"
    s = RE_UNIT_GLUE.sub(r"\1 \2", s)

    s = RE_SPACES.sub(" ", s).strip()
    return s


# =========================
# District
# =========================
def _find_district(text: str) -> Optional[str]:
    t = _nfkc_upper(text)
    tokens = RE_WORDS.findall(t)

    # exact via alias map
    for tok in tokens:
        key = _clean_token_for_lookup(tok)
        if key in _ALIAS_TO_CANON:
            return _ALIAS_TO_CANON[key]

    # also try 2-token windows (e.g. "ХАН УУЛ")
    for i in range(len(tokens) - 1):
        pair = _clean_token_for_lookup(tokens[i] + tokens[i+1])
        if pair in _ALIAS_TO_CANON:
            return _ALIAS_TO_CANON[pair]

    # fuzzy as last resort
    best, best_score = None, 0.0
    for tok in tokens:
        w = _clean_token_for_lookup(tok)
        if len(w) < 2:
            continue
        for alias, canon in _ALIAS_TO_CANON.items():
            if len(alias) < 2:
                continue
            sc = SequenceMatcher(None, w, alias).ratio()
            if sc > best_score and sc >= DISTRICT_MIN_SCORE:
                best, best_score = canon, sc
    return best


# =========================
# Horoo
# =========================
def _find_horoo(text: str, district: str) -> int:
    m = RE_HOROO_CLASSIC.search(text)
    if m:
        return int(m.group(1))

    m = RE_HOROO_SHORT.search(text)
    if m:
        return int(m.group(1))

    if district:
        for a in CANON_DISTRICTS.get(district, []) + [district]:
            a_u = _nfkc_upper(a)
            if not a_u:
                continue
            m = re.search(rf"\b{re.escape(a_u)}\b\s*(\d{{1,2}})\b", _nfkc_upper(text))
            if m:
                return int(m.group(1))
    return 0


# =========================
# Building fallback
# =========================
def _find_building_block_fallback(text: str) -> Tuple[int, str, int, str]:
    m = RE_BAIR_KORPUS_XAALGA.search(text)
    if m:
        bair = int(m.group(1))
        korpus = _korpus_clean(m.group(3))
        xaalga = int(m.group(4))
        return bair, korpus, xaalga, "bair.korpus xaalga"

    m = RE_BAIR_LETTER_XAALGA.search(text)
    if m:
        bair = int(m.group(1))
        korpus = _korpus_clean(m.group(2))
        xaalga = int(m.group(3))
        return bair, korpus, xaalga, "bair+letter xaalga"

    m = RE_BAIR_XAALGA.search(text)
    if m:
        return int(m.group(1)), "0", int(m.group(2)), "bair xaalga"

    m = RE_XAALGA_ONLY.search(text)
    if m:
        num = m.group(1) or m.group(2)
        return 0, "0", int(num), "xaalga only"

    return 0, "0", 0, "none"


# =========================
# Main parse
# =========================
def parse_with_rules(text: str) -> Dict[str, object]:
    norm = normalize_address(text)
    sumname = _find_district(norm) or ""
    horooid = _find_horoo(norm, sumname)

    content = norm

    # --- remove horoo phrase + horoo number ---
    if horooid > 0:
        # remove "2 HOROO"/"2H" only
        for hp in (
            rf"\b{horooid}\s*(?:-Р|-R)?\s*(?:ХОРОО|HOROO|KHOROO)\b",
            rf"\b{horooid}\s*(?:Х|H)\b",
        ):
            content = re.sub(hp, " ", content, flags=re.I)

        # IMPORTANT: do NOT delete horoo number if used as "2 BAIR"/"BAIR 2"/"2 KORPUS"/"KORPUS 2"/"2 TOOT"...
        content = re.sub(
            rf"(?<!\d)\b{horooid}\b"
            rf"(?!\s*[-./]\s*\d)"  # don't break 1.4, 2/4, 10-9
            rf"(?!\s*(?:BAIR|БАЙР|KORPUS|КОРПУС|CORPUS|{UNIT_WORD})\b)",
            " ",
            content,
            flags=re.I
        )

    # --- remove city + district aliases ---
    skip = ["УЛААНБААТАР", "ULAANBAATAR", "UB", "ХОТ", "HOT"]
    if sumname:
        skip.append(sumname)
        skip.extend(CANON_DISTRICTS.get(sumname, []))

    content_u = _nfkc_upper(content)
    for k in skip:
        if k:
            content_u = re.sub(rf"\b{re.escape(_nfkc_upper(k))}\b", " ", content_u, flags=re.I)

    content_u = RE_SPACES.sub(" ", content_u).strip()

    bair, korpus, xaalga = 0, "0", 0
    matched_pattern = "none"
    warnings: List[str] = []

    # ======================================================
    # ✅ KEYWORD PARSING (priority)
    # Supports:
    #   - "2 BAIR 4 KORPUS 67 TOOT"
    #   - "BAIR 2 KORPUS 3 TOOT 56"
    #   - "BAIR 2 3 KORPUS 56"  (door without TOOT)
    #   - "KORPUS 3 56" => korpus=3, door=56
    # ======================================================
    # --- implicit keyword case: "3 BAIR 4 56" or "BAIR 3 4 56"
    m_imp = RE_BAIR_IMPLICIT_KORPUS_DOOR.search(content_u) or RE_BAIR_IMPLICIT_KORPUS_DOOR_REV.search(content_u)
    if m_imp:
        bair = int(m_imp.group(1))
        korpus = str(int(m_imp.group(2)))
        xaalga = int(m_imp.group(3))
        matched_pattern = "keyword_bair_implicit_korpus_door"
        keyword_matched = True

    # 1) BAIR
    m_bair = RE_BAIR_WORD.search(content_u) or RE_BAIR_WORD_REV.search(content_u)

    # 2) KORPUS (+ optional door right after it)
    m_korp_door = RE_KORPUS_AND_DOOR.search(content_u)
    if m_korp_door:
        m_korpus = m_korp_door  # group(1)=korpus
        door_after_korpus = int(m_korp_door.group(2))
    else:
        m_korpus = RE_KORPUS_WORD.search(content_u) or RE_KORPUS_WORD_REV.search(content_u)
        door_after_korpus = 0

    # 3) TOOT (door)
    m_toot = RE_TOOT_WORD.search(content_u) or RE_TOOT_WORD_REV.search(content_u)

    keyword_matched = False

    if m_bair and (m_korpus or m_toot):
        bair = int(m_bair.group(1))

        if m_korpus:
            korpus = str(int(m_korpus.group(1)))
        else:
            korpus = "0"

        if m_toot:
            xaalga = int(m_toot.group(1))
        elif door_after_korpus > 0:
            # e.g. "KORPUS 3 56"
            xaalga = door_after_korpus
        else:
            # last fallback in keyword-mode: trailing number
            nums = [int(x) for x in re.findall(r"\b\d{1,5}\b", content_u)]
            cand = nums[-1] if nums else 0
            if cand and cand != bair and str(cand) != korpus:
                xaalga = cand
            else:
                xaalga = 0

        matched_pattern = "keyword_bair_korpus_toot"
        keyword_matched = True

    # allow: "KORPUS 3 56" without BAIR
    elif (not m_bair) and m_korp_door:
        bair = 0
        korpus = str(int(m_korp_door.group(1)))
        xaalga = int(m_korp_door.group(2))
        matched_pattern = "keyword_korpus_door"
        keyword_matched = True

    # ======================================================
    # Other logic if keyword not matched
    # ======================================================
    if not keyword_matched:
        raw_blocks = [b.strip(" ,.;") for b in content_u.split() if re.search(r"\d", b)]
        blocks = [b for b in raw_blocks if b]

        # ✅ SPECIAL RULE (10-9) when it's the ONLY numeric block after horoo
        if horooid > 0 and len(blocks) == 1:
            m = RE_BAIR_XAALGA_TOKEN.match(blocks[0])
            if m:
                bair = int(m.group(1))
                korpus = "0"
                xaalga = int(m.group(2))
                matched_pattern = "bair-xaalga-no-korpus"

        # STRICT CONTENT BLOCKS:
        if matched_pattern == "none" and len(blocks) >= 2:
            first = blocks[0]
            last = blocks[-1]

            m = re.match(r"^(\d+)", first)
            if m:
                bair = int(m.group(1))
                rem = first[len(str(bair)):]
                korpus = _korpus_clean(rem)

                m2 = re.search(r"\d+", last)
                if m2:
                    xaalga = int(m2.group())
                    matched_pattern = "strict_content_blocks"

        # FALLBACK
        if matched_pattern == "none":
            bair, korpus, xaalga, matched_pattern = _find_building_block_fallback(content_u)

    # Range validation + confidence
    horooid, bair, xaalga, warns = _clamp_ranges(horooid, bair, xaalga)
    warnings.extend(warns)

    # Confidence strategy
    if bair > 0 and xaalga > 0:
        conf = 0.98
        if matched_pattern in ("keyword_bair_korpus_toot",):
            conf = 0.99
        if matched_pattern == "bair-xaalga-no-korpus":
            conf = 0.97
    elif matched_pattern == "xaalga only" and xaalga > 0:
        conf = 0.30
        warnings.append("partial_only_xaalga")
    elif matched_pattern == "keyword_korpus_door" and xaalga > 0:
        conf = 0.70
        warnings.append("partial_no_bair")
    else:
        conf = 0.0
        warnings.append("not_enough_info")

    return {
        "SUMNAME_PRED": sumname,
        "HOROOID_PRED": int(horooid or 0),
        "BAIR_PRED": int(bair or 0),
        "KORPUS_PRED": str(korpus or "0"),
        "XAALGA_PRED": int(xaalga or 0),
        "CONFIDENCE": float(conf),
        "MATCHED_PATTERN": matched_pattern,
        "RULES_VERSION": RULES_VERSION,
        "NORMALIZED": norm,
        "WARNINGS": warnings,
    }
