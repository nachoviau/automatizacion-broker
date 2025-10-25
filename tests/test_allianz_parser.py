import os

from automation_broker.parsers.allianz_auto import parse_allianz_auto


PDF_PATH = "/home/nishy/Desktop/automatizacion broker/auto_allianz.pdf"


essential_keys = {
    "cliente",
    "aseguradora",
    "moneda",
    "numero_poliza",
}


def test_pdf_exists() -> None:
    assert os.path.exists(PDF_PATH), "El PDF de ejemplo no existe en la ruta esperada"


def test_parse_returns_policy_and_missing() -> None:
    data, missing = parse_allianz_auto(PDF_PATH)
    assert data.aseguradora == "ALLIANZ"
    assert isinstance(missing, list)


def test_partial_success_allowed() -> None:
    data, missing = parse_allianz_auto(PDF_PATH)
    data_dict = data.to_dict()
    present = {k for k, v in data_dict.items() if v}
    assert essential_keys & present, "Debe extraer al menos algún campo esencial"
