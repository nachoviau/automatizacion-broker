# Automatización de carga de pólizas (Allianz Auto)

Proyecto para extraer datos de PDFs de pólizas de Allianz (autos) y preparar la carga en AbsaNet.

## Requisitos
- Python 3.10+
- Firefox (para Selenium en el futuro)

## Instalación
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecutar tests
```bash
pytest
```

## Uso del parser (CLI)
```bash
python -m automation_broker.cli parse --pdf "/home/nishy/Desktop/automatizacion broker/auto_allianz.pdf" --out salida.json
```

El comando imprime un JSON con `data` (campos extraídos normalizados) y `missing` (campos faltantes para completar manualmente).

## Próximos pasos
- Completar Page Objects de Selenium para AbsaNet usando IDs reales.
- Mejorar regex del parser según más muestras de PDFs.
- Soporte para Chrome (Windows) y ejecución guiada.
