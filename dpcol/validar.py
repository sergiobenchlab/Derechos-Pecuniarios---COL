"""Validaciones posteriores a la normalización y reporte de cobertura.

Las validaciones solo marcan; nunca cambian valores.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .normalizar import FUENTE_DP


def variacion_anual(d: pd.DataFrame, var_min: float = -0.05, var_max: float = 0.25) -> pd.DataFrame:
    """Agrega VAR_ANUAL (contra el año anterior, misma fuente y programa) y
    ALERTA_VARIACION si está por fuera de [var_min, var_max].

    El rango por defecto refleja que los incrementos típicos 2024-2026 están
    alrededor de IPC + 1-3 puntos (mediana ~5,5 %).
    """
    d = d.copy()
    col = np.where(d["PRC_HMGNZD"].notna(), d["PRC_HMGNZD"], d["PRC"]).astype(float)
    d["_v"] = col
    d = d.sort_values(["ID_PRGRM", "FUENTE", "ID_PRD"], kind="stable")
    prev = d.groupby(["ID_PRGRM", "FUENTE"])["_v"].shift(1)
    prev_anio = d.groupby(["ID_PRGRM", "FUENTE"])["ANIO"].shift(1)
    d["VAR_ANUAL"] = d["_v"] / prev - 1
    # solo se compara con el año inmediatamente anterior
    d.loc[(d["ANIO"] - prev_anio) != 1, "VAR_ANUAL"] = np.nan
    d["ALERTA_VARIACION"] = d["VAR_ANUAL"].notna() & ~d["VAR_ANUAL"].between(var_min, var_max)
    return d.drop(columns="_v").sort_index()


def resumen_estados(d: pd.DataFrame) -> pd.DataFrame:
    dp = d[d["FUENTE"] == FUENTE_DP]
    t = pd.crosstab(dp["ESTADO"], dp["ANIO"], margins=True, margins_name="TOTAL")
    return t.reset_index()


def cobertura_por_ies(d: pd.DataFrame) -> pd.DataFrame:
    g = d.groupby(["ID_IES", "ANIO", "FUENTE"])["ID_PRGRM"].nunique().unstack("FUENTE").fillna(0).astype(int)
    g.columns = [f"PROGRAMAS_{c.replace(' ', '_')}" for c in g.columns]
    revisar = (
        d[(d["FUENTE"] == FUENTE_DP) & d["ESTADO"].str.startswith(("REVISAR", "ERROR"))]
        .groupby(["ID_IES", "ANIO"]).size().rename("FILAS_A_REVISAR")
    )
    alertas = d[d["ALERTA_VARIACION"]].groupby(["ID_IES", "ANIO"]).size().rename("ALERTAS_VARIACION") \
        if "ALERTA_VARIACION" in d.columns else pd.Series(dtype=int, name="ALERTAS_VARIACION")
    out = g.join(revisar, how="left").join(alertas, how="left").fillna(0)
    return out.reset_index()


def a_revisar(d: pd.DataFrame) -> pd.DataFrame:
    m = d["ESTADO"].str.startswith(("REVISAR", "ERROR", "UNIDAD_"))
    if "ALERTA_VARIACION" in d.columns:
        m |= d["ALERTA_VARIACION"]
    return d[m & (d["FUENTE"] == FUENTE_DP)]
