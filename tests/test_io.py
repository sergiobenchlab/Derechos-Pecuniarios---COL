import math

import pytest

from dpcol.io import leer_csv, parsear_numero


@pytest.mark.parametrize("txt,esperado", [
    ("14142600,0", 14142600.0),
    (" 17.608.727 ", 17608727.0),
    ("$ 2.106.115", 2106115.0),
    ("2.106.115,50", 2106115.5),
    ("2,106,115.50", 2106115.5),
    ("658,500", 658500.0),
    ("658500", 658500.0),
    ("1234.5", 1234.5),
    ("", math.nan),
    (None, math.nan),
    (14142600, 14142600.0),
])
def test_parsear_numero(txt, esperado):
    v = parsear_numero(txt)
    if math.isnan(esperado):
        assert math.isnan(v)
    else:
        assert v == esperado


def test_leer_csv_latin1_y_bom(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes("ID;NOMBRE\n1;DISEÑO GRÁFICO\n".encode("cp1252"))
    df = leer_csv(p)
    assert df.loc[0, "NOMBRE"] == "DISEÑO GRÁFICO"
    p.write_bytes("﻿ID;NOMBRE\r\n1;DISEÑO\r\n".encode("utf-8"))
    assert list(leer_csv(p).columns) == ["ID", "NOMBRE"]


def test_leer_csv_no_descarta_filas(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("A;B\n1;2\n3;4;5\n", encoding="utf-8")
    with pytest.raises(ValueError, match="número de columnas"):
        leer_csv(p)
