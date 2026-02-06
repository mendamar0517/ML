# -*- coding: utf-8 -*-
import re
import unicodedata
from difflib import SequenceMatcher

# =========================
# Constants
# =========================
UNIT_WORD = r"(?:ТООТ|Т|№|NO\.?|NO|ТОТ|ТОО|ТООТ\.?|TOOT|TOOT\.?)"
SEP_CHARS = r'[.\\\/\-#\$\^&\*\?`~:;<>|]'
SEP = rf"(?:{SEP_CHARS}|\s+)"

# Дүүргийн нэрсийн латин болон кирилл хувилбаруудыг нэгтгэв
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
    if text is None: return ""
    # Кирилл болон Латин холимог байж болох тул зөвхөн том үсэг болгоно
    s = str(text).strip().upper()
    s = s.replace("\n", " ").replace("\r", " ")
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\t", " ")
    s = re.sub(r"[，,]+", " ", s)

    # Хорооны стандартууд (Кирилл + Латин)
    s = re.sub(r"(\d+)\s*-\s*Р", r"\1-Р", s)
    s = re.sub(r"(\d+)\s*Р\b", r"\1-Р", s)

    # ТООТ-г наах
    s = re.sub(rf"(\d+)\s*({UNIT_WORD})\b", r"\1 \2", s)

    s = re.sub(r"\s+", " ", s).strip()
    return s


def _find_district(text: str):
    t = text.upper()
    # 1. Exact match (Латин ба Кирилл алиасуудыг шалгана)
    for canon, aliases in CANON_DISTRICTS.items():
        for alias in aliases:
            if re.search(rf"\b{alias}\b", t):
                return canon

    # 2. Fuzzy match
    best_match = None
    max_score = 0
    words = t.split()
    for word in words:
        clean_word = re.sub(r'[^\w]', '', word)
        if len(clean_word) < 2: continue

        for canon, aliases in CANON_DISTRICTS.items():
            for alias in aliases:
                score = SequenceMatcher(None, clean_word, alias).ratio()
                if score > max_score and score >= DISTRICT_MIN_SCORE:
                    max_score = score
                    best_match = canon
    return best_match


def _find_horoo(text: str, district_name: str):
    """
    Хороог кирилл болон латин хэлбэрээр хайх
    """
    # 1) Классик бичиглэл: 3-Р ХОРОО, 3 KHOROO, 3 HOROO, 3-R HOROO
    m = re.search(r"(\d{1,2})\s*(?:-Р|-R)?\s*(?:ХОРОО|KHOROO|HOROO|H|Х)\b", text, re.I)
    if m: return int(m.group(1))

    # 2) Товчилсон: 3Х, 3H
    m = re.search(r"\b(\d{1,2})\s*(?:Х|H)\b", text, re.I)
    if m: return int(m.group(1))

    # 3) Дүүргийн ард байгаа тоо
    if district_name:
        aliases = CANON_DISTRICTS.get(district_name, []) + [district_name]
        for alias in aliases:
            m = re.search(rf"{alias}\s*(\d{{1,2}})\b", text, re.I)
            if m: return int(m.group(1))
    return 0


def _find_building_block(text: str, horoo: int):
    search_text = text
    # 1) БАЙР [ТУСГААРЛАГЧ] КОРПУС [ЗАЙ] ТООТ
    m = re.search(rf"\b(\d{{1,5}})({SEP_CHARS})([А-ЯӨҮЁA-Z]|\d{{1,2}})\s+(\d{{1,4}})\b", search_text)
    if m:
        return int(m.group(1)), m.group(3), int(m.group(4)), "bair.korpus xaalga"

    # 2) БАЙР+ҮСЭГ [ЗАЙ] ТООТ
    m = re.search(rf"\b(\d{{1,5}})([А-ЯӨҮЁA-Z])\s+(\d{{1,4}})\b", search_text)
    if m:
        return int(m.group(1)), m.group(2), int(m.group(3)), "bair+letter xaalga"

    # 3) БАЙР [ЗАЙ] ТООТ
    m = re.search(rf"\b(\d{{1,5}})\s+(\d{{1,4}})\s*(?:{UNIT_WORD})?\b", search_text)
    if m:
        return int(m.group(1)), "0", int(m.group(2)), "bair xaalga"

    # 4) Зөвхөн тоот
    m = re.search(rf"{UNIT_WORD}\s*(\d{{1,4}})\b", search_text)
    if m:
        return 0, "0", int(m.group(1)), "xaalga only"

    return 0, "0", 0, "none"


def parse_with_rules(text: str):
    norm_text = normalize_address(text)
    sumname = _find_district(norm_text) or ""

    # 1. Хороог олж, текстээс БҮРЭН (таслалтай нь) устгах
    horooid = _find_horoo(norm_text, sumname)
    content_area = norm_text

    if horooid > 0:
        horoo_patterns = [
            rf"\b{horooid}\s*(?:-Р|-R)?\s*(?:ХОРОО|KHOROO|HOROO|Х|H)\b",
            rf"\b{horooid}(?:Х|H)\b"
        ]
        for pat in horoo_patterns:
            content_area = re.sub(pat, " ", content_area, flags=re.I)

        # Хорооны тоог таслалтай нь хамт устгах
        content_area = re.sub(rf"\b{horooid}\b\s*,?", " ", content_area)

    # 2. Дүүргийн нэр болон Хотын нэрийг устгах (Латин + Кирилл)
    skip_keywords = ["УЛААНБААТАР", "ULAANBAATAR", "UB", "ХОТ", "HOT", sumname]
    if sumname in CANON_DISTRICTS:
        skip_keywords.extend(CANON_DISTRICTS[sumname])

    for k in skip_keywords:
        if k:
            content_area = re.sub(rf"\b{re.escape(str(k))}\b\s*,?", " ", content_area, flags=re.I)

    # 3. Текстийг цэвэрлэх
    content_area = content_area.replace(",", " ").strip()
    content_area = re.sub(r"\s+", " ", content_area)

    # 4. Блок салгалт
    blocks = [p.strip() for p in content_area.split() if re.search(r'\d', p)]

    bair, korpus, xaalga = 0, "0", 0
    pat = "none"

    if len(blocks) >= 2:
        b_block = blocks[0]  # ж: "10/5", "10.5", "10-5"

        bair_match = re.match(r'(\d+)', b_block)
        if bair_match:
            bair = int(bair_match.group(1))

            rem = b_block[len(str(bair)):]  # "/5", ".5", "-5"

            # ⭐ зөвхөн тоо/үсэг үлдээнэ
            korpus = re.sub(r"[^0-9А-ЯӨҮЁA-Z]", "", rem)
            if not korpus:
                korpus = "0"

            # хаалга
            xaalga_match = re.search(r'\d+', blocks[-1])
            if xaalga_match:
                xaalga = int(xaalga_match.group())
                pat = "strict_content_blocks"

    if pat == "none":
        bair, korpus, xaalga, pat = _find_building_block(content_area, horooid)

    return {
        "SUMNAME_PRED": sumname,
        "HOROOID_PRED": horooid,
        "BAIR_PRED": bair,
        "KORPUS_PRED": korpus if korpus else "0",
        "XAALGA_PRED": xaalga,
        "CONFIDENCE": 0.98 if (bair > 0 and xaalga > 0) else 0.0,
        "MATCHED_PATTERN": pat,
    }