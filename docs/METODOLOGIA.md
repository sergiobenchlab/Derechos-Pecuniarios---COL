# Metodología de normalización

## Formato T08

| Columna | Descripción |
|---|---|
| `ID_IES` | ID de institución en el aplicativo (incluye seccionales) |
| `ID_PRGRM` | ID de programa en el aplicativo |
| `ID_PRD` | Período: 57=2024, 59=2025, 61=2026, 63=2027 (supuesto, confirmar) |
| `FCH_INC_PRD` | Fecha de inicio del período, serial de Excel (45292 = 2024‑01‑01) |
| `PRC` | Precio tal como lo publica la fuente |
| `FUENTE` | `DERECHOS PECUNIARIOS` (publicado por la IES) o `SNIES` |
| `PRC_HMGNZD` | Precio equivalente a un semestre (6 meses). Vacío en filas SNIES, como en el histórico |
| `PRD_PRC` | Unidad con la que se interpretó `PRC` |

## Conversión a equivalente semestral

| Unidad | Factor sobre `PRC` |
|---|---|
| Semestral | ×1 |
| Anual | ×0,5 |
| Cuatrimestral | ×1,5 |
| Trimestral | ×2 |
| Bimestral / Mensual | ×3 / ×6 |
| Crédito | × créditos ÷ períodos × (6 ÷ meses del período del programa) |
| Total / Cohorte | ÷ (períodos × meses del período ÷ 6) |
| Periodo | × 6 ÷ meses del período del programa |

Créditos, períodos y periodicidad salen del maestro de programas (base ancha).
Si la periodicidad es `Periodos`, `Sin definir` o vacía se asume semestral y se marca.

Verificado contra `T08_PRECIOS.csv` (2024‑2026): estas reglas reproducen la
homogeneización original en el 95 % de las filas (18.144 de 19.064).

## SNIES como referencia

El precio SNIES está expresado por período del programa; se lleva a semestre
con la periodicidad. `RATIO_SNIES = PRC_HMGNZD / SNIES_semestral`:

- `0,6 ≤ ratio ≤ 1,6` → **OK**.
- Fuera de ese rango se prueban las demás unidades; si alguna deja el ratio en
  `[0,8; 1,25]` se usa esa unidad → **UNIDAD_REINTERPRETADA** (p. ej. un "Total"
  que en realidad es semestral). El `PRC` no cambia.
- Programa anual con precio "Semestral" ≈ SNIES anual → **REVISAR_PERIODICIDAD**
  (puede estar mal la etiqueta o la periodicidad del maestro). No se cambia.
- Ninguna unidad lo explica → **REVISAR_RATIO_SNIES**. No se cambia.

## Estados

| Estado | Significado |
|---|---|
| `OK` | Unidad declarada coherente con SNIES |
| `SIN_REFERENCIA_SNIES` | No hay SNIES para comparar; se usa la unidad declarada |
| `UNIDAD_REINTERPRETADA` | Se cambió la unidad por evidencia de SNIES |
| `UNIDAD_ASUMIDA` | Unidad vacía o no reconocida; se asumió semestral |
| `REVISAR_PERIODICIDAD` | Ambigüedad anual/semestral |
| `REVISAR_RATIO_SNIES` | Diferencia con SNIES que ninguna unidad explica |
| `REVISAR_RANGO` | `PRC_HMGNZD` fuera de [100.000; 150.000.000] |
| `REVISAR_SIN_MAESTRO` | Precio por crédito/total sin créditos o períodos en el maestro |
| `ERROR_VALOR` | `PRC` > 500 millones (error de separadores) |
| `SIN_PRECIO` | Sin valor |

`ALERTA_VARIACION` marca variaciones anuales fuera de [‑5 %, +25 %] (mediana
histórica ≈ 5,5 %) y `PRC_CON_DECIMALES` marca precios con centavos.

## Hallazgos sobre la base 2026 (T08_PRECIOS.csv, mar‑2026)

- La homogeneización por **crédito** original era correcta (precio × créditos/períodos ≈ SNIES, mediana 1,00);
  el notebook de auditoría la descartó.
- La regla del notebook "si DP > 2,5 × SNIES, usar SNIES" reemplazaba datos de la IES por SNIES. Se eliminó.
- Cerca de la mitad de las filas marcadas **Total** son en realidad semestrales (ratio ≈ 1 con SNIES).
- **1.653 filas de 2026 (65 IES) tienen precios con decimales** y variación mediana de exactamente 5,5 %
  sobre 2025: muy probablemente son proyecciones, no precios publicados.
- `on_bad_lines='skip'` en los notebooks descartaba filas sin aviso; aquí está prohibido.

## Validación de documentos fuente (`dpcol validar-documentos`)

Para los precios del año N se espera un **acto administrativo** (acuerdo, resolución,
acta, circular, orden ejecutiva…) **expedido en noviembre o diciembre de N‑1**, que diga
que fija valores **para N**, con su tabla de valores, todas sus páginas y su cierre/firma.
Se revisan las carpetas `N-1/` y `N/` de cada institución, porque un acto expedido en
2025 para 2026 puede haber quedado en `2025/` por el año de su nombre.

Por documento se extrae el texto (OCR con Tesseract en páginas escaneadas, guardado en
caché) y se determina:

| Campo | Cómo |
|---|---|
| Acto | Tipo + identificador en el encabezado; se prefiere el que va seguido de "por el/la cual…" y se ignoran referencias ("Personería jurídica: Resolución…", "mediante Acuerdo…") |
| Fecha de expedición | "Dado en … a los 28 días del mes de noviembre de 2025"; si no, la fecha del encabezado |
| Vigencia | La del título ("…para el año 2026"); si no, en actos de sep‑dic se toma el año siguiente cuando se menciona |
| Completo | "Página X de N" vs. páginas del archivo, y cierre en la última página |
| Precios | Montos con separador de miles (con o sin `$`, también `1'200.000`) |
| Cobertura | % de programas activos de la institución cuyo nombre aparece en el texto |

Estados por documento: `OK`, `OTRO_ANIO_OK` (acto del año de su carpeta, p. ej. precios 2025
en `2025/`), `SOLO_INCREMENTO` (fija un % sin tabla), `FECHA_TEMPRANA` (ene‑oct de N‑1),
`FECHA_TARDIA` (ene‑mar de N), `SIN_CIERRE`, `SIN_FECHA`, `SIN_ACTO_IDENTIFICADO`
(tabla de tarifas sin acto), `FECHA_FUERA_DE_RANGO`, `INCOMPLETO_PAGINAS`,
`VIGENCIA_DISTINTA`, `SIN_PRECIOS` (p. ej. un reglamento), `NO_LEGIBLE`, `NO_PDF`.

Por institución: `COMPLETO` (al menos un acto `OK` para N), `REVISAR` (hay acto para N con
observaciones), `SOLO_TABULAR` (solo XLSX/CSV), `FALTA_ACTO`.

Caso de referencia — Universidad Simón Bolívar 2026: `PRECIOS 2026.pdf` (escaneado) es el
Acuerdo de Sala General No. 65 de 2025 (28‑nov‑2025), "para el año 2026", 9 de 9 páginas,
con cierre → `OK`. `SIMON_BOLIVAR_2026.pdf` es el Reglamento (Acuerdo 58 de 2019) → `SIN_PRECIOS`.
