from pathlib import Path

from dpcol.organizar import clasificar, institucion_por_nombre, maestro_instituciones, organizar


def _arbol(tmp: Path):
    a = tmp / "sp" / "ULT" / "1" / "2805-UNIVERSIDAD SIMON BOLIVAR"
    a.mkdir(parents=True)
    (a / "PRECIOS 2026.pdf").write_bytes(b"pdf2026")
    (a / "PRECIOS 2025.pdf").write_bytes(b"pdf2025")
    b = tmp / "sp" / "data_2023" / "1706-UNIVERSIDAD EXTERNADO DE COLOMBIA"
    b.mkdir(parents=True)
    (b / "1706_UNIVERSIDAD EXTERNADO DE COLOMBIA_2021_2022.pdf").write_bytes(b"ext")
    (b / "sin fecha.pdf").write_bytes(b"x")
    (tmp / "sp" / "Archivos").mkdir()
    (tmp / "sp" / "Archivos" / "1706_acuerdo-2021019.pdf").write_bytes(b"ext2")
    (tmp / "sp" / "base.xlsx").write_bytes(b"base")
    (tmp / "sp" / ".DS_Store").write_bytes(b"")
    n = tmp / "nuevo" / "PRECIOS 2026"
    n.mkdir(parents=True)
    (n / "SIMON_BOLIVAR_2026.pdf").write_bytes(b"pdf2026")  # duplicado exacto
    (n / "Externado precios 2027.pdf").write_bytes(b"ext2027")
    (n / "algo raro.pdf").write_bytes(b"raro")


def test_maestro_y_nombre(tmp_path):
    _arbol(tmp_path)
    m = maestro_instituciones([tmp_path / "sp"])
    assert set(m) == {"2805", "1706"}
    assert institucion_por_nombre("SIMON_BOLIVAR_2026", m) == "2805"
    assert institucion_por_nombre("Externado precios", m) == "1706"
    assert institucion_por_nombre("algo raro", m) is None


def test_clasificar_anio(tmp_path):
    _arbol(tmp_path)
    m = maestro_instituciones([tmp_path / "sp"])
    raiz = tmp_path / "sp"
    c = clasificar(raiz / "data_2023/1706-UNIVERSIDAD EXTERNADO DE COLOMBIA/1706_UNIVERSIDAD EXTERNADO DE COLOMBIA_2021_2022.pdf", raiz, m)
    assert c["CODIGO_INSTITUCION"] == "1706" and c["ANIO"] == 2022
    c = clasificar(raiz / "Archivos/1706_acuerdo-2021019.pdf", raiz, m)
    assert c["CODIGO_INSTITUCION"] == "1706" and c["ORIGEN_INSTITUCION"] == "prefijo_archivo"
    assert c["ANIO"] is None  # 2021019 no es un año


def test_organizar(tmp_path):
    _arbol(tmp_path)
    m = maestro_instituciones([tmp_path / "sp"])
    dest = tmp_path / "docs"
    inv = organizar([(tmp_path / "nuevo", None), (tmp_path / "sp", None)], dest, m)
    assert str(inv["ANIO"].dtype) == "Int64"
    est = inv.set_index("ARCHIVO")["ESTADO"]
    assert est["SIMON_BOLIVAR_2026.pdf"] == "COPIADO"
    assert est["PRECIOS 2026.pdf"] == "DUPLICADO"
    assert est["base.xlsx"] == "EXCLUIDO_BASE"
    assert est["algo raro.pdf"] == "SIN_CLASIFICAR"
    assert est["sin fecha.pdf"] == "COPIADO_SIN_ANIO"
    assert (dest / "2805-UNIVERSIDAD SIMON BOLIVAR" / "2026" / "2805_2026_simon_bolivar.pdf").exists()
    assert (dest / "1706-UNIVERSIDAD EXTERNADO DE COLOMBIA" / "2027").is_dir()
    assert (dest / "1706-UNIVERSIDAD EXTERNADO DE COLOMBIA" / "2022" / "1706_2022_2021.pdf").exists()
    # los originales siguen ahí
    assert (tmp_path / "nuevo" / "PRECIOS 2026" / "SIMON_BOLIVAR_2026.pdf").exists()
    # segunda corrida: todo ya está, nada nuevo se copia
    inv2 = organizar([(tmp_path / "nuevo", None), (tmp_path / "sp", None)], dest, m)
    assert not inv2["ESTADO"].isin(["COPIADO", "COPIADO_SIN_ANIO", "SIN_CLASIFICAR"]).any()
