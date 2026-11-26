from datetime import date

from dpcol.validar_documentos import analizar_texto, cobertura_programas, dictaminar

# Extractos del OCR real de "PRECIOS 2026.pdf" de la Universidad Simón Bolívar
USB_P1 = """ACREDITACIÓN INSTITUCIONAL EN ALTA CALIDAD
ACUERDO DE SALA GENERAL No. 65 DE 2025
(noviembre 28)
POR EL CUAL SE FIJAN LOS VALORES DE MATRÍCULA Y OTROS
DERECHOS PECUNIARIOS PARA EL AÑO 2026.
2. Que la Sala General de la Universidad en sesiones celebradas el 13 y el 20 de
noviembre de 2025 aprobó mediante acuerdos No. 61 y No. 63 la propuesta de
incremento para establecer los derechos pecuniarios y valores de matrícula para el año
2026, considerando el estudio...
Artículo 1. Establecer los valores de matrícula para el año 2026 para los programas
| ADMINISTRACIÓN DE EMPRESAS | $ 4,791,500. IPC | 551% | $ 5,055,500
| CONTADURÍA PÚBLICA | $ 5,664,700. IPC 551% | $ 5,976,800
| NEGOCIOS INTERNACIONALES $ 5,613,500 IPC | $ 5,922,800
Acuerdo de Sala General No. 65 de 2025 Página 1 de 9"""
USB_MEDIO = "MEDICINA $ 18,290,100 IPC 5.51% $ 19,297,800 ENFERMERIA $ 6,310,800 $ 6,658,500 PSICOLOGIA $ 6,098,700 $ 6,434,700 Página 2 de 9"
USB_P9 = """OPCION ACADEMICA DE GRADO $ 1,086,700
Artículo 4. Envíese copia del presente acuerdo a las dependencias que correspondan.
COMUNÍQUESE Y CÚMPLASE
Dado en la ciudad de Barranquilla, a los veintiocho (28) días del mes de noviembre de 2025.
Para constancia firman,
Rector
Acuerdo de Sala General No. 65 de 2025 Página 9 de 9"""

# Extracto real de "SIMON_BOLIVAR_2026.pdf" (reglamento, sin valores)
REGLAMENTO = """REGLAMENTO DE DERECHOS PECUNIARIOS
ACUERDO No. 58 DE 2019
Documento actualizado en noviembre de 2019, y en consecuencia deroga las
disposiciones sobre derechos pecuniarios publicadas mediante Acuerdo No. 57 de 2018.
Publicado: Noviembre 28 de 2019.
ACTUALIZADO POR SALA GENERAL EN ENERO DE 2021.
ACUERDO DE SALA GENERAL No. 58 de 2019
(Noviembre 15)
POR EL CUAL SE ACTUALIZA EL REGLAMENTO DE DERECHOS PECUNIARIOS
Artículo 2. Derechos Pecuniarios. Artículo 3. Valor de los Derechos Pecuniarios.
""" + "texto del reglamento sin valores " * 20 + "\nAcuerdo de Sala General No. 58 de 2019 Página 1 de 13"


def _usb():
    return [USB_P1] + [USB_MEDIO] * 7 + [USB_P9]


def test_simon_bolivar_2026_ok():
    a = analizar_texto(_usb(), [True] * 9)
    assert (a.tipo_acto, a.numero_acto, a.anio_acto) == ("ACUERDO", "65", 2025)
    assert a.fecha_expedicion == date(2025, 11, 28)
    assert a.origen_fecha == "cierre"
    assert a.vigencia == 2026
    assert a.paginas_declaradas == 9 and a.paginas == 9
    assert a.tiene_cierre
    estado, obs = dictaminar(a, 2026)
    assert estado == "OK", obs


def test_simon_bolivar_incompleto_si_faltan_paginas():
    a = analizar_texto(_usb()[:5])
    estado, obs = dictaminar(a, 2026)
    assert "INCOMPLETO_PAGINAS" in obs
    assert estado == "INCOMPLETO_PAGINAS"


def test_reglamento_no_es_acto_de_precios():
    a = analizar_texto([REGLAMENTO] * 13)
    assert a.es_reglamento
    estado, obs = dictaminar(a, 2026)
    assert estado == "SIN_PRECIOS"
    assert "FECHA_FUERA_DE_RANGO" in obs


def test_acto_de_otro_anio():
    p = USB_P1.replace("2026", "2025").replace("DE 2025\n(noviembre 28)", "DE 2024\n(noviembre 28)")
    a = analizar_texto([p, USB_MEDIO, USB_P9.replace("2025", "2024")])
    estado, obs = dictaminar(a, 2026)
    assert a.vigencia == 2025
    assert estado == "VIGENCIA_DISTINTA"


def test_fecha_temprana_y_tardia():
    a = analizar_texto(_usb())
    a.fecha_expedicion = date(2025, 7, 10)
    assert dictaminar(a, 2026)[0] == "FECHA_TEMPRANA"
    a.fecha_expedicion = date(2026, 1, 20)
    assert dictaminar(a, 2026)[0] == "FECHA_TARDIA"


def test_resolucion_rectoral():
    t = ("RESOLUCIÓN RECTORAL No. 1762 del 2 de diciembre de 2025\nPor la cual se fijan los valores de matrícula "
         "para el periodo académico 2026-1 y 2026-2\n" + "PROGRAMA $ 4.500.000 " * 10 +
         "\nDada en Bogotá D.C., a los 2 días del mes de diciembre de 2025. Publíquese y cúmplase")
    a = analizar_texto([t])
    assert a.tipo_acto == "RESOLUCION" and a.numero_acto == "1762" and a.anio_acto == 2025
    assert a.fecha_expedicion == date(2025, 12, 2)
    assert a.vigencia == 2026
    assert dictaminar(a, 2026)[0] == "OK"


def test_cobertura_programas():
    v, n = cobertura_programas(USB_P1 + "\n" + USB_MEDIO, ["ADMINISTRACION DE EMPRESAS", "MEDICINA", "DERECHO", "ESPECIALIZACION EN PSICOLOGIA"])
    assert (v, n) == (3, 4)
