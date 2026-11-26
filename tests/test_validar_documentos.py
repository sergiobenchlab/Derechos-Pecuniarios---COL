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


# Encabezados reales (texto/OCR) de actos 2026 de otras IES
import pytest

from dpcol.validar_documentos import _identificar_acto, _plano


@pytest.mark.parametrize("texto,tipo,num,anio", [
    ("CONSEJO SUPERIOR UNIVERSITARIO Acto Constitutivo No. 397 del 01 de diciembre de 2025 “Por medio del cual se fijan",
     "ACTO", "397", 2025),
    ("ACUERDO No.19 (1 de diciembre de 2025) EL CONSEJO ADMINISTRATIVO Y FINANCIERO GENERAL", "ACUERDO", "19", 2025),
    ("Externado RESOLUCIÓN RECTORAL DP-033-2025 Por la cual se aprueba el incremento", "RESOLUCION", "dp-033-2025", 2025),
    ("UTADEO ACUERDO No. 014 Noviembre 14 de 2025 Por el cual se aprueba el valor", "ACUERDO", "014", 2025),
    ("RESOLUCIÓN DE RECTORÍA No. R – 2025 – 032 21 de noviembre de 2025", "RESOLUCION", "r–2025–032", 2025),
    ("RESOLUCIÓN DE RECTORÍA 114 DEL 21 DE NOVIEMBRE DE 2025 POR LA CUAL SE FIJA", "RESOLUCION", "114", 2025),
    ("Resolución No. 023 2 de diciembre de 2025 Por medio de la cual modifica", "RESOLUCION", "023", 2025),
    ("Derechos Pecuniarios ACUERDO CD-037-2025 Estos valores entran en vigencia", "ACUERDO", "cd-037-2025", 2025),
    ("CONSEJO SUPERIOR Acuerdo No. 047 de 2025 (5 de diciembre) Por el cual", "ACUERDO", "047", 2025),
    ("RESOLUCIÓN RECTORAL Nro. 130 Medellín, noviembre 27 de 2025", "RESOLUCION", "130", None),
    ("ACUERDO DE SALA GENERAL No. 65 DE 2025 (noviembre 28)", "ACUERDO", "65", 2025),
    ("Vigilada MEN. Personería jurídica: Resolución 9168 del 6 de agosto de 1987. CONSEJO SUPERIOR TecMD "
     "ACUERDO No 058 (27 de noviembre 2025) POR MEDIO DE LA CUAL SE DETERMINAN LOS DERECHOS", "ACUERDO", "058", 2025),
    ("RESOLUCIÓN CONSEJO DIRECTIVO No 20-2025 Por la cual se establece el valor de la Matricula", "RESOLUCION", "20-2025", 2025),
    ("REGLAMENTO ACUERDO No. 58 DE 2019 deroga lo publicado mediante Acuerdo No. 57 de 2018. "
     "ACUERDO DE SALA GENERAL No. 58 de 2019 (Noviembre 15) POR EL CUAL SE ACTUALIZA", "ACUERDO", "58", 2019),
])
def test_identificar_acto(texto, tipo, num, anio):
    t, n, a, _ = _identificar_acto(_plano(texto))
    assert (t, n, a) == (tipo, num, anio)


def test_orden_ejecutiva_sin_numero_toma_anio_de_fecha():
    t = ("ORDEN EJECUTIVA Del 27 de noviembre de 2025 Por medio de la cual se fijan los derechos de matrícula "
         "para la vigencia del año 2026. Programa 4.500.000 Programa 5.200.000 Programa 6.100.000 "
         "Dado en Bogotá a los 27 días del mes de noviembre de 2025. Comuníquese")
    a = analizar_texto([t * 3])
    assert a.fecha_expedicion == date(2025, 11, 27)
    assert a.vigencia == 2026


def test_montos_sin_signo_y_solo_incremento():
    ucc = ("RESOLUCIÓN RECTORAL Nro. 139 Medellín, 27 de noviembre de 2025 VIGENCIA 2026 se incrementa en el IPC a "
           "octubre 31 de 2025 en 5.51%. 599.068 599.068 641.859 " + "texto " * 60 + " Comuníquese y cúmplase")
    a = analizar_texto([ucc])
    assert a.valores_dinero == 3
    assert dictaminar(a, 2026)[0] != "SIN_PRECIOS"
    solo = ("ACUERDO 325 (19 de noviembre de 2025) para el año 2026. ARTÍCULO TERCERO. Incrementar en 5.51% los "
            "valores de las matrículas. Matrícula $21.855.000 " + "texto " * 60 + " Comuníquese y cúmplase")
    estado, obs = dictaminar(analizar_texto([solo]), 2026)
    assert estado == "SOLO_INCREMENTO", obs


def test_vigencia_por_asunto_y_montos_con_apostrofo():
    t = ("CIRCULAR No. 306 12 de noviembre de 2025 ASUNTO: TARIFAS 2026 NIVEL DE FORMACIÓN POSGRADOS "
         "Especialización $8'450.000 Maestría $12'300.000 Doctorado $15'100.000 " + "x " * 120 + " Rector")
    a = analizar_texto([t])
    assert a.vigencia == 2026
    assert a.valores_dinero == 3
    assert a.fecha_expedicion == date(2025, 11, 12)


def test_vigencia_no_se_confunde_con_columna_del_anio_anterior():
    # Acto de nov-2025 cuyas tablas muestran "valor 2025" más veces que "2026"
    cuerpo = " ".join(["Programa valor año 2025 $4.500.000 incremento valor año 2026 $4.750.000"] * 3
                      + ["vigencia 2025 comparativo"] * 4)
    t = ("ACUERDO No. 010 de 2025 (28 de noviembre de 2025) Por el cual se fijan los derechos pecuniarios. "
         + "x " * 800 + cuerpo + " Dado en Medellín a los 28 días del mes de noviembre de 2025. Comuníquese")
    a = analizar_texto([t])
    assert a.vigencia == 2026
