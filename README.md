# Derechos pecuniarios – Colombia (Benchlab)

Flujo para recolectar, extraer, normalizar y validar los precios de matrícula
(derechos pecuniarios) de las IES de Colombia y entregarlos en el formato
**T08** del aplicativo Benchlab.

```
fuentes/catalogo_fuentes.csv   una fila por institución y año: URL, acto administrativo, archivo, estado
config/periodos.csv            ID_PRD ↔ año ↔ FCH_INC_PRD (serial Excel)
dpcol/                         código (python -m dpcol ...)
  io.py                        lectura robusta (codificaciones, números colombianos), escritura T08 exacta
  unidades.py                  Semestral/Anual/Crédito/Total/... → equivalente semestral
  normalizar.py                PRC_HMGNZD + estado y regla por fila
  validar.py                   variación anual, cobertura, filas a revisar
  desde_ancho.py               base ancha de trabajo → formato largo
  catalogo.py                  catálogo de fuentes por institución
  organizar.py                 copia documentos a <CÓDIGO>-<IES>/<AÑO>/ con inventario y detección de duplicados
  validar_documentos.py        verifica acto, fecha, vigencia, páginas y firmas de los documentos de un año (con OCR)
  panorama.py                  cruza costos SNIES (consulta pública HECAA) con precios DP por programa e institución
data/raw|staging|salidas       datos locales (no se versionan)
docs/METODOLOGIA.md            reglas, estados y hallazgos
tests/                         pruebas (pytest)
```

## Uso

```bash
pip install -r requirements.txt
python -m pytest -q

# Normalizar una base T08 (o staging largo)
python -m dpcol normalizar --entrada T08_PRECIOS.csv --maestro PRECIOS_2026_AUDITORIA.xlsx --salida data/salidas/2026

# Normalizar desde la base ancha de trabajo
python -m dpcol normalizar --entrada PRECIOS_2026_AUDITORIA.xlsx --formato ancho --maestro PRECIOS_2026_AUDITORIA.xlsx --salida data/salidas/2026

# Crear/actualizar el catálogo de fuentes de 2027
python -m dpcol catalogo --base PRECIOS_2026_AUDITORIA.xlsx --anio 2027

# Validar los documentos de un año (OCR en caché)
python -m dpcol validar-documentos --documentos 01_DOCUMENTOS --anio 2026 --base 02_BASES/PRECIOS_2026_AUDITORIA.xlsx \
    --salida 03_SALIDAS/2026 --cache 03_SALIDAS/_texto_documentos

# Panorama SNIES vs. derechos pecuniarios
# (Programas.xlsx = botón "Descargar programas" en hecaa.mineducacion.gov.co/consultaspublicas/programas)
python -m dpcol panorama-snies --snies 02_BASES/SNIES/Programas.xlsx --base 02_BASES/PRECIOS_2026_AUDITORIA.xlsx \
    --auditoria 03_SALIDAS/2026/auditoria_completa.csv --validacion 03_SALIDAS/2026/validacion_instituciones_2026.csv \
    --anio 2026 --salida 03_SALIDAS/2026

# Organizar documentos fuente (copia; nunca mueve ni borra originales)
python -m dpcol organizar --fuente PDF --fuente "Derechos Pecuniarios/ULT. COMPILADO" \
    --fuente "Derechos Pecuniarios/DATA_2024::2024" --fuente "Derechos Pecuniarios/data_2023::2023" \
    --fuente "Derechos Pecuniarios/Archivos" --destino 01_DOCUMENTOS
```

`::AÑO` asigna ese año a los archivos que no lo tienen en el nombre ni en su carpeta
(queda marcado como `ORIGEN_ANIO=raiz`). El orden de `--fuente` define cuál copia se
conserva cuando hay archivos idénticos.

## Carpeta de trabajo (PRECIOS)

```
PRECIOS/
  Derechos Pecuniarios/            histórico descargado del SharePoint, sin modificar
  01_DOCUMENTOS/<CÓDIGO>-<IES>/<AÑO>/<CÓDIGO>_<AÑO>_<descripción>.pdf
  02_BASES/                        T08 vigente, base con histórico, auditoría; _versiones_2026/ con intermedios
  03_SALIDAS/<AÑO>/                resultados de `dpcol normalizar`
  inventario_documentos.csv        cada archivo: estado, institución, año, SHA-256, ruta nueva y original
  resumen_documentos_por_institucion.csv
```

Salidas de `normalizar`:

| Archivo | Contenido |
|---|---|
| `T08_PRECIOS.csv` | Formato exacto del aplicativo (UTF‑8 BOM, `;`, CRLF, precios enteros) |
| `auditoria_completa.csv` | T08 + unidad declarada/aplicada, factor, referencia SNIES, estado, regla, variación anual |
| `a_revisar.csv` | Filas de derechos pecuniarios con estado `REVISAR_*`, `ERROR_*`, `UNIDAD_*` o alerta de variación |
| `resumen_estados.csv` | Conteo de estados por año |
| `cobertura_por_ies.csv` | Programas con precio por IES, año y fuente |

## Principios

1. **El precio publicado por la IES no se reemplaza.** SNIES es solo referencia.
2. **Ninguna fila se descarta en silencio.** Si un CSV está mal formado, el proceso se detiene y dice en qué línea.
3. **Cada valor es trazable**: archivo de origen, unidad original, conversión aplicada y estado.
