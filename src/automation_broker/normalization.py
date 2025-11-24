import re
import unicodedata
from datetime import datetime
from typing import Optional

from dateutil import parser

SPANISH_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def normalize_date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    # Try dd/mm/yyyy first
    m = re.search(r"(\d{1,2})[\-/\.](\d{1,2})[\-/\.](\d{2,4})", value)
    if m:
        d, mo, y = m.groups()
        if len(y) == 2:
            y = ("20" + y) if int(y) < 50 else ("19" + y)
        try:
            dt = datetime(int(y), int(mo), int(d))
            return dt.strftime("%d/%m/%Y")
        except Exception:
            return None

    # Try Spanish textual dates e.g. "20 de octubre de 2025"
    normalized_spanish = extract_spanish_date(value)
    if normalized_spanish:
        return normalized_spanish

    # Fallback to dateutil for other permissive formats
    try:
        dt = parser.parse(value, dayfirst=True, yearfirst=False)
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


def extract_spanish_date(text: str) -> Optional[str]:
    if not text:
        return None
    # e.g. "Buenos Aires, 20 de octubre de 2025" or just "20 de octubre de 2025"
    m = re.search(
        r"(\d{1,2})\s+de\s+([a-záéíóú]+)\s+de\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if not m:
        return None
    d_str, month_name, y_str = m.groups()
    month_name_norm = month_name.lower()
    month_num = SPANISH_MONTHS.get(month_name_norm)
    if not month_num:
        return None
    try:
        dt = datetime(int(y_str), int(month_num), int(d_str))
        return dt.strftime("%d/%m/%Y")
    except Exception:
        return None


def normalize_money(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    s = str(value)
    s = s.replace("\u00a0", " ")
    s = s.replace(" ", "")
    s = s.replace(".", "").replace(",", ".")
    m = re.search(r"(-?\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None


def normalize_plate(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return value.replace("-", "").replace(" ", "").upper()


def normalize_text_for_comparison(s: str) -> str:
    """
    Normalize text by removing accents and converting to lowercase.
    
    Useful for comparing text values in a tolerant way (e.g., for selecting
    options in dropdowns where accents or case might differ).
    
    Args:
        s: Input string to normalize
        
    Returns:
        Normalized string (lowercase, no accents, trimmed)
    """
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.strip().lower()
