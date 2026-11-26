"""Lectura y escritura robusta de las bases de Benchlab.

Las bases históricas mezclan codificaciones (UTF-8 con y sin BOM, Latin-1),
separador ';' y formatos numéricos colombianos ("14.142.600", "14142600,0",
"$ 2.106.115"). Aquí se centraliza ese manejo para que ningún paso descarte
filas en silencio (nada de on_bad_lines='skip').
"""
from __future__ import annotations

import csv
import math
import re
from pathlib import Path

import pandas as pd

T08_COLUMNAS = [
    "ID_IES", "ID_PRGRM", "ID_PRD", "FCH_INC_PRD",
    "PRC", "FUENTE", "PRC_HMGNZD", "PRD_PRC",
]

_CODIFICACIONES = ("utf-8-sig", "cp1252", "latin-1")


def leer_csv(ruta: str | Path, sep: str = ";") -> pd.DataFrame:
    """Lee un CSV como texto, probando codificaciones, sin descartar filas.

    Si alguna fila tiene un número de campos distinto al encabezado se lanza
    un error que indica la línea, en vez de omitirla.
    """
    ruta = Path(ruta)
    ultimo_error: Exception | None = None
    for cod in _CODIFICACIONES:
        try:
            texto = ruta.read_text(encoding=cod)
        except UnicodeDecodeError as e:
            ultimo_error = e
            continue
        filas = list(csv.reader(texto.splitlines(), delimiter=sep))
        filas = [f for f in filas if any(c.strip() for c in f)]
        if not filas:
            return pd.DataFrame()
        encabezado = [c.strip() for c in filas[0]]
        n = len(encabezado)
        malas = [i + 1 for i, f in enumerate(filas[1:], start=1) if len(f) != n]
        if malas:
            raise ValueError(
                f"{ruta.name}: {len(malas)} filas con número de columnas distinto "
                f"al encabezado ({n}). Primeras líneas: {malas[:10]}"
            )
        df = pd.DataFrame(filas[1:], columns=_nombres_unicos(encabezado), dtype=object)
        df.attrs["codificacion"] = cod
        return df
    raise ValueError(f"No se pudo decodificar {ruta}: {ultimo_error}")


def _nombres_unicos(cols: list[str]) -> list[str]:
    vistos: dict[str, int] = {}
    salida = []
    for i, c in enumerate(cols):
        c = c or f"SIN_NOMBRE_{i}"
        if c in vistos:
            vistos[c] += 1
            c = f"{c}_{vistos[c]}"
        else:
            vistos[c] = 0
        salida.append(c)
    return salida


_NO_NUM = re.compile(r"[^\d,.\-]")


def parsear_numero(valor) -> float:
    """Convierte un valor monetario en formato colombiano/mixto a float.

    Reglas:
    - Se eliminan '$', espacios y cualquier símbolo.
    - Si aparecen '.' y ',', el separador que va de último es el decimal.
    - Si aparece un solo tipo de separador repetido, es de miles.
    - Si aparece una sola vez, es de miles solo si a la izquierda hay 1-3
      dígitos y a la derecha exactamente 3 ("658,500" -> 658500). En otro caso
      es decimal ("14142600,0" -> 14142600.0; "5311993,547" -> 5311993.547,
      valor estimado con decimales presente en el T08 2026).
    """
    if valor is None:
        return math.nan
    if isinstance(valor, (int, float)):
        return float(valor)
    s = _NO_NUM.sub("", str(valor))
    if s in ("", "-", ",", "."):
        return math.nan
    if "," in s and "." in s:
        dec = "," if s.rfind(",") > s.rfind(".") else "."
        mil = "." if dec == "," else ","
        s = s.replace(mil, "").replace(dec, ".")
    elif "," in s or "." in s:
        sepr = "," if "," in s else "."
        partes = s.split(sepr)
        es_miles = len(partes) > 2 or (len(partes[-1]) == 3 and 1 <= len(partes[0].lstrip("-")) <= 3)
        if es_miles:
            s = s.replace(sepr, "")
        else:
            s = s.replace(sepr, ".")
    try:
        return float(s)
    except ValueError:
        return math.nan


def a_numero(serie: pd.Series) -> pd.Series:
    return serie.map(parsear_numero).astype(float)


def _fmt_num(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return ""
    x = round(float(x))
    return str(int(x))


def escribir_t08(df: pd.DataFrame, ruta: str | Path) -> None:
    """Escribe en el formato exacto del T08 que consume el aplicativo.

    UTF-8 con BOM, separador ';', fin de línea CRLF y precios enteros.
    """
    faltan = [c for c in T08_COLUMNAS if c not in df.columns]
    if faltan:
        raise ValueError(f"Faltan columnas T08: {faltan}")
    out = df[T08_COLUMNAS].copy()
    for c in ("PRC", "PRC_HMGNZD"):
        out[c] = out[c].map(_fmt_num)
    for c in ("ID_IES", "ID_PRGRM", "ID_PRD", "FCH_INC_PRD"):
        out[c] = out[c].map(lambda v: _fmt_num(parsear_numero(v)))
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(ruta, sep=";", index=False, encoding="utf-8-sig", lineterminator="\r\n")


def escribir_csv(df: pd.DataFrame, ruta: str | Path) -> None:
    """CSV de trabajo (auditoría, reportes): UTF-8 con BOM para abrir en Excel."""
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, sep=";", index=False, encoding="utf-8-sig", decimal=",")
