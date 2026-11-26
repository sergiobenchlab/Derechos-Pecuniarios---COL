"""Maestro de programas (duración, créditos, periodicidad) y de períodos."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import a_numero, leer_csv

RAIZ = Path(__file__).resolve().parent.parent

COLUMNAS_MAESTRO = {
    "ID_PRGRM": "ID_PRGRM",
    "ID_IES": "ID_IES",
    "NOMBRE_INSTITUCIÓN": "NOMBRE_INSTITUCION",
    "CÓDIGO_SNIES_DEL_PROGRAMA": "CODIGO_SNIES",
    "NOMBRE_DEL_PROGRAMA": "NOMBRE_PROGRAMA",
    "NIVEL_DE_FORMACIÓN": "NIVEL",
    "MODALIDAD": "MODALIDAD",
    "NÚMERO_CRÉDITOS": "CREDITOS",
    "NÚMERO_PERIODOS_DE_DURACIÓN": "PERIODOS",
    "PERIODICIDAD": "PERIODICIDAD",
}


def cargar_maestro(ruta: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lee la base ancha con histórico (CSV o XLSX) y deja un programa por fila.

    Devuelve (maestro, duplicados). Si un ID_PRGRM aparece más de una vez se
    conserva la primera fila con créditos y períodos válidos y las demás se
    devuelven en `duplicados` para revisión.
    """
    ruta = Path(ruta)
    if ruta.suffix.lower() in (".xlsx", ".xls"):
        df = pd.read_excel(ruta, dtype=object)
        df.columns = [str(c).strip() for c in df.columns]
    else:
        df = leer_csv(ruta)
    faltan = [c for c in ("ID_PRGRM", "NÚMERO_CRÉDITOS", "NÚMERO_PERIODOS_DE_DURACIÓN", "PERIODICIDAD") if c not in df.columns]
    if faltan:
        raise ValueError(f"El maestro {ruta.name} no tiene las columnas {faltan}")
    m = df[[c for c in COLUMNAS_MAESTRO if c in df.columns]].rename(columns=COLUMNAS_MAESTRO)
    m["ID_PRGRM"] = a_numero(m["ID_PRGRM"])
    m = m[m["ID_PRGRM"].notna()].copy()
    m["ID_PRGRM"] = m["ID_PRGRM"].astype("int64")
    for c in ("CREDITOS", "PERIODOS"):
        m[c] = a_numero(m[c])
    m["_valido"] = (m["CREDITOS"] > 0) & (m["PERIODOS"] > 0)
    m = m.sort_values(["ID_PRGRM", "_valido"], ascending=[True, False], kind="stable")
    dup_mask = m.duplicated("ID_PRGRM", keep="first")
    duplicados = m[m["ID_PRGRM"].isin(m.loc[dup_mask, "ID_PRGRM"])].drop(columns="_valido")
    maestro = m[~dup_mask].drop(columns="_valido").reset_index(drop=True)
    return maestro, duplicados


def cargar_periodos(ruta: str | Path | None = None) -> pd.DataFrame:
    ruta = Path(ruta) if ruta else RAIZ / "config" / "periodos.csv"
    p = leer_csv(ruta)
    for c in ("ID_PRD", "ANIO", "FCH_INC_PRD"):
        p[c] = a_numero(p[c]).astype("int64")
    return p
