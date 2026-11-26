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
    ("Personería jurídica, Res. No. 0618 de 1970. RESOLUCIÓN DEL CONSEJO SUPERIOR No. 750 DEL 05 DE NOVIEMBRE DE 2024 "
     "POR LA CUAL SE FIJAN LOS VALORES. Que el Consejo Superior en su sesión Acta No. 327 autorizó", "RESOLUCION", "750", 2024),
    ("RESOLUCIÓN RECTORAL Nro. 130 Medellín, noviembre 27 de 2025", "RESOLUCION", "130", None),
    ("ACUERDO DE SALA GENERAL No. 65 DE 2025 (noviembre 28)", "ACUERDO", "65", 2025),
    ("UNIVERSIDAD Resolución de la Presidencia Institucional No 017 de 2025 Por la cual se autoriza el porcentaje de "
     "aumento de matriculas Personeria Juridica No 22195 de 1985 Resolución 1780 de 2010", "RESOLUCION", "017", 2025),
    ("Pontificia Universidad JAVERIANA ACUERDO N”. 781 Valores de Matrícula y Otros Derechos Pecuniarios", "ACUERDO", "781", None),
    ("R.R.G. No. 086/2025 RESOLUCIÓN RECTORAL GENERAL NO. 086 DEL 14 DE NOVIEMBRE DE 2025 “Por medio de la cual se establecen",
     "RESOLUCION", "086", 2025),
    ("Resolución N.º 43 de 2025 (7 de noviembre) “Por la cual se fijan los derechos pecuniarios", "RESOLUCION", "43", 2025),
    ("Bogotá, D.C., 3 de septiembre de 2025 RECTORÍA Resolución N.* 013 de 2025 Derechos de Matrícula 2026", "RESOLUCION", "013", 2025),
    ("RECTCRÍA ACUERDO NUM. O31 [27 de noviembre de 2O25) Por el cual se establecen los derechos", "ACUERDO", "031", 2025),
    ("ORDEN EJECUTIVA Del 27 de noviembre de 2025 Por medio de la cual se fijan los derechos de matrícula", "ORDEN", "s/n", 2025),
    ("Derechos pecuniarios Universidad de los Andes 2026 El Comité Directivo, en su sesión No. 312-25 del 10 de diciembre "
     "de 2025, aprobó el incremento", "SESION", "312-25", 2025),
    ("Personería Jurídica: RES. 2085 de 1987 del MEN RES. 1904 del MEN, 5 de Agosto de 2002 ACUERDO DEL CONSEJO DE "
     "FUNDADORES 002 (25 de noviembre de 2025) POR EL CUAL SE DETERMINAN LOS VALORES", "ACUERDO", "002", 2025),
    ("ACREDITACIÓN INSTITUCIONAL UNIVERSIDAD SIMÓN BOLÍVAR ALTA CALIDAD Resolución 015 MINEDUCACIÓN BARRANQUILLA "
     "ACUERDO DE SALA GENERAL No. 51 DE 2024 (noviembre 29) POR EL CUAL SE FIJAN LOS VALORES", "ACUERDO", "51", 2024),
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


def test_ajuste_porcentual_y_valor_unico():
    central = ("ACUERDO DEL CONSEJO SUPERIOR N.° 34 de 2025 Noviembre 26 de 2025 Por el cual se establece el ajuste al "
               "valor de las matrículas para el año 2026. La actualización del valor del crédito académico para el año "
               "2026 será del 5,51 %, lo que corresponde al IPC. " + "texto " * 60 + " Comuníquese y cúmplase")
    assert dictaminar(analizar_texto([central]), 2026)[0] == "SOLO_INCREMENTO"
    sanjose = ("RESOLUCIÓN CONSEJO DIRECTIVO No 20-2025 Por la cual se establece el valor de la Matricula para el año "
               "2026. Establecer el valor de la matricula por estudiante: CUATRO MILLONES ($4.370.822) y el crédito "
               "$277.157 " + "texto " * 60 + " Dada en Bogotá a los 15 días del mes de diciembre de 2025. Comuníquese")
    estado, obs = dictaminar(analizar_texto([sanjose]), 2026)
    assert estado == "POCOS_VALORES", obs


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


def test_tabla_de_tarifas_upb_titulo_manda():
    # UPB "TARIFAS SEDE CENTRAL 2025": cada fila cita el acto "RRG No 083/2024"
    fila = "1205 RRG No 083/2024 Arquitectura MEDELLIN 10 164 17 6,50% $ 796.700 $ 13.543.900 $ 13.065.880 "
    t = ("TARIFAS SEDE CENTRAL 2025 Pregrado Presencial Incremento con base en las tarifas 2024 Valor Crédito 2025 "
         "Valor Primer Semestre 2025 " + fila * 40)
    assert analizar_texto([t]).vigencia == 2025


def test_uao_tecnologias_es_2025():
    t = ("Personería jurídica, Res. No. 0618, de la Gobernación del Valle del Cauca del 20 de Febrero de 1970. "
         "RESOLUCIÓN DEL CONSEJO SUPERIOR No. 750 DEL 05 DE NOVIEMBRE DE 2024 POR LA CUAL SE FIJAN LOS DERECHOS "
         "PECUNIARIOS PARA LOS PROGRAMAS ACADÉMICOS DE NIVEL TECNOLÓGICO, PARA EL AÑO 2025 Que el Consejo Superior "
         "en su sesión del 05 de noviembre de 2024 Acta No. 327 " + "$225.580 " * 10 +
         "Dada en Santiago de Cali, a los cinco (05) días del mes de noviembre del año dos mil veinticuatro (2024).")
    a = analizar_texto([t])
    assert (a.tipo_acto, a.numero_acto, a.anio_acto) == ("RESOLUCION", "750", 2024)
    assert a.vigencia == 2025
    assert dictaminar(a, 2026)[0] == "VIGENCIA_DISTINTA"


def test_ipc_mas_puntos_es_incremento():
    cesa = ("EXTRACTO DE ACTA ACTA No. 622 CONSEJO DIRECTIVO 24 DE NOVIEMBRE DE 2025 3. Tarifas 2026 se propone un "
            "incremento en las matrículas del IPC + 1 para algunos programas " + "texto " * 60 + " Secretaria General")
    assert dictaminar(analizar_texto([cesa]), 2026)[0] == "SOLO_INCREMENTO"


def test_institucion_completa_con_acto_porcentual_y_tabla():
    import pandas as pd
    from dpcol.validar_documentos import resumen_institucion
    docs = pd.DataFrame([
        {"CODIGO_INSTITUCION": "1709", "INSTITUCION": "CENTRAL", "CARPETA_ANIO": 2026, "ARCHIVO": "acuerdo.pdf",
         "RUTA": "a", "ESTADO_DOC": "SOLO_INCREMENTO", "ACTO": "ACUERDO 34 de 2025", "FECHA_EXPEDICION": "2025-11-26",
         "VIGENCIA_DETECTADA": 2026, "VALORES_DINERO": 0, "PROGRAMAS_ENCONTRADOS": 0, "PROGRAMAS_ACTIVOS": 40},
        {"CODIGO_INSTITUCION": "1709", "INSTITUCION": "CENTRAL", "CARPETA_ANIO": 2026, "ARCHIVO": "tabla.pdf",
         "RUTA": "b", "ESTADO_DOC": "SIN_ACTO_IDENTIFICADO", "ACTO": "", "FECHA_EXPEDICION": "",
         "VIGENCIA_DETECTADA": 2026, "VALORES_DINERO": 76, "PROGRAMAS_ENCONTRADOS": 30, "PROGRAMAS_ACTIVOS": 40},
    ])
    r = resumen_institucion(docs, 2026).iloc[0]
    assert (r.ESTADO_INSTITUCION, r.TIPO_FUENTE, r.ACTO_PRINCIPAL) == ("COMPLETO", "acto+tabla", "ACUERDO 34 de 2025")
