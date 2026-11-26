import math

import pandas as pd
import pytest

from dpcol.maestro import cargar_periodos
from dpcol.normalizar import normalizar
from dpcol.unidades import factor_semestral, unidad_canonica
from dpcol.validar import variacion_anual

PERIODOS = cargar_periodos()

MAESTRO = pd.DataFrame([
    # ID_PRGRM, créditos, períodos, periodicidad
    {"ID_PRGRM": 1, "CREDITOS": 160, "PERIODOS": 10, "PERIODICIDAD": "Semestral"},
    {"ID_PRGRM": 2, "CREDITOS": 26, "PERIODOS": 2, "PERIODICIDAD": "Semestral"},
    {"ID_PRGRM": 3, "CREDITOS": 60, "PERIODOS": 2, "PERIODICIDAD": "Anual"},
    {"ID_PRGRM": 4, "CREDITOS": 48, "PERIODOS": 6, "PERIODICIDAD": "Cuatrimestral"},
    {"ID_PRGRM": 5, "CREDITOS": 30, "PERIODOS": 2, "PERIODICIDAD": "Sin definir"},
])


def fila(prg, prd, prc, fuente, unidad, ies=10):
    return {"ID_IES": ies, "ID_PRGRM": prg, "ID_PRD": prd, "PRC": prc, "FUENTE": fuente, "PRD_PRC": unidad}


def run(filas):
    return normalizar(pd.DataFrame(filas), MAESTRO, PERIODOS).set_index(["ID_PRGRM", "ID_PRD", "FUENTE"])


def test_unidades():
    assert unidad_canonica(" Crédito ") == "Credito"
    assert unidad_canonica("SEMESTRE") == "Semestral"
    assert unidad_canonica("xyz") is None
    assert factor_semestral("Anual")[0] == 0.5
    assert factor_semestral("Cuatrimestral")[0] == 1.5
    assert factor_semestral("Credito", 160, 10, "Semestral")[0] == 16
    assert factor_semestral("Total", 26, 2, "Semestral")[0] == 0.5
    # programa anual de 2 años = 4 semestres
    assert factor_semestral("Total", 60, 2, "Anual")[0] == 0.25
    # crédito en programa anual: 30 créditos por año = 15 por semestre
    assert factor_semestral("Credito", 60, 2, "Anual")[0] == 15


def test_semestral_ok_y_fch_desde_config():
    d = run([fila(1, 61, "16.000.000", "DERECHOS PECUNIARIOS", "Semestral"),
             fila(1, 61, "16100000", "SNIES", "Semestral")])
    r = d.loc[(1, 61, "DERECHOS PECUNIARIOS")]
    assert r.PRC_HMGNZD == 16_000_000
    assert r.ESTADO == "OK"
    assert r.FCH_INC_PRD == 46023
    assert math.isnan(d.loc[(1, 61, "SNIES")].PRC_HMGNZD)  # como el T08 histórico


def test_credito_se_multiplica():
    d = run([fila(1, 61, 1_000_000, "DERECHOS PECUNIARIOS", "Credito"),
             fila(1, 61, 16_000_000, "SNIES", "Semestral")])
    r = d.loc[(1, 61, "DERECHOS PECUNIARIOS")]
    assert r.PRC_HMGNZD == 16_000_000
    assert r.ESTADO == "OK"
    assert r.PRC == 1_000_000  # el precio publicado nunca se toca


def test_total_mal_etiquetado_se_reinterpreta():
    # Especialización: 'Total' de 8M pero SNIES semestral también ~8M -> era semestral
    d = run([fila(2, 61, 8_000_000, "DERECHOS PECUNIARIOS", "Total"),
             fila(2, 61, 8_050_000, "SNIES", "Semestral")])
    r = d.loc[(2, 61, "DERECHOS PECUNIARIOS")]
    assert r.ESTADO == "UNIDAD_REINTERPRETADA"
    assert r.PRD_PRC == "Semestral"
    assert r.PRD_PRC_ORIGINAL == "Total"
    assert r.PRC_HMGNZD == 8_000_000


def test_total_real_se_divide():
    d = run([fila(1, 61, 160_000_000, "DERECHOS PECUNIARIOS", "Total"),
             fila(1, 61, 16_000_000, "SNIES", "Semestral")])
    r = d.loc[(1, 61, "DERECHOS PECUNIARIOS")]
    assert r.ESTADO == "OK"
    assert r.PRC_HMGNZD == 16_000_000


def test_anual_con_snies_anual():
    d = run([fila(3, 61, 40_000_000, "DERECHOS PECUNIARIOS", "Anual"),
             fila(3, 61, 40_000_000, "SNIES", "Anual")])
    r = d.loc[(3, 61, "DERECHOS PECUNIARIOS")]
    assert r.PRC_HMGNZD == 20_000_000
    assert r.ESTADO == "OK"
    assert r.RATIO_SNIES == pytest.approx(1.0)


def test_cuatrimestral():
    d = run([fila(4, 61, 4_000_000, "DERECHOS PECUNIARIOS", "Cuatrimestral")])
    r = d.loc[(4, 61, "DERECHOS PECUNIARIOS")]
    assert r.PRC_HMGNZD == 6_000_000
    assert r.ESTADO == "SIN_REFERENCIA_SNIES"


def test_ratio_inexplicable_se_marca_no_se_reemplaza():
    d = run([fila(1, 61, 45_000_000, "DERECHOS PECUNIARIOS", "Semestral"),
             fila(1, 61, 16_000_000, "SNIES", "Semestral")])
    r = d.loc[(1, 61, "DERECHOS PECUNIARIOS")]
    assert r.ESTADO == "REVISAR_RATIO_SNIES"
    assert r.PRC_HMGNZD == 45_000_000


def test_error_de_separadores():
    d = run([fila(1, 61, 1_600_000_000_0, "DERECHOS PECUNIARIOS", "Semestral")])
    r = d.loc[(1, 61, "DERECHOS PECUNIARIOS")]
    assert r.ESTADO == "ERROR_VALOR"
    assert math.isnan(r.PRC_HMGNZD)


def test_unidad_desconocida_y_periodicidad_supuesta():
    d = run([fila(5, 61, 9_000_000, "DERECHOS PECUNIARIOS", "rarísimo"),
             fila(5, 61, 9_000_000, "SNIES", "")])
    r = d.loc[(5, 61, "DERECHOS PECUNIARIOS")]
    assert r.ESTADO == "UNIDAD_ASUMIDA"
    assert r.PRC_HMGNZD == 9_000_000


def test_sin_maestro():
    d = run([fila(999, 61, 1_000_000, "DERECHOS PECUNIARIOS", "Credito")])
    r = d.loc[(999, 61, "DERECHOS PECUNIARIOS")]
    assert r.ESTADO == "REVISAR_SIN_MAESTRO"
    assert not r.EN_MAESTRO


def test_variacion_anual():
    d = normalizar(pd.DataFrame([
        fila(1, 57, 10_000_000, "DERECHOS PECUNIARIOS", "Semestral"),
        fila(1, 59, 10_500_000, "DERECHOS PECUNIARIOS", "Semestral"),
        fila(1, 61, 15_000_000, "DERECHOS PECUNIARIOS", "Semestral"),
    ]), MAESTRO, PERIODOS)
    v = variacion_anual(d).set_index("ID_PRD")
    assert v.loc[59, "VAR_ANUAL"] == pytest.approx(0.05)
    assert not v.loc[59, "ALERTA_VARIACION"]
    assert v.loc[61, "ALERTA_VARIACION"]


def test_programa_anual_precio_semestral_ambiguo():
    d = run([fila(3, 61, 40_000_000, "DERECHOS PECUNIARIOS", "Semestral"),
             fila(3, 61, 40_000_000, "SNIES", "Anual")])
    r = d.loc[(3, 61, "DERECHOS PECUNIARIOS")]
    assert r.ESTADO == "REVISAR_PERIODICIDAD"
    assert r.PRC_HMGNZD == 40_000_000  # no se cambia sin evidencia


def test_marca_decimales():
    d = run([fila(1, 61, "5311993,547", "DERECHOS PECUNIARIOS", "Semestral")])
    r = d.loc[(1, 61, "DERECHOS PECUNIARIOS")]
    assert r.PRC == pytest.approx(5311993.547)
    assert r.PRC_CON_DECIMALES
