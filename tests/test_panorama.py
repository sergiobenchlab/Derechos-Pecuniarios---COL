import pandas as pd

from dpcol.panorama import panorama, resumen_nacional


def _hecaa():
    return pd.DataFrame({
        "CODIGO_SNIES": pd.array([10, 11, 12, 13, 14], dtype="Int64"),
        "CODIGO_PADRE": pd.array([1701] * 5, dtype="Int64"),
        "CODIGO_INSTITUCION": pd.array([1701] * 5, dtype="Int64"),
        "INSTITUCION_SNIES": ["JAVERIANA"] * 5,
        "SECTOR": ["Privado"] * 5,
        "PROGRAMA_SNIES": ["A", "B", "C", "D", "E"],
        "ESTADO_PROGRAMA_SNIES": ["Activo", "Activo", "Activo", "Activo", "Inactivo"],
        "NIVEL_SNIES": ["Universitario"] * 5,
        "MODALIDAD_SNIES": ["Presencial"] * 5,
        "PERIODICIDAD_SNIES": ["Semestral", "Semestral", "Anual", "Semestral", "Semestral"],
        "COSTO_SNIES": [10_000_000, 8_000_000, 20_000_000, None, 5_000_000],
        "COSTO_SNIES_SEM": [10_000_000, 8_000_000, 10_000_000, None, 5_000_000],
    })


def test_panorama_clases_y_resumen():
    base = pd.DataFrame({
        "ID_PRGRM": [1, 2, 3, 4], "CÓDIGO_SNIES_DEL_PROGRAMA": [10, 11, 12, 13],
        "CÓDIGO_INSTITUCIÓN_PADRE": [1701] * 4, "ESTADO_OFICIAL": ["Activo"] * 4,
    })
    aud = pd.DataFrame([
        {"ANIO": "2026", "ID_PRGRM": "1", "FUENTE": "DERECHOS PECUNIARIOS", "PRC": "10000000", "PRC_HMGNZD": "10000000",
         "PRD_PRC_ORIGINAL": "Semestral", "PRC_CON_DECIMALES": "False", "ESTADO": "OK"},
        {"ANIO": "2026", "ID_PRGRM": "2", "FUENTE": "DERECHOS PECUNIARIOS", "PRC": "8440000,55", "PRC_HMGNZD": "8440000,55",
         "PRD_PRC_ORIGINAL": "Semestral", "PRC_CON_DECIMALES": "True", "ESTADO": "OK"},
        {"ANIO": "2026", "ID_PRGRM": "3", "FUENTE": "DERECHOS PECUNIARIOS", "PRC": "26000000", "PRC_HMGNZD": "13000000",
         "PRD_PRC_ORIGINAL": "Anual", "PRC_CON_DECIMALES": "False", "ESTADO": "OK"},
        {"ANIO": "2026", "ID_PRGRM": "1", "FUENTE": "SNIES", "PRC": "9500000", "PRC_HMGNZD": "",
         "PRD_PRC_ORIGINAL": "Semestral", "PRC_CON_DECIMALES": "False", "ESTADO": "SNIES"},
    ])
    val = pd.DataFrame([{"CODIGO_INSTITUCION": "1701", "ESTADO_INSTITUCION": "COMPLETO", "TIPO_FUENTE": "acto",
                         "ACTO_PRINCIPAL": "ACUERDO 781 de 2025", "FECHA_EXPEDICION": "2025-12-09"}])
    prog, inst = panorama(_hecaa(), base, aud, val, 2026)
    clases = prog.set_index("ID_PRGRM")["CLASE"].to_dict()
    assert clases == {1: "DP_IGUAL_SNIES", 2: "DP_PROYECTADO", 3: "DP_DIFERENCIA_ALTA", 4: "SIN_DP"}
    assert prog.set_index("ID_PRGRM").loc[1, "SNIES_CAMBIO_VS_BASE"] > 0.05  # SNIES actualizado desde la base
    r = inst.iloc[0]
    assert (r.PROGRAMAS_ACTIVOS_SNIES, r.ACTIVOS_CON_PRECIO_DP, r.DP_IGUAL_SNIES, r.ESTADO_DOCUMENTO) == (4, 3, 1, "COMPLETO")
    nac = resumen_nacional(_hecaa(), inst).set_index("INDICADOR")["VALOR"]
    assert nac["Programas activos en SNIES (todas las IES)"] == 4
