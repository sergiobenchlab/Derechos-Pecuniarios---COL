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
