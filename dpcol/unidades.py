"""Unidades de cobro y su conversión a precio equivalente semestral.

`PRC_HMGNZD` en el T08 es el precio equivalente a un semestre (6 meses).
Las reglas reproducen lo que hacía la base original (verificado contra
T08_PRECIOS.csv: Anual ÷2, Cuatrimestral ×1,5, Trimestral ×2,
Crédito × créditos/períodos, Total ÷ períodos), y agregan el ajuste por la
periodicidad del programa cuando no es semestral.
"""
from __future__ import annotations

import math
import unicodedata

# Meses que dura cada período según su nombre.
MESES_POR_PERIODO = {
    "Semestral": 6,
    "Anual": 12,
    "Cuatrimestral": 4,
    "Trimestral": 3,
    "Bimestral": 2,
    "Mensual": 1,
}

# Unidades de cobro reconocidas en PRD_PRC.
UNIDADES = (
    "Semestral", "Anual", "Cuatrimestral", "Trimestral", "Bimestral", "Mensual",
    "Credito", "Total", "Cohorte", "Periodo",
)

_ALIAS = {
    "semestral": "Semestral", "semestre": "Semestral", "semestres": "Semestral",
    "anual": "Anual", "ano": "Anual", "anio": "Anual", "anualidad": "Anual",
    "cuatrimestral": "Cuatrimestral", "cuatrimestre": "Cuatrimestral",
    "trimestral": "Trimestral", "trimestre": "Trimestral",
    "bimestral": "Bimestral", "bimensual": "Bimestral", "bimestre": "Bimestral",
    "mensual": "Mensual", "mes": "Mensual",
    "credito": "Credito", "creditos": "Credito", "por credito": "Credito",
    "total": "Total", "valor total": "Total", "programa": "Total",
    "cohorte": "Cohorte",
    "periodo": "Periodo", "periodos": "Periodo", "periodo academico": "Periodo",
}


def _plano(texto) -> str:
    if texto is None or (isinstance(texto, float) and math.isnan(texto)):
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(t.lower().split())


def unidad_canonica(texto) -> str | None:
    """'Crédito ' -> 'Credito'; devuelve None si no se reconoce."""
    return _ALIAS.get(_plano(texto))


def meses_periodicidad(periodicidad) -> tuple[float, bool]:
    """Meses de un período del programa. Devuelve (meses, supuesto).

    Si la periodicidad no se conoce ('Periodos', 'Sin definir', vacío) se
    asume semestral y supuesto=True para dejarlo marcado.
    """
    u = unidad_canonica(periodicidad)
    if u in MESES_POR_PERIODO:
        return float(MESES_POR_PERIODO[u]), False
    return 6.0, True


def factor_semestral(
    unidad: str,
    creditos: float = math.nan,
    periodos: float = math.nan,
    periodicidad_programa=None,
) -> tuple[float, str, bool]:
    """Factor que multiplica el precio original para llevarlo a semestre.

    Devuelve (factor, descripción de la regla, supuesto). factor=nan si no se
    puede calcular (p. ej. precio por crédito sin número de créditos).
    """
    meses_prog, supuesto = meses_periodicidad(periodicidad_programa)
    if unidad in MESES_POR_PERIODO:
        f = 6.0 / MESES_POR_PERIODO[unidad]
        return f, f"{unidad}: x6/{MESES_POR_PERIODO[unidad]}", False
    if unidad == "Periodo":
        return 6.0 / meses_prog, f"Periodo del programa ({meses_prog:g} meses)", supuesto
    if unidad == "Credito":
        if not (creditos > 0 and periodos > 0):
            return math.nan, "Credito sin créditos/períodos en el maestro", supuesto
        f = (creditos / periodos) * (6.0 / meses_prog)
        return f, f"Credito: x{creditos:g} créditos/{periodos:g} períodos", supuesto
    if unidad in ("Total", "Cohorte"):
        if not periodos > 0:
            return math.nan, f"{unidad} sin períodos en el maestro", supuesto
        semestres = periodos * meses_prog / 6.0
        return 1.0 / semestres, f"{unidad}: /{semestres:g} semestres", supuesto
    return math.nan, f"Unidad no reconocida: {unidad}", False
