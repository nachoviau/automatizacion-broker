from typing import Tuple, List
import re

import pdfplumber

from ..models import PolicyData
from ..normalization import normalize_date, normalize_money, normalize_plate, extract_spanish_date


PAGES_OF_INTEREST = {1, 2, 32, 33, 34}


def _extract_selected_pages_text(pdf_path: str) -> dict[int, str]:
    pages_text: dict[int, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):
            if idx in PAGES_OF_INTEREST:
                try:
                    page_text = page.extract_text() or ""
                except Exception:
                    page_text = ""
                pages_text[idx] = page_text
    return pages_text


def _clean(s: str) -> str:
    return re.sub(r"[\t\r]+", " ", s)


def _normalize_moneda(raw: str) -> str:
    r = raw.strip().upper()
    if "PESO" in r:
        return "PESOS"
    if "DOLAR" in r or "U$S" in r or "USD" in r:
        return "USD"
    return r


def parse_allianz_auto(pdf_path: str) -> Tuple[PolicyData, List[str]]:
    pages = _extract_selected_pages_text(pdf_path)
    p1 = _clean(pages.get(1, ""))
    p2 = _clean(pages.get(2, ""))
    p32 = _clean(pages.get(32, ""))
    p33 = _clean(pages.get(33, ""))
    p34 = _clean(pages.get(34, ""))

    data = PolicyData()

    # Página 1 - Cliente (Tomador)
    cliente = None
    m = re.search(r"Nombre y Apellido\s*:?\s*(.+)", p1, flags=re.IGNORECASE)
    if m:
        cliente = m.group(1).strip()
    data.cliente = cliente

    # Página 1 - Productor / Razón social
    productor = None
    for pattern in [
        r"Nombre\s+y\s+Apellido\s+o\s+Raz[oó]n\s+Social\s*:?\s*(.+)",
        r"Productor\s*:?\s*(.+)",
    ]:
        m = re.search(pattern, p1, flags=re.IGNORECASE)
        if m:
            productor = m.group(1).strip()
            break
    data.productor = productor

    # Página 1 - Moneda del contrato (puede estar en misma línea o siguiente columna/línea)
    moneda = None
    m = re.search(
        r"Moneda\s+del\s+contrato\s*[:\.·\s]*([A-ZÁÉÍÓÚ$]{3,})",
        p1,
        flags=re.IGNORECASE,
    )
    if not m:
        m = re.search(
            r"Moneda\s+del\s+contrato[\s\.·:]*\n\s*([A-ZÁÉÍÓÚ$]{3,})",
            p1,
            flags=re.IGNORECASE,
        )
    if m:
        moneda = _normalize_moneda(m.group(1))
    if moneda:
        data.moneda = moneda

    # Página 1 - Número de póliza
    poliza = None
    m = re.search(r"n[uú]mero\s*de\s*p[oó]liza\s*:?\s*([A-Z0-9\-/\.]+)", p1, flags=re.IGNORECASE)
    if m:
        poliza = m.group(1).strip()
    data.numero_poliza = poliza

    # Página 1 - Fecha de emisión
    emision = None
    m = re.search(r"Lugar\s+y\s+Fecha\s+de\s+Emisi[oó]n[\s\n,]*([^\n]+\d{4})", p1, flags=re.IGNORECASE)
    if m:
        emision = extract_spanish_date(m.group(1)) or normalize_date(m.group(1))
    data.fecha_emision = emision

    # Página 2 - Vehículo
    anio = None
    m = re.search(r"A[nñ]o\s*:?\s*(\d{4})", p2, flags=re.IGNORECASE)
    if m:
        anio = int(m.group(1))
    data.anio = anio

    # Marca: tomar todo el resto de la línea después de 'Marca', y cortar si aparecen otros rótulos
    marca = None
    m = re.search(r"(?mi)^\s*Marca\s*: ?\s*([^\n]+)", p2)
    if not m:
        m = re.search(r"Marca\s*:?\s*([^\n]+)", p2, flags=re.IGNORECASE)
    if m:
        raw_marca = m.group(1).strip()
        raw_marca = re.split(r"\b(?:A[ñn]o|Anio|Patente|Dominio|Chasis|VIN|Motor)\b", raw_marca)[0].strip()
        marca = raw_marca.rstrip("·.:")
    data.marca = marca

    # Por ahora no extraemos modelo/vehiculo/combustible
    data.modelo = None
    data.vehiculo = None
    data.combustible = None

    patente = data.patente
    m = re.search(r"(?:Patente|Dominio)\s*:?\s*([A-Z0-9\- ]{5,10})", p2, flags=re.IGNORECASE)
    if m:
        patente = normalize_plate(m.group(1))
    data.patente = patente

    chasis = data.chasis
    m = re.search(r"(?:Chasis|VIN)\s*:?\s*([A-Z0-9]+)", p2, flags=re.IGNORECASE)
    if m:
        chasis = m.group(1).strip()
    data.chasis = chasis

    motor = data.motor
    m = re.search(r"Motor\s*:?\s*([A-Z0-9]+)", p2, flags=re.IGNORECASE)
    if m:
        motor = m.group(1).strip()
    data.motor = motor

    prima = None
    m = re.search(r"\bprima\b\s*:?\s*([^\n]+)", p2, flags=re.IGNORECASE)
    if m:
        prima = normalize_money(m.group(1))
    data.prima_total = prima

    premio = None
    m = re.search(r"\bpremio\b\s*:?\s*([^\n]+)", p2, flags=re.IGNORECASE)
    if m:
        premio = normalize_money(m.group(1))
    data.premio_total = premio

    # Tipo IVA: buscar en p32, luego p34
    tipo_iva = None
    for section in (p32, p34):
        if tipo_iva:
            break
        m = re.search(r"Condici[oó]n\s*I\.V\.A\.?\s*:?\s*([^\n]+)", section, flags=re.IGNORECASE)
        if m:
            tipo_iva = m.group(1).strip()
    data.tipo_iva = tipo_iva

    # Inicio vigencia: buscar cerca de 'Vigencia' en p1, p34, p33, luego p32
    inicio_vigencia = None
    for section in (p1, p34, p33, p32):
        if inicio_vigencia:
            break
        m = re.search(r"Vigencia[\s\S]{0,200}?(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})", section, flags=re.IGNORECASE)
        if m:
            inicio_vigencia = normalize_date(m.group(1))
    data.inicio_vigencia = inicio_vigencia

    # Vencimiento primera cuota: buscar después de 'plan de pago' en p34, luego p32
    vto_primera = None
    for section in (p34, p32):
        if vto_primera:
            break
        m = re.search(r"plan\s+de\s+pago[\s\S]*?(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})", section, flags=re.IGNORECASE)
        if m:
            vto_primera = normalize_date(m.group(1))
    # Fallback: buscar línea que contenga 'Vencimiento 1' o '1ra' con fecha
    if not vto_primera:
        for section in (p34, p32):
            m = re.search(r"Vencimiento\s*(?:1(?:ra|ª|°)?|primera)\s*[^\d]*(\d{1,2}[\-/\.]\d{1,2}[\-/\.]\d{2,4})", section, flags=re.IGNORECASE)
            if m:
                vto_primera = normalize_date(m.group(1))
                break
    data.vencimiento_primera_cuota = vto_primera

    # Valores fijos de este parser/aseguradora
    data.aseguradora = "ALLIANZ"
    data.riesgo = "AUTO"
    data.tipo_contacto_ssn = "PRESENCIAL"
    data.tipo_renovacion = "AUTOMATICA"
    data.clausula_ajuste = 0
    data.cant_cuotas = 1
    data.tipo_vigencia = "anual"
    data.refacturacion = "mensual"

    missing = [
        key
        for key, value in data.to_dict().items()
        if value in (None, "", []) and key not in ("modelo",)
    ]

    return data, missing
