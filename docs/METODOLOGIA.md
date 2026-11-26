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
