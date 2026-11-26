"""Convierte la base ancha de trabajo (una fila por programa, columnas por
año) al formato largo de staging que recibe el normalizador.

Columnas que reconoce para cada año AAAA:
  AAAA                       precio de derechos pecuniarios
  Periodo reportado AAAA     unidad de ese precio
  PRC_SNIES AAAA             precio SNIES
  FUENTE_AAAA / CONFIANZA_AAAA   trazabilidad (opcional)
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from .io import a_numero, leer_csv
from .normalizar import FUENTE_DP, FUENTE_SNIES


def leer_base(ruta: str | Path) -> pd.DataFrame:
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(ruta, dtype=object)
    else:
        df = leer_csv(ruta)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def ancho_a_largo(df: pd.DataFrame, periodos: pd.DataFrame) -> pd.DataFrame:
    id_por_anio = dict(zip(periodos["ANIO"], periodos["ID_PRD"]))
    anios = sorted(int(c) for c in df.columns if re.fullmatch(r"\d{4}", str(c)) and int(c) in id_por_anio)
    filas = []
    base = df[["ID_IES", "ID_PRGRM"]].copy()
    for anio in anios:
        id_prd = id_por_anio[anio]
        dp = base.copy()
        dp["ID_PRD"] = id_prd
        dp["PRC"] = a_numero(df[str(anio)])
        dp["FUENTE"] = FUENTE_DP
        dp["PRD_PRC"] = df.get(f"Periodo reportado {anio}")
        dp["ARCHIVO_FUENTE"] = df.get(f"FUENTE_{anio}")
        dp["CONFIANZA_ORIGEN"] = df.get(f"CONFIANZA_{anio}")
        filas.append(dp[dp["PRC"] > 0])
        col_snies = f"PRC_SNIES {anio}"
        if col_snies in df.columns:
            sn = base.copy()
            sn["ID_PRD"] = id_prd
            sn["PRC"] = a_numero(df[col_snies])
            sn["FUENTE"] = FUENTE_SNIES
            sn["PRD_PRC"] = df.get("PERIODICIDAD")
            filas.append(sn[sn["PRC"] > 0])
    largo = pd.concat(filas, ignore_index=True)
    largo["ID_IES"] = a_numero(largo["ID_IES"])
    largo["ID_PRGRM"] = a_numero(largo["ID_PRGRM"])
    largo = largo[largo["ID_PRGRM"].notna()]
    return largo.drop_duplicates(["ID_PRGRM", "ID_PRD", "FUENTE"], keep="first").reset_index(drop=True)
