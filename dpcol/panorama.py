"""Panorama SNIES vs. derechos pecuniarios.

Cruza, por programa, el costo de matrícula que las IES reportan a SNIES
(consulta pública HECAA, campo COSTO_MATRÍCULA_ESTUD_NUEVOS) con el precio de
derechos pecuniarios de la base normalizada, y resume por institución junto
con el estado de validación del documento fuente.

SNIES no es el precio real (lo reporta la IES, a veces desactualizado o para
estudiantes nuevos), pero sirve de referencia para dimensionar:
  - cobertura: programas activos en SNIES vs. programas con precio DP;
  - precios DP idénticos a SNIES (posible copia de SNIES en la base);
  - precios DP proyectados (con decimales);
  - diferencias grandes DP vs. SNIES.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .io import a_numero, leer_csv
from .normalizar import FUENTE_DP, FUENTE_SNIES
from .unidades import meses_periodicidad

TOL_IGUAL = 0.002     # |DP/SNIES - 1| <= 0,2 % -> idéntico
TOL_CERCA = 0.10      # dentro de ±10 %
TOL_LEJOS = 0.20      # fuera de ±20 % -> diferencia alta


def leer_hecaa(ruta: str | Path) -> pd.DataFrame:
    """Lee la descarga 'Programas.xlsx' de la consulta pública de SNIES (HECAA)."""
    df = pd.read_excel(ruta, sheet_name="Programas", dtype=object)
    df.columns = [str(c).strip() for c in df.columns]
    out = pd.DataFrame({
        "CODIGO_SNIES": a_numero(df["CÓDIGO_SNIES_DEL_PROGRAMA"]),
        "CODIGO_PADRE": a_numero(df["CÓDIGO_INSTITUCIÓN_PADRE"]),
        "CODIGO_INSTITUCION": a_numero(df["CÓDIGO_INSTITUCIÓN"]),
        "INSTITUCION_SNIES": df["NOMBRE_INSTITUCIÓN"],
        "SECTOR": df.get("SECTOR"),
        "PROGRAMA_SNIES": df["NOMBRE_DEL_PROGRAMA"],
        "ESTADO_PROGRAMA_SNIES": df["ESTADO_PROGRAMA"],
        "NIVEL_SNIES": df.get("NIVEL_DE_FORMACIÓN"),
        "MODALIDAD_SNIES": df.get("MODALIDAD"),
        "PERIODICIDAD_SNIES": df.get("PERIODICIDAD"),
        "COSTO_SNIES": a_numero(df["COSTO_MATRÍCULA_ESTUD_NUEVOS"]),
    })
    out = out[out["CODIGO_SNIES"].notna()].copy()
    for c in ("CODIGO_SNIES", "CODIGO_PADRE", "CODIGO_INSTITUCION"):
        out[c] = out[c].astype("Int64")
    out.loc[out["COSTO_SNIES"] <= 0, "COSTO_SNIES"] = np.nan
    out["COSTO_SNIES_SEM"] = [
        c * 6.0 / meses_periodicidad(p)[0] if pd.notna(c) else np.nan
        for c, p in zip(out["COSTO_SNIES"], out["PERIODICIDAD_SNIES"])
    ]
    return out.drop_duplicates("CODIGO_SNIES")


def _mapa_base(base: pd.DataFrame) -> pd.DataFrame:
    b = base.copy()
    b.columns = [str(c).strip() for c in b.columns]
    m = pd.DataFrame({
        "ID_PRGRM": a_numero(b["ID_PRGRM"]),
        "CODIGO_SNIES": a_numero(b["CÓDIGO_SNIES_DEL_PROGRAMA"]),
        "CODIGO_PADRE": a_numero(b["CÓDIGO_INSTITUCIÓN_PADRE"]),
        "ESTADO_BASE": b.get("ESTADO_OFICIAL", b.get("ESTADO")),
    })
    m = m[m["ID_PRGRM"].notna()].drop_duplicates("ID_PRGRM")
    for c in ("ID_PRGRM", "CODIGO_SNIES", "CODIGO_PADRE"):
        m[c] = m[c].astype("Int64")
    return m


def _precios_anio(auditoria: pd.DataFrame, anio: int) -> pd.DataFrame:
    a = auditoria.copy()
    a["ANIO"] = a_numero(a["ANIO"])
    a = a[a["ANIO"] == anio]
    a["ID_PRGRM"] = a_numero(a["ID_PRGRM"]).astype("Int64")
    dp = a[a["FUENTE"] == FUENTE_DP]
    sn = a[a["FUENTE"] == FUENTE_SNIES]
    dec = dp["PRC_CON_DECIMALES"].astype(str).str.lower().isin(["true", "1", "verdadero"])
    dpf = pd.DataFrame({
        "ID_PRGRM": dp["ID_PRGRM"],
        "DP_PRC": a_numero(dp["PRC"]),
        "DP_SEM": a_numero(dp["PRC_HMGNZD"]),
        "DP_UNIDAD": dp["PRD_PRC_ORIGINAL"],
        "DP_DECIMALES": dec,
        "DP_ESTADO_NORMALIZACION": dp["ESTADO"],
    }).drop_duplicates("ID_PRGRM")
    snf = pd.DataFrame({"ID_PRGRM": sn["ID_PRGRM"], "SNIES_BASE": a_numero(sn["PRC"])}).drop_duplicates("ID_PRGRM")
    return dpf.merge(snf, on="ID_PRGRM", how="outer")


def _clase(r) -> str:
    if pd.isna(r.DP_SEM):
        return "SIN_DP"
    if pd.isna(r.COSTO_SNIES_SEM):
        return "SIN_SNIES"
    if r.DP_DECIMALES:
        return "DP_PROYECTADO"
    d = abs(r.RATIO_DP_SNIES - 1)
    if d <= TOL_IGUAL:
        return "DP_IGUAL_SNIES"
    if d <= TOL_CERCA:
        return "DP_CERCA_SNIES"
    if d <= TOL_LEJOS:
        return "DP_DIFERENCIA_MEDIA"
    return "DP_DIFERENCIA_ALTA"


def panorama(
    hecaa: pd.DataFrame,
    base: pd.DataFrame,
    auditoria: pd.DataFrame,
    validacion_instituciones: pd.DataFrame | None,
    anio: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (por_programa, por_institucion) para las instituciones del universo Benchlab."""
    mapa = _mapa_base(base)
    precios = _precios_anio(auditoria, anio)
    p = mapa.merge(precios, on="ID_PRGRM", how="left")
    p = p.merge(hecaa.drop(columns=["CODIGO_PADRE"]), on="CODIGO_SNIES", how="left")
    p["RATIO_DP_SNIES"] = p["DP_SEM"] / p["COSTO_SNIES_SEM"]
    p["SNIES_CAMBIO_VS_BASE"] = (p["COSTO_SNIES"] / p["SNIES_BASE"] - 1).where(p["SNIES_BASE"] > 0)
    p["ACTIVO_SNIES"] = p["ESTADO_PROGRAMA_SNIES"].astype(str).str.lower().str.startswith("activ")
    p["CLASE"] = [_clase(r) for r in p.itertuples(index=False)]

    universo = set(p["CODIGO_PADRE"].dropna())
    h = hecaa[hecaa["CODIGO_PADRE"].isin(universo)]
    act = h[h["ESTADO_PROGRAMA_SNIES"].astype(str).str.lower().str.startswith("activ")]
    filas = []
    for cod, g in p.groupby("CODIGO_PADRE"):
        ga = g[g["ACTIVO_SNIES"]]
        hs = act[act["CODIGO_PADRE"] == cod]
        con_dp = ga["DP_SEM"].notna()
        comparables = ga[con_dp & ga["COSTO_SNIES_SEM"].notna()]
        cl = ga["CLASE"].value_counts()
        filas.append({
            "CODIGO_INSTITUCION": str(cod),
            "INSTITUCION": hs["INSTITUCION_SNIES"].mode().iat[0] if len(hs) else g["INSTITUCION_SNIES"].dropna().mode().iat[0] if g["INSTITUCION_SNIES"].notna().any() else "",
            "PROGRAMAS_ACTIVOS_SNIES": len(hs),
            "ACTIVOS_SNIES_CON_COSTO": int(hs["COSTO_SNIES"].notna().sum()),
            "ACTIVOS_SNIES_EN_BASE": int(hs["CODIGO_SNIES"].isin(g["CODIGO_SNIES"]).sum()),
            "ACTIVOS_CON_PRECIO_DP": int(con_dp.sum()),
            "COBERTURA_DP": round(con_dp.sum() / len(hs), 3) if len(hs) else np.nan,
            "DP_IGUAL_SNIES": int(cl.get("DP_IGUAL_SNIES", 0)),
            "DP_PROYECTADO": int(cl.get("DP_PROYECTADO", 0)),
            "DP_CERCA_SNIES": int(cl.get("DP_CERCA_SNIES", 0)),
            "DP_DIFERENCIA_MEDIA": int(cl.get("DP_DIFERENCIA_MEDIA", 0)),
            "DP_DIFERENCIA_ALTA": int(cl.get("DP_DIFERENCIA_ALTA", 0)),
            "MEDIANA_RATIO_DP_SNIES": round(float(comparables["RATIO_DP_SNIES"].median()), 3) if len(comparables) else np.nan,
            "SNIES_ACTUALIZADO_VS_BASE": int((ga["SNIES_CAMBIO_VS_BASE"].abs() > 0.005).sum()),
        })
    inst = pd.DataFrame(filas)
    if validacion_instituciones is not None and len(validacion_instituciones):
        v = validacion_instituciones.copy()
        v["CODIGO_INSTITUCION"] = v["CODIGO_INSTITUCION"].astype(str)
        cols = [c for c in ("CODIGO_INSTITUCION", "ESTADO_INSTITUCION", "TIPO_FUENTE", "ACTO_PRINCIPAL", "FECHA_EXPEDICION") if c in v]
        inst = inst.merge(v[cols], on="CODIGO_INSTITUCION", how="left")
        inst = inst.rename(columns={"ESTADO_INSTITUCION": "ESTADO_DOCUMENTO"})
    inst = inst.sort_values("PROGRAMAS_ACTIVOS_SNIES", ascending=False).reset_index(drop=True)

    cols_p = ["CODIGO_PADRE", "INSTITUCION_SNIES", "ID_PRGRM", "CODIGO_SNIES", "PROGRAMA_SNIES", "NIVEL_SNIES",
              "MODALIDAD_SNIES", "ESTADO_PROGRAMA_SNIES", "PERIODICIDAD_SNIES", "COSTO_SNIES", "COSTO_SNIES_SEM",
              "SNIES_BASE", "SNIES_CAMBIO_VS_BASE", "DP_PRC", "DP_UNIDAD", "DP_SEM", "DP_DECIMALES",
              "DP_ESTADO_NORMALIZACION", "RATIO_DP_SNIES", "CLASE"]
    return p[[c for c in cols_p if c in p.columns]], inst


def resumen_nacional(hecaa: pd.DataFrame, inst: pd.DataFrame) -> pd.DataFrame:
    act = hecaa[hecaa["ESTADO_PROGRAMA_SNIES"].astype(str).str.lower().str.startswith("activ")]
    priv = act[act["SECTOR"].astype(str).str.lower().str.startswith("priv")]
    filas = [
        ("Programas activos en SNIES (todas las IES)", len(act)),
        ("  de IES privadas", len(priv)),
        ("  con costo de matrícula reportado", int(act["COSTO_SNIES"].notna().sum())),
        ("Instituciones en el universo Benchlab", len(inst)),
        ("  programas activos en SNIES", int(inst["PROGRAMAS_ACTIVOS_SNIES"].sum())),
        ("  de ellos con precio DP en la base", int(inst["ACTIVOS_CON_PRECIO_DP"].sum())),
        ("  precios DP idénticos a SNIES", int(inst["DP_IGUAL_SNIES"].sum())),
        ("  precios DP proyectados (decimales)", int(inst["DP_PROYECTADO"].sum())),
        ("  precios DP con diferencia > 20 % vs SNIES", int(inst["DP_DIFERENCIA_ALTA"].sum())),
    ]
    return pd.DataFrame(filas, columns=["INDICADOR", "VALOR"])


def cargar_y_calcular(ruta_hecaa, ruta_base, ruta_auditoria, ruta_validacion, anio):
    from .desde_ancho import leer_base

    hecaa = leer_hecaa(ruta_hecaa)
    base = leer_base(ruta_base)
    aud = leer_csv(ruta_auditoria)
    val = leer_csv(ruta_validacion) if ruta_validacion and Path(ruta_validacion).exists() else None
    prog, inst = panorama(hecaa, base, aud, val, anio)
    return prog, inst, resumen_nacional(hecaa, inst)
