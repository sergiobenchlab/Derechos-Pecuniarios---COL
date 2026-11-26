"""Línea de comandos.

    python -m dpcol normalizar --entrada T08_PRECIOS.csv --maestro "Precios 2026(Base con histórico).csv" --salida data/salidas/2026
    python -m dpcol normalizar --entrada PRECIOS_2026_AUDITORIA.xlsx --formato ancho --maestro PRECIOS_2026_AUDITORIA.xlsx --salida data/salidas/2026
    python -m dpcol catalogo --base PRECIOS_2026_AUDITORIA.xlsx --anio 2027
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .catalogo import catalogo_inicial, fusionar, guardar
from .desde_ancho import ancho_a_largo, leer_base
from .io import escribir_csv, escribir_t08, leer_csv
from .maestro import cargar_maestro, cargar_periodos
from .normalizar import Parametros, normalizar
from .organizar import maestro_instituciones, organizar, resumen_por_institucion
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


def _cmd_catalogo(a: argparse.Namespace) -> int:
    base = leer_base(a.base)
    cat = catalogo_inicial(base, a.anio, a.anio_ref)
    destino = Path(a.salida)
    cat = fusionar(destino, cat)
    guardar(cat, destino)
    print(f"Catálogo con {len(cat)} filas en {destino}")
    return 0


def _cmd_organizar(a: argparse.Namespace) -> int:
    fuentes = []
    for f in a.fuente:
        ruta, _, anio = f.partition("::")
        fuentes.append((Path(ruta), int(anio) if anio else None))
    maestro = maestro_instituciones([r for r, _ in fuentes])
    destino = Path(a.destino)
    inv = organizar(fuentes, destino, maestro, ejecutar=not a.simular)
    inv_path = Path(a.inventario) if a.inventario else destino.parent / "inventario_documentos.csv"
    escribir_csv(inv, inv_path)
    escribir_csv(resumen_por_institucion(inv), inv_path.with_name("resumen_documentos_por_institucion.csv"))
    print(f"{'SIMULACIÓN: ' if a.simular else ''}{len(inv):,} archivos revisados; inventario en {inv_path}")
    print(inv["ESTADO"].value_counts().to_string())
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

    c = sub.add_parser("catalogo", help="Crea/actualiza el catálogo de fuentes por IES para un año")
    c.add_argument("--base", required=True, help="Base ancha de trabajo (p. ej. PRECIOS_2026_AUDITORIA.xlsx)")
    c.add_argument("--anio", type=int, required=True, help="Año a recolectar (p. ej. 2027)")
    c.add_argument("--anio-ref", type=int, default=None, help="Año del que se toman las fuentes previas (por defecto anio-1)")
    c.add_argument("--salida", default="fuentes/catalogo_fuentes.csv")
    c.set_defaults(func=_cmd_catalogo)

    o = sub.add_parser("organizar", help="Copia documentos fuente a <CÓDIGO>-<IES>/<AÑO>/ y genera inventario")
    o.add_argument("--fuente", action="append", required=True,
                   help="Carpeta origen, opcionalmente con año por defecto: 'ruta::2024'. Repetible; el orden es la prioridad ante duplicados")
    o.add_argument("--destino", required=True)
    o.add_argument("--inventario", default=None)
    o.add_argument("--simular", action="store_true", help="No copia; solo genera el inventario")
    o.set_defaults(func=_cmd_organizar)

    a = ap.parse_args(argv)
    return a.func(a)
