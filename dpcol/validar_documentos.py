"""Valida que los documentos fuente de un año de precios sean el acto correcto
y estén completos.

Para los precios del año N se espera un acto administrativo (acuerdo,
resolución, acta) expedido normalmente en noviembre o diciembre de N-1, que
diga explícitamente que fija valores para N, con tablas de valores, todas sus
páginas y su cierre/firma.

Caso de referencia (Universidad Simón Bolívar, 2026):
  - "PRECIOS 2026.pdf": escaneado; OCR -> Acuerdo de Sala General No. 65 de
    2025 (noviembre 28), "valores de matrícula ... para el año 2026",
    "Página 1 de 9" con 9 páginas, cierre "Dado en ... 28 de noviembre de 2025".
    -> OK.
  - "SIMON_BOLIVAR_2026.pdf": Reglamento de Derechos Pecuniarios, Acuerdo 58
    de 2019 actualizado en 2021, sin tabla de valores -> SIN_PRECIOS.
"""
from __future__ import annotations

import io
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}
_M = "|".join(MESES)


def _plano(t: str) -> str:
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t.lower()


# ---------------------------------------------------------------- extracción

def extraer_paginas(ruta: Path, ocr: bool = True, dpi: int = 200, min_chars: int = 80, idioma: str = "spa") -> tuple[list[str], list[bool]]:
    """Texto por página. Usa la capa de texto del PDF y, si una página casi no
    tiene texto (escaneada), la pasa por OCR. Devuelve (textos, usó_ocr)."""
    import fitz  # PyMuPDF

    textos, usados = [], []
    with fitz.open(ruta) as doc:
        for pag in doc:
            t = pag.get_text("text") or ""
            usado = False
            if ocr and len(t.strip()) < min_chars:
                try:
                    import pytesseract
                    from PIL import Image

                    pix = pag.get_pixmap(dpi=dpi)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    t = pytesseract.image_to_string(img, lang=idioma)
                    usado = True
                except Exception as e:  # OCR no disponible
                    t = t + f"\n[OCR_ERROR {e}]"
            textos.append(t)
            usados.append(usado)
    return textos, usados


def extraer_con_cache(ruta: Path, cache: Path | None, sha: str | None, **kw) -> tuple[list[str], list[bool]]:
    sep = "\n\f<<PAGINA>>\n"
    if cache and sha:
        f = cache / f"{sha}.txt"
        if f.exists():
            partes = f.read_text(encoding="utf-8").split(sep)
            usados = [p.startswith("[OCR]") for p in partes]
            return [p[5:] if p.startswith("[OCR]") else p for p in partes], usados
    textos, usados = extraer_paginas(ruta, **kw)
    if cache and sha:
        cache.mkdir(parents=True, exist_ok=True)
        (cache / f"{sha}.txt").write_text(
            sep.join(("[OCR]" + t) if u else t for t, u in zip(textos, usados)), encoding="utf-8"
        )
    return textos, usados


# ------------------------------------------------------------------ análisis

_RE_ACTO = re.compile(
    r"(acuerdo|resolucion|acta)\b[^\n]{0,60}?\bn(?:o|um|umero|°|º)?\s*[.:°º]?\s*(\d{1,5}[a-z]?)"
    r"(?:\s*[-/]\s*\d{1,4})?\s*(?:de|del|-|/)\s*(?:\d{1,2}\s+de\s+(?:" + _M + r")\s+de\s+)?(20\d{2})",
)
_RE_ACTO_SIMPLE = re.compile(r"(acuerdo|resolucion|acta)[^\n]{0,40}?\b(\d{1,5})\s+(?:de|del)\s+(20\d{2})")
_RE_DADO = re.compile(
    r"(?:dad[oa]|expedid[oa]|aprobad[oa]|firmad[oa])\b[^\n]{0,120}?"
    r"(?:\(?(\d{1,2})\)?\s*(?:dias?\s+del?\s+mes\s+de\s+|de\s+)?)(" + _M + r")\s+(?:de|del)\s+(?:ano\s+)?(20\d{2})",
    re.S,
)
_RE_FECHA = re.compile(r"\b(\d{1,2})\s*(?:\(\d{1,2}\)\s*)?(?:de\s+)?(" + _M + r")\s+(?:de|del)\s+(20\d{2})")
_RE_FECHA_MES_DIA = re.compile(r"\(\s*(" + _M + r")\s+(\d{1,2})\s*(?:de\s+(20\d{2}))?\s*\)")
_RE_FECHA_MDA = re.compile(r"\b(" + _M + r")\s+(\d{1,2})\s*(?:,|de|del)\s*(20\d{2})")
_RE_PAGINA = re.compile(r"pagina\s*(\d{1,3})\s*(?:de|/)\s*(\d{1,3})")
_RE_CIERRE = re.compile(r"(dad[oa] en|comuniquese|publiquese|cumplase|para constancia|firman?\b|secretari[oa] general|rector)")
_RE_DINERO = re.compile(r"\$\s*\d{1,3}(?:[.,\s]\d{3})+|\b\d{1,3}(?:[.,]\d{3}){2,}\b")
_RE_REGLAMENTO = re.compile(r"\breglamento\b")


def _vigencias(t: str) -> Counter:
    c: Counter = Counter()
    pats = [
        r"para el (?:ano|periodo|periodo academico|semestre)?\s*(?:academico\s*)?(20\d{2})",
        r"vigencia\s*(?:del?\s*)?(?:ano\s*)?(20\d{2})",
        r"(?:ano|anualidad)\s+(20\d{2})",
        r"(?:periodo|semestre)s?\s*(?:academicos?\s*)?(?:del?\s*)?(20\d{2})\s*[-–]\s*[12i]\b",
        r"\b(20\d{2})\s*[-–]\s*(?:0?[12]|i{1,2})\b",
        r"a partir del?[^\n]{0,60}?(20\d{2})",
    ]
    for p in pats:
        for m in re.finditer(p, t):
            c[int(m.group(1))] += 1
    return c


@dataclass
class Analisis:
    paginas: int
    paginas_ocr: int
    caracteres: int
    tipo_acto: str | None
    numero_acto: str | None
    anio_acto: int | None
    fecha_expedicion: date | None
    origen_fecha: str | None
    vigencia: int | None
    vigencias_mencionadas: str
    paginas_declaradas: int | None
    tiene_cierre: bool
    valores_dinero: int
    es_reglamento: bool


def _fecha(d, mes, a) -> date | None:
    try:
        return date(int(a), MESES[mes], int(d))
    except (ValueError, KeyError, TypeError):
        return None


def analizar_texto(paginas: list[str], usados_ocr: list[bool] | None = None) -> Analisis:
    planos = [_plano(p) for p in paginas]
    todo = "\n".join(planos)
    cabecera = "\n".join(planos[:2])[:6000]
    ultima = "\n".join(planos[-2:])

    tipo = num = None
    anio_acto = None
    m = _RE_ACTO.search(cabecera) or _RE_ACTO_SIMPLE.search(cabecera) or _RE_ACTO.search(todo)
    if m:
        tipo, num, anio_acto = m.group(1).upper(), m.group(2), int(m.group(3))

    fecha, origen = None, None
    dados = [_fecha(*x.groups()) for x in _RE_DADO.finditer(ultima)] or [_fecha(*x.groups()) for x in _RE_DADO.finditer(todo)]
    dados = [d for d in dados if d]
    if dados:
        fecha, origen = dados[-1], "cierre"
    if not fecha and m:
        # fecha del encabezado tras el número de acto: "(noviembre 28)", "28 de noviembre de 2025"
        ventana = cabecera[m.start(): m.end() + 600]
        md = _RE_FECHA_MES_DIA.search(ventana)
        fd = _RE_FECHA.search(ventana)
        fm = _RE_FECHA_MDA.search(ventana)
        candidatos = []
        if md:
            candidatos.append((md.start(), _fecha(md.group(2), md.group(1), md.group(3) or anio_acto)))
        if fd:
            candidatos.append((fd.start(), _fecha(*fd.groups())))
        if fm:
            candidatos.append((fm.start(), _fecha(fm.group(2), fm.group(1), fm.group(3))))
        candidatos = [c for c in candidatos if c[1]]
        if candidatos:
            fecha, origen = min(candidatos)[1], "encabezado"
    if not fecha:
        fd = _RE_FECHA.search(cabecera)
        fm = _RE_FECHA_MDA.search(cabecera)
        cand = [(x.start(), f) for x, f in ((fd, _fecha(*fd.groups()) if fd else None),
                                              (fm, _fecha(fm.group(2), fm.group(1), fm.group(3)) if fm else None)) if f]
        if cand:
            fecha, origen = min(cand)[1], "primera_fecha"

    vig = _vigencias(todo)
    vigencia = None
    if vig:
        base = anio_acto or (fecha.year if fecha else None)
        candidatos = {a: n for a, n in vig.items() if base is None or a >= base}
        if candidatos:
            vigencia = max(candidatos, key=lambda a: (candidatos[a], a))

    decl = [int(b) for a, b in _RE_PAGINA.findall(todo) if 0 < int(a) <= int(b) < 500]
    paginas_decl = Counter(decl).most_common(1)[0][0] if decl else None

    titulo = cabecera[:1500]
    return Analisis(
        paginas=len(paginas),
        paginas_ocr=sum(usados_ocr or []),
        caracteres=sum(len(p.strip()) for p in paginas),
        tipo_acto=tipo,
        numero_acto=num,
        anio_acto=anio_acto,
        fecha_expedicion=fecha,
        origen_fecha=origen,
        vigencia=vigencia,
        vigencias_mencionadas=", ".join(f"{a}:{n}" for a, n in sorted(vig.items())),
        paginas_declaradas=paginas_decl,
        tiene_cierre=bool(_RE_CIERRE.search(ultima)),
        valores_dinero=len(_RE_DINERO.findall(todo)),
        es_reglamento=bool(_RE_REGLAMENTO.search(titulo)),
    )


# ---------------------------------------------------------------- dictamen

ORDEN_GRAVEDAD = [
    "NO_LEGIBLE", "SIN_PRECIOS", "VIGENCIA_DISTINTA", "INCOMPLETO_PAGINAS",
    "FECHA_FUERA_DE_RANGO", "SIN_ACTO_IDENTIFICADO", "SIN_FECHA", "SIN_CIERRE",
    "FECHA_TARDIA", "FECHA_TEMPRANA", "VIGENCIA_NO_EXPLICITA", "OK",
]


def dictaminar(a: Analisis, anio_objetivo: int, min_valores: int = 8) -> tuple[str, list[str]]:
    obs: list[str] = []
    if a.caracteres < 200:
        return "NO_LEGIBLE", ["sin texto útil ni con OCR"]
    if a.valores_dinero < min_valores:
        obs.append("SIN_PRECIOS")
        if a.es_reglamento:
            obs.append("es un reglamento, no un acto que fija valores")
    if a.vigencia is None:
        obs.append("VIGENCIA_NO_EXPLICITA")
    elif a.vigencia != anio_objetivo:
        obs.append("VIGENCIA_DISTINTA")
    if a.paginas_declaradas and a.paginas_declaradas > a.paginas:
        obs.append("INCOMPLETO_PAGINAS")
    if not a.tipo_acto:
        obs.append("SIN_ACTO_IDENTIFICADO")
    f = a.fecha_expedicion
    if not f:
        obs.append("SIN_FECHA")
    else:
        if f.year == anio_objetivo - 1:
            if f.month < 11:
                obs.append("FECHA_TEMPRANA")
        elif f.year == anio_objetivo and f.month <= 3:
            obs.append("FECHA_TARDIA")
        else:
            obs.append("FECHA_FUERA_DE_RANGO")
    if not a.tiene_cierre:
        obs.append("SIN_CIERRE")
    codigos = [o for o in obs if o in ORDEN_GRAVEDAD]
    estado = min(codigos, key=ORDEN_GRAVEDAD.index) if codigos else "OK"
    return estado, obs


# ------------------------------------------------------------- cobertura

def cobertura_programas(texto: str, programas: list[str]) -> tuple[int, int]:
    """Cuántos nombres de programa (normalizados) aparecen literalmente en el texto."""
    t = re.sub(r"[^a-z0-9]+", " ", _plano(texto))
    t = " " + re.sub(r"\s+", " ", t) + " "
    vistos = 0
    nombres = {re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", _plano(p))).strip() for p in programas if p}
    for n in nombres:
        n2 = re.sub(r"^(especializacion|maestria|doctorado|tecnologia|tecnico profesional)( en)? ", "", n)
        if f" {n} " in t or (len(n2) > 6 and f" {n2} " in t):
            vistos += 1
    return vistos, len(nombres)


# --------------------------------------------------------------- recorrido

def validar_carpeta(
    documentos: Path,
    anio_objetivo: int,
    carpetas_anio: tuple[int, ...] | None = None,
    programas_por_inst: dict[str, list[str]] | None = None,
    cache: Path | None = None,
    ocr: bool = True,
    solo: set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Valida los PDF en <documentos>/<CÓD>-<IES>/<año>/ para los años en
    `carpetas_anio` (por defecto N-1 y N). Devuelve (por_documento, por_institucion)."""
    from .organizar import sha256

    carpetas_anio = carpetas_anio or (anio_objetivo - 1, anio_objetivo)
    filas = []
    for inst_dir in sorted(p for p in documentos.iterdir() if p.is_dir() and not p.name.startswith("_")):
        cod = inst_dir.name.split("-", 1)[0]
        if solo and cod not in solo:
            continue
        for anio in carpetas_anio:
            d = inst_dir / str(anio)
            if not d.is_dir():
                continue
            for f in sorted(d.iterdir()):
                if f.name.startswith(".") or not f.is_file():
                    continue
                fila = {"CODIGO_INSTITUCION": cod, "INSTITUCION": inst_dir.name.split("-", 1)[-1],
                        "CARPETA_ANIO": anio, "ARCHIVO": f.name, "RUTA": str(f.relative_to(documentos))}
                if f.suffix.lower() != ".pdf":
                    fila.update({"ESTADO_DOC": "NO_PDF", "OBSERVACIONES": f"archivo {f.suffix}: revisar manualmente"})
                    filas.append(fila)
                    continue
                try:
                    sha = sha256(f)
                    paginas, usados = extraer_con_cache(f, cache, sha, ocr=ocr)
                except Exception as e:
                    fila.update({"ESTADO_DOC": "ERROR_LECTURA", "OBSERVACIONES": str(e)[:200]})
                    filas.append(fila)
                    continue
                a = analizar_texto(paginas, usados)
                estado, obs = dictaminar(a, anio_objetivo)
                if anio != anio_objetivo and a.vigencia == anio:
                    # acto del año de su carpeta (p. ej. precios 2025 en 2025/): correcto, no es del objetivo
                    estado, obs = "OTRO_ANIO_OK", [f"acto de precios {anio}, bien ubicado"]
                vistos = total = None
                if programas_por_inst and cod in programas_por_inst:
                    vistos, total = cobertura_programas("\n".join(paginas), programas_por_inst[cod])
                fila.update({
                    "ESTADO_DOC": estado,
                    "OBSERVACIONES": "; ".join(obs),
                    "ACTO": f"{a.tipo_acto} {a.numero_acto} de {a.anio_acto}" if a.tipo_acto else "",
                    "FECHA_EXPEDICION": a.fecha_expedicion.isoformat() if a.fecha_expedicion else "",
                    "ORIGEN_FECHA": a.origen_fecha or "",
                    "VIGENCIA_DETECTADA": a.vigencia,
                    "VIGENCIAS_MENCIONADAS": a.vigencias_mencionadas,
                    "PAGINAS": a.paginas,
                    "PAGINAS_DECLARADAS": a.paginas_declaradas,
                    "PAGINAS_OCR": a.paginas_ocr,
                    "TIENE_CIERRE": a.tiene_cierre,
                    "VALORES_DINERO": a.valores_dinero,
                    "PROGRAMAS_ENCONTRADOS": vistos,
                    "PROGRAMAS_ACTIVOS": total,
                    "CARPETA_SUGERIDA": a.vigencia if (a.vigencia and a.vigencia != anio and estado not in ("SIN_PRECIOS", "NO_LEGIBLE")) else "",
                    "SHA256": sha,
                })
                filas.append(fila)
    docs = pd.DataFrame(filas)
    return docs, resumen_institucion(docs, anio_objetivo)


_VALIDOS = {"OK", "FECHA_TEMPRANA", "FECHA_TARDIA", "VIGENCIA_NO_EXPLICITA", "SIN_CIERRE", "SIN_FECHA", "SIN_ACTO_IDENTIFICADO"}


def resumen_institucion(docs: pd.DataFrame, anio_objetivo: int) -> pd.DataFrame:
    if docs.empty:
        return docs
    filas = []
    for (cod, inst), g in docs.groupby(["CODIGO_INSTITUCION", "INSTITUCION"]):
        vig = pd.to_numeric(g.get("VIGENCIA_DETECTADA"), errors="coerce")
        del_anio = g[(vig == anio_objetivo) | ((g["CARPETA_ANIO"] == anio_objetivo) & vig.isna())]
        validos = del_anio[del_anio["ESTADO_DOC"].isin(_VALIDOS)]
        limpios = validos[validos["ESTADO_DOC"] == "OK"]
        if len(limpios):
            estado = "COMPLETO"
        elif len(validos):
            estado = "REVISAR"
        elif (g["ESTADO_DOC"] == "NO_PDF").any():
            estado = "SOLO_TABULAR"
        else:
            estado = "FALTA_ACTO"
        mejor = (limpios if len(limpios) else validos).head(1)
        enc = pd.to_numeric(validos.get("PROGRAMAS_ENCONTRADOS"), errors="coerce").max() if len(validos) else None
        tot = pd.to_numeric(g.get("PROGRAMAS_ACTIVOS"), errors="coerce").max()
        filas.append({
            "CODIGO_INSTITUCION": cod, "INSTITUCION": inst, "ESTADO_INSTITUCION": estado,
            "DOCUMENTOS_REVISADOS": len(g), "DOCUMENTOS_VALIDOS": len(validos),
            "ACTO_PRINCIPAL": mejor["ACTO"].iat[0] if len(mejor) else "",
            "FECHA_EXPEDICION": mejor["FECHA_EXPEDICION"].iat[0] if len(mejor) else "",
            "ARCHIVO_PRINCIPAL": mejor["RUTA"].iat[0] if len(mejor) else "",
            "MAX_PROGRAMAS_ENCONTRADOS_EN_UN_DOC": enc, "PROGRAMAS_ACTIVOS": tot,
            "PROBLEMAS": "; ".join(sorted(set(g.loc[~g["ESTADO_DOC"].isin(["OK", "OTRO_ANIO_OK"]), "ESTADO_DOC"]))),
        })
    orden = {"FALTA_ACTO": 0, "SOLO_TABULAR": 1, "REVISAR": 2, "COMPLETO": 3}
    out = pd.DataFrame(filas)
    return out.sort_values("ESTADO_INSTITUCION", key=lambda s: s.map(orden)).reset_index(drop=True)


def programas_activos_por_institucion(base: pd.DataFrame) -> dict[str, list[str]]:
    """CÓDIGO_INSTITUCIÓN_PADRE -> nombres de programas activos, desde la base ancha."""
    b = base.copy()
    b.columns = [str(c).strip() for c in b.columns]
    estado = b.get("ESTADO_OFICIAL", b.get("ESTADO"))
    if estado is not None:
        b = b[estado.astype(str).str.strip().str.lower() == "activo"]
    cod = pd.to_numeric(b["CÓDIGO_INSTITUCIÓN_PADRE"], errors="coerce").astype("Int64").astype(str)
    return b.assign(_c=cod).groupby("_c")["NOMBRE_DEL_PROGRAMA"].apply(lambda s: sorted(set(s.dropna().astype(str)))).to_dict()
