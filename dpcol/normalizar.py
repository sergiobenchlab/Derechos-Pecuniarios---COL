"""Normalizador de precios a formato T08 con PRC_HMGNZD semestral.

Principio: el precio publicado por la universidad nunca se reemplaza por el
de SNIES. SNIES se usa solo como referencia para detectar unidades mal
etiquetadas (p. ej. un precio semestral marcado como "Total"). Cada fila
queda con la regla aplicada y un estado para auditoría.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .io import T08_COLUMNAS, a_numero
from .unidades import factor_semestral, meses_periodicidad, unidad_canonica

FUENTE_DP = "DERECHOS PECUNIARIOS"
FUENTE_SNIES = "SNIES"


@dataclass
class Parametros:
    # Rango de H/SNIES en el que se acepta la unidad declarada.
    rango_ok: tuple[float, float] = (0.6, 1.6)
    # Rango (más estrecho) que debe cumplir una unidad alternativa para
    # reinterpretar la declarada.
    rango_reinterpretar: tuple[float, float] = (0.8, 1.25)
    # Unidades que se prueban como alternativa.
    candidatas: tuple[str, ...] = (
        "Semestral", "Anual", "Credito", "Total", "Periodo", "Cuatrimestral", "Trimestral",
    )
    # Valores por fuera de estos límites se marcan como error de captura.
    prc_max: float = 500_000_000
    hmgnzd_min: float = 100_000
    hmgnzd_max: float = 150_000_000
    # Si True, también se llena PRC_HMGNZD en filas SNIES (el T08 histórico
    # lo deja vacío).
    homogeneizar_snies: bool = False
    unidad_por_defecto: str = "Semestral"
    extras: dict = field(default_factory=dict)


def _preparar(df: pd.DataFrame, periodos: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for c in ("ID_IES", "ID_PRGRM", "ID_PRD"):
        d[c] = a_numero(d[c]).astype("Int64")
    d["PRC_ORIGINAL_TXT"] = d["PRC"].astype(str)
    d["PRC"] = a_numero(d["PRC"])
    d["FUENTE"] = d["FUENTE"].astype(str).str.strip().str.upper()
    d.loc[d["FUENTE"].str.contains("SNIES"), "FUENTE"] = FUENTE_SNIES
    d.loc[d["FUENTE"].str.contains("PECUNIARIO"), "FUENTE"] = FUENTE_DP
    fch = periodos.set_index("ID_PRD")["FCH_INC_PRD"]
    if "FCH_INC_PRD" not in d.columns:
        d["FCH_INC_PRD"] = np.nan
    d["FCH_INC_PRD"] = a_numero(d["FCH_INC_PRD"])
    falta = d["FCH_INC_PRD"].isna()
    d.loc[falta, "FCH_INC_PRD"] = d.loc[falta, "ID_PRD"].map(fch).astype(float)
    anio = periodos.set_index("ID_PRD")["ANIO"]
    d["ANIO"] = d["ID_PRD"].map(anio)
    d["PRD_PRC_ORIGINAL"] = d.get("PRD_PRC", pd.Series(index=d.index, dtype=object))
    d["UNIDAD_DECLARADA"] = d["PRD_PRC_ORIGINAL"].map(unidad_canonica)
    return d


def _referencia_snies(d: pd.DataFrame) -> pd.DataFrame:
    """Precio SNIES equivalente semestral por (ID_PRGRM, ID_PRD).

    El precio SNIES está expresado por período del programa, por eso se
    ajusta con la periodicidad del maestro (verificado: programas anuales
    tienen DP anual ≈ SNIES).
    """
    s = d[(d["FUENTE"] == FUENTE_SNIES) & d["PRC"].notna()]
    s = s.groupby(["ID_PRGRM", "ID_PRD"], as_index=False).agg(
        PRC_SNIES=("PRC", "mean"), _per=("PERIODICIDAD", "first")
    )
    s["PRC_SNIES_SEM"] = [p * 6.0 / meses_periodicidad(x)[0] for p, x in zip(s["PRC_SNIES"], s["_per"])]
    return s.drop(columns="_per")


def _convertir(prc, unidad, cred, per, periodicidad):
    if unidad is None or (isinstance(unidad, float) and math.isnan(unidad)):
        return math.nan, "Sin unidad", False
    return factor_semestral(unidad, cred, per, periodicidad)


def normalizar(
    staging: pd.DataFrame,
    maestro: pd.DataFrame,
    periodos: pd.DataFrame,
    params: Parametros | None = None,
) -> pd.DataFrame:
    """Devuelve la base completa con columnas T08 + columnas de auditoría."""
    p = params or Parametros()
    d = _preparar(staging, periodos)
    cols_m = [c for c in ("ID_PRGRM", "CREDITOS", "PERIODOS", "PERIODICIDAD", "NIVEL", "NOMBRE_PROGRAMA") if c in maestro.columns]
    m = maestro[cols_m].copy()
    m["ID_PRGRM"] = m["ID_PRGRM"].astype("Int64")
    d = d.drop(columns=[c for c in cols_m if c != "ID_PRGRM" and c in d.columns]).merge(m, on="ID_PRGRM", how="left")
    d["EN_MAESTRO"] = d["CREDITOS"].notna() | d["PERIODOS"].notna() | d["PERIODICIDAD"].notna()
    d = d.merge(_referencia_snies(d), on=["ID_PRGRM", "ID_PRD"], how="left")

    lo_ok, hi_ok = p.rango_ok
    lo_re, hi_re = p.rango_reinterpretar
    salida = {k: [] for k in ("UNIDAD_APLICADA", "FACTOR", "REGLA", "SUPUESTO_PERIODICIDAD", "PRC_HMGNZD", "RATIO_SNIES", "ESTADO")}

    for r in d.itertuples(index=False):
        prc = r.PRC
        cred, per, peri = r.CREDITOS, r.PERIODOS, r.PERIODICIDAD
        unidad = r.UNIDAD_DECLARADA
        estado = "OK"
        notas = []
        if r.FUENTE == FUENTE_SNIES:
            f = 6.0 / meses_periodicidad(peri)[0]
            h = prc * f if p.homogeneizar_snies else math.nan
            salida["UNIDAD_APLICADA"].append("Periodo")
            salida["FACTOR"].append(f)
            salida["REGLA"].append("SNIES: precio por período del programa")
            salida["SUPUESTO_PERIODICIDAD"].append(meses_periodicidad(peri)[1])
            salida["PRC_HMGNZD"].append(h)
            salida["RATIO_SNIES"].append(math.nan)
            salida["ESTADO"].append("SNIES" if not math.isnan(prc) else "SIN_PRECIO")
            continue

        if math.isnan(prc):
            for k, v in (("UNIDAD_APLICADA", unidad), ("FACTOR", math.nan), ("REGLA", "Sin precio"),
                         ("SUPUESTO_PERIODICIDAD", False), ("PRC_HMGNZD", math.nan),
                         ("RATIO_SNIES", math.nan), ("ESTADO", "SIN_PRECIO")):
                salida[k].append(v)
            continue

        if unidad is None:
            unidad = p.unidad_por_defecto
            notas.append(f"unidad '{r.PRD_PRC_ORIGINAL}' no reconocida, se asume {unidad}")
            estado = "UNIDAD_ASUMIDA"

        f, regla, supuesto = _convertir(prc, unidad, cred, per, peri)
        h = prc * f
        ref = r.PRC_SNIES_SEM
        ratio = h / ref if (ref and not math.isnan(ref) and not math.isnan(h)) else math.nan

        if prc > p.prc_max:
            estado = "ERROR_VALOR"
            notas.append(f"PRC > {p.prc_max:,.0f}: posible error de separadores")
        elif math.isnan(f):
            estado = "REVISAR_SIN_MAESTRO"
        elif not math.isnan(ratio) and not (lo_ok <= ratio <= hi_ok):
            mejor = None
            for u in p.candidatas:
                if u == unidad:
                    continue
                fu, ru, su = factor_semestral(u, cred, per, peri)
                if math.isnan(fu):
                    continue
                rr = prc * fu / ref
                dist = abs(math.log(rr))
                if mejor is None or dist < mejor[0]:
                    mejor = (dist, u, fu, ru, su, rr)
            if mejor and lo_re <= mejor[5] <= hi_re:
                _, u, f, regla_u, supuesto, ratio = mejor
                notas.append(f"declarada {unidad} daba H/SNIES={h / ref:.2f}; se reinterpreta como {u}")
                regla = regla_u
                unidad = u
                h = prc * f
                estado = "UNIDAD_REINTERPRETADA"
            else:
                estado = "REVISAR_RATIO_SNIES"
        elif math.isnan(ratio):
            estado = "SIN_REFERENCIA_SNIES" if estado == "OK" else estado

        if estado in ("OK", "SIN_REFERENCIA_SNIES", "UNIDAD_ASUMIDA", "UNIDAD_REINTERPRETADA") and not math.isnan(h):
            if not (p.hmgnzd_min <= h <= p.hmgnzd_max):
                estado = "REVISAR_RANGO"
                notas.append(f"PRC_HMGNZD fuera de [{p.hmgnzd_min:,.0f}, {p.hmgnzd_max:,.0f}]")
        if supuesto:
            notas.append("periodicidad del programa desconocida, se asume semestral")

        salida["UNIDAD_APLICADA"].append(unidad)
        salida["FACTOR"].append(f)
        salida["REGLA"].append(regla + ("; " + "; ".join(notas) if notas else ""))
        salida["SUPUESTO_PERIODICIDAD"].append(supuesto)
        salida["PRC_HMGNZD"].append(h)
        salida["RATIO_SNIES"].append(ratio)
        salida["ESTADO"].append(estado)

    for k, v in salida.items():
        d[k] = v
    # PRD_PRC conserva la unidad con la que se interpretó el precio original.
    d["PRD_PRC"] = np.where(d["FUENTE"] == FUENTE_DP, d["UNIDAD_APLICADA"], d["PRD_PRC_ORIGINAL"])
    d.loc[d["ESTADO"].isin(["ERROR_VALOR"]), "PRC_HMGNZD"] = np.nan

    extras = [c for c in d.columns if c not in T08_COLUMNAS]
    orden_audit = [
        "ANIO", "NOMBRE_PROGRAMA", "NIVEL", "PRD_PRC_ORIGINAL", "UNIDAD_DECLARADA", "UNIDAD_APLICADA",
        "FACTOR", "CREDITOS", "PERIODOS", "PERIODICIDAD", "PRC_SNIES", "PRC_SNIES_SEM", "RATIO_SNIES",
        "ESTADO", "REGLA", "SUPUESTO_PERIODICIDAD", "EN_MAESTRO", "PRC_ORIGINAL_TXT",
    ]
    resto = [c for c in extras if c not in orden_audit]
    return d[T08_COLUMNAS + [c for c in orden_audit if c in d.columns] + resto]
