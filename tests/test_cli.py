import pandas as pd

from dpcol.cli import main
from dpcol.io import leer_csv


def test_cli_ancho_a_t08(tmp_path):
    base = tmp_path / "base.csv"
    base.write_text(
        "ID_IES;ID_PRGRM;NÚMERO_CRÉDITOS;NÚMERO_PERIODOS_DE_DURACIÓN;PERIODICIDAD;PRC_SNIES 2026;2025;Periodo reportado 2025;2026;Periodo reportado 2026\n"
        "72;646;140;8;Semestral; 18.755.346 ; 16.811.000 ;Semestral; 18.000.000 ;Semestral\n"
        "72;700;24;2;Semestral; 9.000.000 ;;; 375.000 ;Credito\n",
        encoding="utf-8-sig",
    )
    out = tmp_path / "out"
    assert main(["normalizar", "--entrada", str(base), "--formato", "ancho", "--maestro", str(base), "--salida", str(out)]) == 0
    t08 = leer_csv(out / "T08_PRECIOS.csv")
    assert list(t08.columns) == ["ID_IES", "ID_PRGRM", "ID_PRD", "FCH_INC_PRD", "PRC", "FUENTE", "PRC_HMGNZD", "PRD_PRC"]
    assert (out / "T08_PRECIOS.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    r = t08[(t08.ID_PRGRM == "700") & (t08.FUENTE == "DERECHOS PECUNIARIOS")].iloc[0]
    assert r.PRC_HMGNZD == "4500000"
    assert r.ID_PRD == "61" and r.FCH_INC_PRD == "46023"
    assert (out / "a_revisar.csv").exists()


def test_catalogo(tmp_path):
    base = tmp_path / "base.csv"
    base.write_text(
        "ID_IES;CÓDIGO_INSTITUCIÓN_PADRE;NOMBRE_INSTITUCIÓN;ID_PRGRM;ESTADO_OFICIAL;FUENTE_2026\n"
        "72;1701;JAVERIANA;1;Activo;PDF_A\n295;1701;JAVERIANA;2;Inactivo;PDF_B\n92;1826;UAN;3;Activo;\n",
        encoding="utf-8",
    )
    out = tmp_path / "cat.csv"
    assert main(["catalogo", "--base", str(base), "--anio", "2027", "--salida", str(out)]) == 0
    cat = leer_csv(out)
    j = cat[cat.CODIGO_INSTITUCION == "1701"].iloc[0]
    assert j.IDS_IES == "72 295"
    assert j.PROGRAMAS_ACTIVOS == "1" and j.FUENTES_ANIO_ANTERIOR == "PDF_A | PDF_B" and j.ESTADO == "PENDIENTE"
    # no duplica al correr de nuevo
    main(["catalogo", "--base", str(base), "--anio", "2027", "--salida", str(out)])
    assert len(leer_csv(out)) == 2
