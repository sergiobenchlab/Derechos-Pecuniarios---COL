from dpcol.extraer import Cruzador, Programa, consolidar, extraer_lineas, extraer_valor_unico, montos


def _cruz():
    return Cruzador([
        Programa(1, 2051, "ADMINISTRACION DE EMPRESAS", "Soacha"),
        Programa(2, 9001, "ADMINISTRACION DE EMPRESAS", "Bogotá, D.C."),
        Programa(3, 100, "ANTROPOLOGIA"),
        Programa(4, 101, "ESPECIALIZACION EN GERENCIA DE PROYECTOS"),
        Programa(5, 102, "ARTES LIBERALES EN CIENCIAS SOCIALES"),
    ])


def test_montos():
    assert montos("Neto $ 14.714.000| $14.714.000") == [14714000.0, 14714000.0]
    assert montos("Créditos 140 año 2026") == []
    assert montos("$8'450.000") == [8450000.0]


def test_lineas_rosario_ignora_descuento_y_neto():
    pag = ("Antropología $ 14.340.000| $ 14.340.000\n(-) Descuento $ 1.775.000 $ 1.775.000\n"
           "Neto $ 12.565.000| $12.565.000\nArtes Liberales en Ciencias Sociales $ 14.482.000| $ 14.482.000\n"
           "Gerencia de Proyectos $ 9.100.000\n")
    f = extraer_lineas([pag], _cruz())
    got = {(r["ID_PRGRM"], r["PRC"], r["CRUCE"]) for r in f}
    assert got == {(3, 14340000.0, "nombre_exacto"), (5, 14482000.0, "nombre_exacto"), (4, 9100000.0, "nombre_sin_nivel")}


def test_cruce_por_codigo_y_municipio():
    c = _cruz()
    assert c.por_codigo(["2051", "Administración de Empresas", "Presencial", "Soacha"]).id_prgrm == 1
    cands, tipo = c.por_nombre("Administración de Empresas", contexto="Presencial Bogotá, D.C.")
    assert [p.id_prgrm for p in cands] == [2] and "municipio" in tipo
    cands, tipo = c.por_nombre("Administración de Empresas")
    assert len(cands) == 2 and tipo.endswith("_multiple")


def test_consolidar_prioriza_codigo_y_marca_conflicto():
    filas = [
        {"ID_PRGRM": 1, "PRC": 5274600.0, "PRD_PRC": "Semestral", "PAGINA": 2, "METODO": "tabla", "CRUCE": "codigo_snies", "ENCABEZADO": "", "TEXTO_FILA": ""},
        {"ID_PRGRM": 1, "PRC": 6329500.0, "PRD_PRC": "Semestral", "PAGINA": 9, "METODO": "lineas", "CRUCE": "nombre_exacto_multiple", "ENCABEZADO": "", "TEXTO_FILA": ""},
        {"ID_PRGRM": 3, "PRC": 14340000.0, "PRD_PRC": "Semestral", "PAGINA": 1, "METODO": "lineas", "CRUCE": "nombre_exacto", "ENCABEZADO": "", "TEXTO_FILA": ""},
        {"ID_PRGRM": 3, "PRC": 14000000.0, "PRD_PRC": "Semestral", "PAGINA": 3, "METODO": "lineas", "CRUCE": "nombre_exacto", "ENCABEZADO": "", "TEXTO_FILA": ""},
    ]
    c = consolidar(filas).set_index("ID_PRGRM")
    assert c.loc[1, "PRC"] == 5274600.0 and not c.loc[1, "CONFLICTO"]
    assert c.loc[3, "CONFLICTO"]


def test_rosario_posgrado_credito_nombre_partido_y_ocr():
    c = Cruzador([
        Programa(10, 1, "ESPECIALIZACION EN GERENCIA DE MARKETING PARA ENTORNOS DIGITALES"),
        Programa(11, 2, "MAESTRIA EN FILOSOFIA"),
        Programa(12, 3, "DOCTORADO EN FILOSOFIA"),
        Programa(13, 4, "ESPECIALIZACION EN DERECHO AMBIENTAL"),
        Programa(14, 5, "ESPECIALIZACION EN DERECHO LABORAL"),
    ])
    pag = ("ESCUELA DE ADMINISTRACIÓN\nNúmero — valor Crédito 2026-1 y 2026-2\nCréditos\n"
           "Especialización en Gerencia de Marketing para Entornos 25 $ 1.578.000\nDigitales\n"
           "Maestría en Filosofía 36 $975.000\n"
           "Múmero Valor semestre 2026-1\nDoctorado en Filosofía 8 515.858.000\n"
           "Especialización en Derecho 25 $ 930.000\n")
    got = {r["ID_PRGRM"]: (r["PRC"], r["PRD_PRC"]) for r in extraer_lineas([pag], c)}
    assert got[10] == (1578000.0, "Credito")
    assert got[11] == (975000.0, "Credito")
    assert got[12] == (15858000.0, "Semestral")
    assert 13 not in got and 14 not in got  # "Derecho" a secas no se asigna por aproximación


def test_valor_unico_mq_rosario():
    c = Cruzador([Programa(20, 1, "ESPECIALIZACION EN ANESTESIOLOGIA", nivel="Especialización médico quirúrgica"),
                  Programa(21, 2, "ESPECIALIZACION EN PEDIATRIA", nivel="Especialización médico quirúrgica"),
                  Programa(22, 3, "ESPECIALIZACION EN FINANZAS", nivel="Especialización universitaria")])
    pags = ["Universidad del Rosario ACUERDO 325 (19 de noviembre de 2025) Por el cual se fijan los valores de matrícula "
            "para los estudiantes de las especialidades médicas y quirúrgicas para el año 2026",
            "Acuerdo 325 - precios especializaciones MQ 2026, página 2\nMatrícula $21.855.000\nCrédito Core $2.318.000"]
    f = extraer_valor_unico(pags, c)
    assert {r["ID_PRGRM"] for r in f} == {20, 21} and all(r["PRC"] == 21855000 for r in f)
    # si otro documento trae precio por nombre exacto, ese gana
    filas = f + [{"ID_PRGRM": 20, "PRC": 25_000_000.0, "PRD_PRC": "Semestral", "PAGINA": 1, "METODO": "lineas",
                  "CRUCE": "nombre_exacto", "ENCABEZADO": "", "TEXTO_FILA": ""}]
    assert consolidar(filas).set_index("ID_PRGRM").loc[20, "PRC"] == 25_000_000.0
