"""Catálogo de fuentes: una fila por IES y año con dónde se publica el
acuerdo/resolución de derechos pecuniarios y el estado de la descarga.

Es el insumo del descargador y la bitácora de qué falta por conseguir.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import a_numero, escribir_csv, leer_csv

COLUMNAS = [
    "CODIGO_INSTITUCION", "IDS_IES", "NOMBRE_INSTITUCION", "ANIO", "TIPO",
    "URL_PAGINA", "URL_DOCUMENTO", "ACTO_ADMINISTRATIVO", "ARCHIVO_LOCAL",
    "SHA256", "FECHA_DESCARGA", "ESTADO", "EXTRACTOR", "NOTAS",
    "PROGRAMAS_ACTIVOS", "FUENTES_ANIO_ANTERIOR",
]

ESTADOS = ("PENDIENTE", "URL_IDENTIFICADA", "DESCARGADO", "EXTRAIDO", "VALIDADO", "NO_PUBLICADO", "ERROR")


def catalogo_inicial(base: pd.DataFrame, anio: int, anio_ref: int | None = None) -> pd.DataFrame:
    """Arma el catálogo para `anio` a partir de la base ancha de trabajo.

    Una fila por institución (CÓDIGO_INSTITUCIÓN_PADRE), porque el acuerdo de
    derechos pecuniarios se publica por institución; IDS_IES lista los ID_IES
    del aplicativo (seccionales/sedes) que cubre. Incluye cuántos programas
    activos tiene y qué archivos se usaron como fuente en `anio_ref`.
    """
    anio_ref = anio_ref or anio - 1
    b = base.copy()
    b.columns = [str(c).strip() for c in b.columns]
    b["ID_IES"] = a_numero(b["ID_IES"]).astype("Int64")
    col_cod = "CÓDIGO_INSTITUCIÓN_PADRE" if "CÓDIGO_INSTITUCIÓN_PADRE" in b.columns else "ID_IES"
    b["_cod"] = a_numero(b[col_cod]).astype("Int64")
    estado = b.get("ESTADO_OFICIAL", b.get("ESTADO"))
    b["_activo"] = estado.astype(str).str.strip().str.lower().eq("activo") if estado is not None else True
    col_f = f"FUENTE_{anio_ref}"
    g = b.groupby("_cod")

    def _unir(s):
        return " | ".join(sorted({str(x).strip() for x in s.dropna() if str(x).strip() and str(x).strip() != "nan"}))

    cat = pd.DataFrame({
        "IDS_IES": g["ID_IES"].agg(lambda s: " ".join(str(x) for x in sorted(s.dropna().unique()))),
        "NOMBRE_INSTITUCION": g["NOMBRE_INSTITUCIÓN"].agg(lambda s: s.mode().iat[0] if len(s.mode()) else "")
        if "NOMBRE_INSTITUCIÓN" in b else "",
        "PROGRAMAS_ACTIVOS": g["_activo"].sum().astype(int),
    })
    if col_f in b.columns:
        cat["FUENTES_ANIO_ANTERIOR"] = g[col_f].agg(_unir)
    cat = cat.reset_index().rename(columns={"_cod": "CODIGO_INSTITUCION"})
    cat["ANIO"] = anio
    cat["ESTADO"] = "PENDIENTE"
    for c in COLUMNAS:
        if c not in cat.columns:
            cat[c] = ""
    return cat[COLUMNAS].sort_values("PROGRAMAS_ACTIVOS", ascending=False).reset_index(drop=True)


def fusionar(existente: Path, nuevo: pd.DataFrame) -> pd.DataFrame:
    """Agrega al catálogo existente las IES/años que falten, sin pisar lo ya diligenciado."""
    if not existente.exists() or existente.stat().st_size == 0:
        return nuevo
    viejo = leer_csv(existente)
    if viejo.empty:
        return nuevo
    clave = viejo["CODIGO_INSTITUCION"].astype(str) + "|" + viejo["ANIO"].astype(str)
    nuevo_clave = nuevo["CODIGO_INSTITUCION"].astype(str) + "|" + nuevo["ANIO"].astype(str)
    return pd.concat([viejo, nuevo[~nuevo_clave.isin(clave)]], ignore_index=True)


def guardar(cat: pd.DataFrame, ruta: Path) -> None:
    escribir_csv(cat, ruta)
