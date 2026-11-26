"""Organiza los documentos fuente (PDF, XLSX, CSV...) en una estructura única

    <destino>/<CÓDIGO>-<NOMBRE INSTITUCIÓN>/<AÑO>/<CÓDIGO>_<AÑO>_<descripción>.<ext>

y genera un inventario con la ruta original, institución, año, huella SHA-256
y duplicados. Nunca mueve ni borra los originales: copia (en macOS con
clonación APFS, que no ocupa espacio adicional).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

EXT_DOCUMENTO = {".pdf", ".xlsx", ".xls", ".csv", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".txt", ".html", ".htm"}
EXT_IGNORAR = {".ds_store", ".r", ".rhistory", ".rdata", ".ipynb", ".xlsm", ".py"}
_RE_CARPETA_IES = re.compile(r"^(\d{4})\s*-\s*(.+)$")
_RE_COD_ARCHIVO = re.compile(r"^(\d{4})(?=[_\s-])")
_RE_ANIO = re.compile(r"(?<!\d)(20[1-3]\d)(?!\d)")
_STOP = {
    "universidad", "universitaria", "universitario", "fundacion", "corporacion", "institucion",
    "instituto", "escuela", "colegio", "de", "del", "la", "las", "los", "el", "y", "en", "e",
    "educacion", "superior", "tecnologica", "tecnologico", "colombia", "nacional", "estudios",
    "precios", "derechos", "pecuniarios", "acuerdo", "resolucion", "pdf", "matricula", "valores",
}


def plano(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def slug(texto: str, maximo: int = 60) -> str:
    return plano(texto).replace(" ", "_")[:maximo].strip("_") or "documento"


def nombre_seguro(texto: str) -> str:
    t = unicodedata.normalize("NFC", str(texto))
    t = re.sub(r'[/\\:*?"<>|]+', " ", t)
    return re.sub(r"\s+", " ", t).strip()


def sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


@dataclass
class Institucion:
    codigo: str
    nombre: str
    tokens: frozenset


def maestro_instituciones(raices: list[Path], extra: dict[str, str] | None = None) -> dict[str, Institucion]:
    """Arma código → nombre a partir de carpetas 'CÓDIGO-NOMBRE' en las raíces."""
    nombres: dict[str, str] = {}
    for raiz in raices:
        for d, ds, _ in os.walk(raiz):
            for x in ds:
                m = _RE_CARPETA_IES.match(unicodedata.normalize("NFC", x))
                if m:
                    cod, nom = m.group(1), m.group(2).strip()
                    if len(nom) > len(nombres.get(cod, "")):  # el más completo
                        nombres[cod] = nom
    for cod, nom in (extra or {}).items():
        nombres.setdefault(str(cod), nom)
    return {
        c: Institucion(c, n, frozenset(t for t in plano(n).split() if t not in _STOP and len(t) > 2))
        for c, n in nombres.items()
    }


def institucion_por_nombre(texto: str, maestro: dict[str, Institucion]) -> str | None:
    """Busca la institución cuyos tokens distintivos aparecen todos en el texto.

    Devuelve None si no hay coincidencia o si es ambigua.
    """
    toks = set(plano(texto).split())
    candidatos = [(len(i.tokens), c) for c, i in maestro.items() if i.tokens and i.tokens <= toks]
    if not candidatos:
        # coincidencia parcial: todos los tokens menos uno, con al menos 2 tokens
        candidatos = [
            (len(i.tokens) - 1, c) for c, i in maestro.items()
            if len(i.tokens) >= 3 and len(i.tokens - toks) == 1
        ]
    if not candidatos:
        return None
    candidatos.sort(reverse=True)
    if len(candidatos) > 1 and candidatos[0][0] == candidatos[1][0]:
        return None
    return candidatos[0][1]


def clasificar(ruta: Path, raiz: Path, maestro: dict[str, Institucion], anio_raiz: int | None = None) -> dict:
    rel = ruta.relative_to(raiz)
    partes = [unicodedata.normalize("NFC", p) for p in rel.parts]
    nombre = partes[-1]
    cod, origen_cod = None, None
    for p in reversed(partes[:-1]):
        m = _RE_CARPETA_IES.match(p)
        if m:
            cod, origen_cod = m.group(1), "carpeta"
            break
    if not cod:
        m = _RE_COD_ARCHIVO.match(nombre)
        if m and m.group(1) in maestro:
            cod, origen_cod = m.group(1), "prefijo_archivo"
    if not cod:
        c = institucion_por_nombre(Path(nombre).stem, maestro)
        if c:
            cod, origen_cod = c, "nombre_archivo"

    anios = [int(a) for a in _RE_ANIO.findall(Path(nombre).stem)]
    if anios:
        anio, origen_anio = max(anios), "nombre_archivo"
    else:
        # solo la carpeta inmediata (p. ej. "PRECIOS 2026/"); las raíces tipo
        # "data_2023" agrupan documentos de varios años
        anios_carpeta = [int(a) for a in _RE_ANIO.findall(partes[-2])] if len(partes) > 1 else []
        if anios_carpeta:
            anio, origen_anio = anios_carpeta[-1], "carpeta"
        elif anio_raiz:
            anio, origen_anio = anio_raiz, "raiz"
        else:
            anio, origen_anio = None, None
    return {"CODIGO_INSTITUCION": cod, "ORIGEN_INSTITUCION": origen_cod, "ANIO": anio, "ORIGEN_ANIO": origen_anio}


def descripcion(nombre: str, cod: str | None, anio: int | None, maestro: dict[str, Institucion]) -> str:
    s = plano(Path(nombre).stem)
    if cod:
        s = re.sub(rf"^{cod}\b", "", s).strip()
        inst = maestro.get(cod)
        if inst:
            nom = plano(inst.nombre)
            s = s.replace(nom, " ").strip()
    if anio:
        s = re.sub(rf"(^|\s){anio}(\s|$)", " ", s).strip()
    return slug(s) if s else "documento"


def copiar(origen: Path, destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        r = subprocess.run(["cp", "-c", "-p", str(origen), str(destino)], capture_output=True)
        if r.returncode == 0:
            return
    shutil.copy2(origen, destino)


def organizar(
    fuentes: list[tuple[Path, int | None]],
    destino: Path,
    maestro: dict[str, Institucion],
    ejecutar: bool = True,
) -> pd.DataFrame:
    """Recorre `fuentes` (ruta, año por defecto de la raíz) en orden de prioridad.

    Ante archivos idénticos (mismo SHA-256) conserva el primero y marca los
    demás como DUPLICADO. Con ejecutar=False solo devuelve el inventario.
    """
    filas = []
    vistos: dict[str, str] = {}
    usados: set[str] = set()
    # archivos que ya estén en el destino (corridas previas)
    if destino.exists():
        for p in destino.rglob("*"):
            if p.is_file() and not p.name.startswith("."):
                vistos.setdefault(sha256(p), str(p))
                usados.add(str(p))

    for raiz, anio_raiz in fuentes:
        for p in sorted(raiz.rglob("*")):
            if not p.is_file():
                continue
            ext = p.suffix.lower()
            fila = {"RUTA_ORIGINAL": str(p), "ARCHIVO": unicodedata.normalize("NFC", p.name),
                    "EXTENSION": ext, "TAMANO_BYTES": p.stat().st_size}
            if p.name.startswith(".") or ext in EXT_IGNORAR or ext not in EXT_DOCUMENTO:
                fila["ESTADO"] = "EXCLUIDO"
                filas.append(fila)
                continue
            fila.update(clasificar(p, raiz, maestro, anio_raiz))
            cod, anio = fila["CODIGO_INSTITUCION"], fila["ANIO"]
            # Bases de datos sueltas (xlsx/csv fuera de carpetas de institución) no son documentos fuente
            if not cod and ext in {".xlsx", ".xls", ".csv", ".txt"}:
                fila["ESTADO"] = "EXCLUIDO_BASE"
                filas.append(fila)
                continue
            h = sha256(p)
            fila["SHA256"] = h
            fila["NOMBRE_INSTITUCION"] = maestro[cod].nombre if cod in maestro else ""
            if h in vistos:
                fila["ESTADO"] = "DUPLICADO"
                fila["DUPLICADO_DE"] = vistos[h]
                filas.append(fila)
                continue
            if cod:
                carpeta = nombre_seguro(f"{cod}-{maestro[cod].nombre}") if cod in maestro else cod
                sub = str(anio) if anio else "sin_anio"
                base = f"{cod}_{anio or 'sa'}_{descripcion(p.name, cod, anio, maestro)}"
                dest_dir = destino / carpeta / sub
                fila["ESTADO"] = "COPIADO" if anio else "COPIADO_SIN_ANIO"
            else:
                dest_dir = destino / "_SIN_CLASIFICAR"
                base = slug(p.stem, 80)
                fila["ESTADO"] = "SIN_CLASIFICAR"
            dest = dest_dir / f"{base}{ext}"
            k = 2
            while str(dest) in usados:
                dest = dest_dir / f"{base}_{k}{ext}"
                k += 1
            usados.add(str(dest))
            vistos[h] = str(dest)
            fila["RUTA_NUEVA"] = str(dest)
            if ejecutar:
                copiar(p, dest)
            filas.append(fila)

    cols = ["ESTADO", "CODIGO_INSTITUCION", "NOMBRE_INSTITUCION", "ANIO", "ORIGEN_INSTITUCION", "ORIGEN_ANIO",
            "ARCHIVO", "EXTENSION", "TAMANO_BYTES", "SHA256", "RUTA_NUEVA", "RUTA_ORIGINAL", "DUPLICADO_DE"]
    inv = pd.DataFrame(filas)
    for c in cols:
        if c not in inv.columns:
            inv[c] = None
    inv["ANIO"] = pd.to_numeric(inv["ANIO"], errors="coerce").astype("Int64")
    return inv[cols]


def resumen_por_institucion(inv: pd.DataFrame) -> pd.DataFrame:
    ok = inv[inv["ESTADO"].isin(["COPIADO", "COPIADO_SIN_ANIO"])]
    t = pd.crosstab([ok["CODIGO_INSTITUCION"], ok["NOMBRE_INSTITUCION"]], ok["ANIO"].fillna(0).astype(int))
    t.columns = ["sin_anio" if c == 0 else str(c) for c in t.columns]
    return t.reset_index()
