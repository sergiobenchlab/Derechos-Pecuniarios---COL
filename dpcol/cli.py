"""Línea de comandos.

    python -m dpcol normalizar --entrada T08_PRECIOS.csv --maestro "Precios 2026(Base con histórico).csv" --salida data/salidas/2026
    python -m dpcol normalizar --entrada PRECIOS_2026_AUDITORIA.xlsx --formato ancho --maestro PRECIOS_2026_AUDITORIA.xlsx --salida data/salidas/2026
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .desde_ancho import ancho_a_largo, leer_base
from .io import escribir_csv, escribir_t08, leer_csv
from .maestro import cargar_maestro, cargar_periodos
from .normalizar import Parametros, normalizar
from .validar import a_revisar, cobertura_por_ies, resumen_estados, variacion_anual


def _cmd_normalizar(a: argparse.Namespace) -> int:
    periodos = cargar_periodos(a.periodos)
    maestro, dups = cargar_maestro(a.maestro)
    if a.formato == "ancho":
        staging = ancho_a_largo(leer_base(a.entrada), periodos)
    else:
        staging = leer_csv(a.entrada)
    params = Parametros(homogeneizar_snies=a.homogeneizar_snies)
    d = normalizar(staging, maestro, periodos, params)
    d = variacion_anual(d)
    if a.anios:
        d = d[d["ANIO"].isin(a.anios)]

    out = Path(a.salida)
    out.mkdir(parents=True, exist_ok=True)
    escribir_t08(d, out / "T08_PRECIOS.csv")
    escribir_csv(d, out / "auditoria_completa.csv")
    escribir_csv(a_revisar(d), out / "a_revisar.csv")
    escribir_csv(resumen_estados(d), out / "resumen_estados.csv")
    escribir_csv(cobertura_por_ies(d), out / "cobertura_por_ies.csv")
    if len(dups):
        escribir_csv(dups, out / "maestro_programas_duplicados.csv")

    print(f"Filas: {len(staging):,} leídas -> {len(d):,} escritas en {out}")
    print(resumen_estados(d).to_string(index=False))
    sin_maestro = (~d["EN_MAESTRO"]).sum()
    if sin_maestro:
        print(f"ADVERTENCIA: {sin_maestro:,} filas con ID_PRGRM que no está en el maestro")
    if len(dups):
        print(f"ADVERTENCIA: {dups['ID_PRGRM'].nunique()} ID_PRGRM duplicados en el maestro (ver maestro_programas_duplicados.csv)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dpcol", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("normalizar", help="Normaliza precios a T08 con PRC_HMGNZD semestral y genera auditoría")
    n.add_argument("--entrada", required=True, help="CSV en formato T08/staging largo, o base ancha (con --formato ancho)")
    n.add_argument("--formato", choices=["largo", "ancho"], default="largo")
    n.add_argument("--maestro", required=True, help="Base de programas (CSV o XLSX) con créditos, períodos y periodicidad")
    n.add_argument("--periodos", default=None, help="CSV ID_PRD/ANIO/FCH_INC_PRD (por defecto config/periodos.csv)")
    n.add_argument("--salida", required=True, help="Carpeta de salida")
    n.add_argument("--anios", type=int, nargs="*", help="Filtrar años en la salida (p. ej. 2026)")
    n.add_argument("--homogeneizar-snies", action="store_true", help="Llenar también PRC_HMGNZD en filas SNIES")
    n.set_defaults(func=_cmd_normalizar)

    a = ap.parse_args(argv)
    return a.func(a)
