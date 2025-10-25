from automation_broker.fillers.absanet import load_mapping, AbsaNetForm
from automation_broker.models import PolicyData


def test_build_fill_plan_basic() -> None:
    mapping = load_mapping("/home/nishy/Desktop/automatizacion broker/src/automation_broker/fillers/mapping.yaml")
    data = PolicyData(
        cliente="Juan Perez",
        productor="ACME",
        tipo_iva="CONSUMIDOR FINAL",
        marca="FORD - FIESTA",
        anio=2015,
        patente="AA123BB",
        chasis="ABC123",
        motor="XYZ789",
        prima_total=1000.0,
        premio_total=1200.0,
        numero_poliza="123",
        fecha_emision="01/01/2025",
        inicio_vigencia="01/02/2025",
        vencimiento_primera_cuota="01/02/2025",
    )

    dummy = AbsaNetForm.__new__(AbsaNetForm)  # type: ignore
    plan = AbsaNetForm.build_fill_plan(dummy, data, mapping)  # type: ignore

    keys = [k for k, _, _ in plan]
    assert "cliente" in keys
    assert "marca" in keys
    assert "numero_poliza" in keys
