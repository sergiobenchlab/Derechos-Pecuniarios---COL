"""Extracción de precios de matrícula desde los actos/tablas validados.

Dos estrategias, en orden:
  1. Tablas (PDF con capa de texto, vía pdfplumber): cada fila se cruza con
     los programas de la institución por código SNIES (si la tabla lo trae) o
     por nombre. Se descartan columnas de matrícula extraordinaria,
     descuentos, año anterior, incrementos e inscripción.
  2. Líneas de texto (sirve para OCR): "Nombre del programa  $ 20.511.000".
     Se ignoran líneas de descuento/neto/total/inscripción.

Cada precio queda con archivo, página, método, tipo de cruce y el texto de la
fila, para auditoría. No reemplaza nada: produce un staging que luego pasa
por el normalizador.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

from .io import a_numero, parsear_numero

_RE_MONTO = re.compile(r"\$?\s*\d{1,3}(?:['’]\d{3})?(?:[.,]\d{3})+(?:,\d{1,2})?(?![\d.,]*\d)")
_EXCLUIR_COL = re.compile(r"extraordinari|descuento|anterior|incremento|variaci|%|inscripci|reserva|neto|2024|2025|seguro|carne")
_EXCLUIR_LINEA = re.compile(r"^\W*(\(-\)|descuento|neto|total|subtotal|inscripci|derechos? de grado|seguro|carne|certificad|"
                            r"duplicad|supletori|habilitaci|validaci|homologaci|curso|examen|multa|reingreso)")
_STOP = {"programa", "de", "del", "la", "las", "los", "el", "en", "y", "e", "a", "con", "para", "por", "profesional",
         "universitario", "modalidad", "presencial", "virtual", "distancia"}
_NIVELES = re.compile(r"^(especializacion|maestria|doctorado|tecnologia|tecnico profesional|licenciatura)( en)? ")


def plano(t) -> str:
    t = unicodedata.normalize("NFKD", str(t or ""))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", t)).strip()


def clave_nombre(t) -> str:
    return " ".join(w for w in plano(t).split() if w not in _STOP)


def montos(texto) -> list[float]:
    # el apóstrofo de millones ("8'450.000") se quita antes de interpretar separadores
    vals = [parsear_numero(re.sub(r"['’]", ".", m.group(0))) for m in _RE_MONTO.finditer(str(texto or ""))]
    return [v for v in vals if v == v and 50_000 <= v <= 400_000_000]


@dataclass
class Programa:
    id_prgrm: int
    codigo_snies: int | None
    nombre: str
    municipio: str = ""
    modalidad: str = ""
    nivel: str = ""
    clave: str = field(init=False)

    def __post_init__(self):
        self.clave = clave_nombre(self.nombre)


class Cruzador:
    """Cruza filas/lineas con los programas de una institución."""

    def __init__(self, programas: list[Programa]):
        self.programas = programas
        self.por_snies = {p.codigo_snies: p for p in programas if p.codigo_snies}
        self.por_clave: dict[str, list[Programa]] = {}
        for p in programas:
            self.por_clave.setdefault(p.clave, []).append(p)

    def por_codigo(self, celdas: list[str]) -> Programa | None:
        for c in celdas:
            s = re.sub(r"\D", "", str(c or ""))
            if 2 <= len(s) <= 6 and s == str(c or "").strip() and int(s) in self.por_snies:
                return self.por_snies[int(s)]
        return None

    def por_nombre(self, texto: str, contexto: str = "") -> tuple[list[Programa], str]:
        k = clave_nombre(texto)
        if not k or len(k) < 4:
            return [], ""
        cands = self.por_clave.get(k)
        tipo = "nombre_exacto"
        if not cands:
            # sin prefijo de nivel ("especializacion en X" vs "X")
            k2 = _NIVELES.sub("", k)
            cands = [p for p in self.programas if _NIVELES.sub("", p.clave) == k2 and len(k2) > 5]
            tipo = "nombre_sin_nivel"
        if not cands:
            mejores = sorted(((SequenceMatcher(None, k, p.clave).ratio(), p) for p in self.programas),
                             key=lambda x: -x[0])
            if mejores and mejores[0][0] >= 0.94 and (len(mejores) == 1 or mejores[1][0] < mejores[0][0] - 0.03):
                cands = [mejores[0][1]]
                tipo = "nombre_aproximado"
        if cands and len(cands) > 1 and contexto:
            ctx = plano(contexto)
            filtrados = [p for p in cands if (p.municipio and plano(p.municipio) in ctx)]
            if filtrados:
                cands = filtrados
                tipo += "+municipio"
        if cands and len(cands) > 1:
            tipo += "_multiple"
        return cands or [], tipo


def _unidad(texto: str) -> str:
    t = plano(texto)
    if re.search(r"valor (del )?credito|por credito", t):
        return "Credito"
    if re.search(r"\banual\b|por ano|valor anual", t):
        return "Anual"
    return "Semestral"


def _columnas_validas(encabezados: list[str]) -> list[int]:
    validas = [i for i, h in enumerate(encabezados) if not _EXCLUIR_COL.search(plano(h))]
    con_2026 = [i for i in validas if "2026" in encabezados[i]]
    return con_2026 or validas


def extraer_tablas(pdf_path: Path, cruz: Cruzador) -> list[dict]:
    import pdfplumber

    filas = []
    with pdfplumber.open(pdf_path) as pdf:
        for npag, pg in enumerate(pdf.pages, start=1):
            for tabla in pg.extract_tables() or []:
                if not tabla or len(tabla[0]) < 2:
                    continue
                ncol = max(len(r) for r in tabla)
                enc = [""] * ncol
                cuerpo = []
                for r in tabla:
                    r = [(c or "").replace("\n", " ").strip() for c in r] + [""] * (ncol - len(r))
                    if not any(montos(c) for c in r):
                        enc = [(enc[i] + " " + r[i]).strip() for i in range(ncol)]
                    else:
                        cuerpo.append(r)
                # encabezados combinados: la celda vacía hereda el texto de la izquierda
                enc_ext = list(enc)
                for i in range(1, ncol):
                    if not enc_ext[i] and enc_ext[i - 1]:
                        enc_ext[i] = enc_ext[i - 1]
                for r in cuerpo:
                    if _EXCLUIR_LINEA.search(plano(" ".join(r[:2]))):
                        continue
                    cols_monto = [i for i, c in enumerate(r) if montos(c)]
                    if not cols_monto:
                        continue
                    buenas = [i for i in cols_monto if i in _columnas_validas(enc_ext)] or cols_monto[:1]
                    valor = montos(r[buenas[0]])[0]
                    prog = cruz.por_codigo(r)
                    if prog:
                        cands, tipo = [prog], "codigo_snies"
                    else:
                        texto = " ".join(c for i, c in enumerate(r) if i not in cols_monto and not montos(c))
                        nombre = max((c for i, c in enumerate(r) if i < cols_monto[0]), key=len, default="")
                        cands, tipo = cruz.por_nombre(nombre, contexto=texto)
                    if not cands:
                        continue
                    for p in cands:
                        filas.append({"ID_PRGRM": p.id_prgrm, "PRC": valor, "PRD_PRC": _unidad(enc_ext[buenas[0]]),
                                      "PAGINA": npag, "METODO": "tabla", "CRUCE": tipo,
                                      "ENCABEZADO": enc_ext[buenas[0]][:80], "TEXTO_FILA": " | ".join(r)[:300]})
    return filas


_RE_SECCION_CREDITO = re.compile(r"valor\s+(?:del?\s+)?credito|por credito")
_RE_SECCION_SEMESTRE = re.compile(r"valor\s+(?:del?\s+)?semestre|valor\s+matricula|matricula\s+semestral|valor\s+20\d\d")
_RE_DOLAR_OCR = re.compile(r"(?<![\d$.,])5(\d{1,3}(?:\.\d{3}){1,2})(?![\d.,]*\d)")


def _corregir_dolar_ocr(linea: str, doc_usa_dolar: bool) -> str:
    """OCR: '$15.858.000' leído como '515.858.000'. Solo si el documento usa '$'
    y la línea no tiene ningún '$'."""
    if doc_usa_dolar and "$" not in linea:
        return _RE_DOLAR_OCR.sub(lambda m: "$" + m.group(1), linea)
    return linea


def _limpiar_nombre(nombre: str) -> str:
    # quita números sueltos al final (créditos o semestres antes del valor) y signos
    return re.sub(r"(?:\s+\d{1,3}){1,2}\s*$", "", nombre.strip(" |:-$\t")).strip()


def extraer_lineas(paginas: list[str], cruz: Cruzador) -> list[dict]:
    filas = []
    unidad_doc = _unidad(" ".join(paginas[:2]))
    usa_dolar = sum(p.count("$") for p in paginas) >= 3
    for npag, txt in enumerate(paginas, start=1):
        lineas = [_corregir_dolar_ocr(l, usa_dolar) for l in txt.splitlines()]
        previa = ""
        unidad = unidad_doc
        for k, linea in enumerate(lineas):
            lp = plano(linea)
            vals = montos(linea)
            if not vals:
                if _RE_SECCION_CREDITO.search(lp):
                    unidad = "Credito"
                elif _RE_SECCION_SEMESTRE.search(lp):
                    unidad = "Semestral"
                previa = linea if len(linea.strip()) > 3 else previa
                continue
            if _EXCLUIR_LINEA.search(lp):
                continue
            ms = list(_RE_MONTO.finditer(linea))
            nombre = _limpiar_nombre(linea[: ms[0].start()])
            if len(clave_nombre(nombre)) < 4 and previa:
                nombre = _limpiar_nombre(previa)  # el nombre quedó en la línea anterior
            cands, tipo = cruz.por_nombre(nombre)
            siguiente = lineas[k + 1] if k + 1 < len(lineas) else ""
            if (not cands or tipo == "nombre_aproximado") and siguiente and not montos(siguiente) and len(siguiente.strip()) < 60:
                c2, t2 = cruz.por_nombre(nombre + " " + siguiente.strip())  # nombre partido en dos líneas
                if c2 and (not cands or "exacto" in t2):
                    cands, tipo = c2, t2 + "+continuacion"
            if not cands:
                continue
            for p in cands:
                filas.append({"ID_PRGRM": p.id_prgrm, "PRC": vals[0], "PRD_PRC": unidad, "PAGINA": npag,
                              "METODO": "lineas", "CRUCE": tipo, "ENCABEZADO": "", "TEXTO_FILA": linea.strip()[:300]})
            previa = ""
    return filas


_RE_TITULO_MQ = re.compile(r"medico[s]?\s*(?:y\s*)?quirurgic|especialidades medic")
_RE_TITULO_TODOS = re.compile(r"todos los programas|para todos los programas|por estudiante para todos")


def extraer_valor_unico(paginas: list[str], cruz: Cruzador) -> list[dict]:
    """Actos que fijan un solo valor de matrícula para un grupo de programas:
    p. ej. Rosario Acuerdo 325 (especialidades médico-quirúrgicas: 'Matrícula $21.855.000')
    o un valor por estudiante para todos los programas. Se asigna a los programas
    del grupo; los que reciban precio por otra vía tienen prioridad en consolidar()."""
    todo = "\n".join(paginas)
    titulo = plano(todo[:2500])
    if _RE_TITULO_MQ.search(titulo):
        grupo = [p for p in cruz.programas if re.search(r"medico", plano(p.nivel))]
        etiqueta = "valor_unico_mq"
    elif _RE_TITULO_TODOS.search(plano(todo)):
        grupo = list(cruz.programas)
        etiqueta = "valor_unico_todos"
    else:
        return []
    vals = set()
    pag_val, txt_val = None, ""
    for npag, txt in enumerate(paginas, start=1):
        for linea in txt.splitlines():
            lp = plano(linea)
            if re.search(r"\bmatricula\b|valor de la matricula", lp) and not _EXCLUIR_LINEA.search(lp):
                v = montos(linea)
                if v:
                    vals.add(round(v[0], -3))
                    pag_val, txt_val = pag_val or npag, txt_val or linea.strip()
    if len(vals) != 1 or not grupo:
        return []
    valor = vals.pop()
    return [{"ID_PRGRM": p.id_prgrm, "PRC": valor, "PRD_PRC": "Semestral", "PAGINA": pag_val, "METODO": "valor_unico",
             "CRUCE": etiqueta, "ENCABEZADO": "", "TEXTO_FILA": txt_val[:300]} for p in grupo]


def programas_institucion(base: pd.DataFrame, codigo_padre: str) -> list[Programa]:
    b = base.copy()
    b.columns = [str(c).strip() for c in b.columns]
    b = b[a_numero(b["CÓDIGO_INSTITUCIÓN_PADRE"]).astype("Int64").astype(str) == str(codigo_padre)]
    out = []
    for _, r in b.iterrows():
        cs = parsear_numero(r.get("CÓDIGO_SNIES_DEL_PROGRAMA"))
        idp = parsear_numero(r.get("ID_PRGRM"))
        if idp != idp:
            continue
        out.append(Programa(int(idp), int(cs) if cs == cs else None, str(r.get("NOMBRE_DEL_PROGRAMA") or ""),
                            str(r.get("MUNICIPIO_OFERTA_PROGRAMA") or ""), str(r.get("MODALIDAD") or ""),
                            str(r.get("NIVEL_DE_FORMACIÓN") or "")))
    return out


def consolidar(filas: list[dict]) -> pd.DataFrame:
    """Una fila por programa. Prioriza cruce por código y método tabla; si un
    programa recibe precios distintos se marca CONFLICTO y se toma el más frecuente."""
    if not filas:
        return pd.DataFrame()
    df = pd.DataFrame(filas)
    prio = {"codigo_snies": 0}
    df["_p"] = df["CRUCE"].map(lambda c: prio.get(c, 3 if c.startswith("valor_unico") else
                                         1 if "exacto" in c and "multiple" not in c else 2))
    df["_m"] = (df["METODO"] != "tabla").astype(int)
    out = []
    for idp, g in df.groupby("ID_PRGRM"):
        g = g.sort_values(["_p", "_m", "PAGINA"])
        mejor = g[g["_p"] == g["_p"].min()]
        vals = mejor["PRC"].round(-2).value_counts()
        fila = mejor.iloc[0].to_dict()
        fila["PRC"] = float(mejor[mejor["PRC"].round(-2) == vals.index[0]]["PRC"].iloc[0])
        fila["N_COINCIDENCIAS"] = len(g)
        fila["CONFLICTO"] = len(vals) > 1
        fila["VALORES_ALTERNOS"] = "; ".join(f"{v:,.0f}" for v in vals.index[1:4])
        out.append(fila)
    return pd.DataFrame(out).drop(columns=["_p", "_m"])


def a_staging(consolidado: pd.DataFrame, base: pd.DataFrame, id_prd: int) -> pd.DataFrame:
    """Convierte la extracción consolidada en filas de staging (formato largo T08)
    listas para dpcol.normalizar, con trazabilidad del documento."""
    if consolidado.empty:
        return consolidado
    b = base.copy()
    b.columns = [str(c).strip() for c in b.columns]
    ies = pd.DataFrame({"ID_PRGRM": a_numero(b["ID_PRGRM"]), "ID_IES": a_numero(b["ID_IES"])}).dropna().drop_duplicates("ID_PRGRM")
    ies["ID_PRGRM"] = ies["ID_PRGRM"].astype("int64")
    c = consolidado.copy()
    c["ID_PRGRM"] = c["ID_PRGRM"].astype("int64")
    c = c.merge(ies, on="ID_PRGRM", how="left")
    return pd.DataFrame({
        "ID_IES": c["ID_IES"], "ID_PRGRM": c["ID_PRGRM"], "ID_PRD": id_prd, "PRC": c["PRC"],
        "FUENTE": "DERECHOS PECUNIARIOS", "PRD_PRC": c["PRD_PRC"],
        "ARCHIVO_FUENTE": c.get("ARCHIVO"), "PAGINA_FUENTE": c["PAGINA"], "METODO_EXTRACCION": c["METODO"],
        "CRUCE": c["CRUCE"], "CONFLICTO": c["CONFLICTO"], "VALORES_ALTERNOS": c["VALORES_ALTERNOS"],
        "TEXTO_FUENTE": c["TEXTO_FILA"],
    })
