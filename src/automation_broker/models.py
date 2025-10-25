from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any


@dataclass
class PolicyData:
    cliente: Optional[str] = None
    productor: Optional[str] = None
    aseguradora: Optional[str] = None #FIJO
    riesgo: Optional[str] = None #FIJO
    moneda: Optional[str] = None
    tipo_contacto_ssn: Optional[str] = None #FIJO
    tipo_iva: Optional[str] = None
    tipo_renovacion: Optional[str] = None #FIJO
    clausula_ajuste: Optional[int] = None #FIJO
    cant_cuotas: Optional[int] = None #FIJO
    tipo_vigencia: Optional[str] = None #FIJO
    refacturacion: Optional[str] =  None #FIJO
    inicio_vigencia: Optional[str] = None

    anio: Optional[int] = None
    marca: Optional[str] = None
    modelo: Optional[str] = None
    combustible: Optional[str] = None
    vehiculo: Optional[str] = None
    patente: Optional[str] = None
    chasis: Optional[str] = None
    motor: Optional[str] = None

    prima_total: Optional[float] = None
    premio_total: Optional[float] = None

    numero_poliza: Optional[str] = None
    fecha_emision: Optional[str] = None
    vencimiento_primera_cuota: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
