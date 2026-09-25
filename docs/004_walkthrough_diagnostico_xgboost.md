# Walkthrough 004 — Diagnóstico XGBoost: Umbral, Costes y Walk-Forward

**Fecha**: 2026-09-25
**Commit**: `ac0d98c` en `develop`
**Fase**: 4 (continuación) — diagnóstico sistemático del primer modelo
**Tests**: 65 pasando

---

## Lo que se ha comprobado

### 1. Barrido de umbral `p_up` — Validación 2024

| Umbral | Exposición | Operaciones | Duración media | Bruto | Neto |
|:------:|----------:|-----------:|---------------:|------:|-----:|
| 0,35 | 15,94% | 2.781 | 30,2 min | +134,17% | −85,49% |
| 0,40 | 10,96% | 2.093 | 27,6 min | +79,04% | −77,92% |
| 0,50 | 2,27% | 556 | 21,5 min | +28,58% | −26,26% |

**Hallazgo clave**: más exposición = más rotación = más costes = peor resultado. El modelo genera retorno bruto positivo en todos los umbrales, pero los costes lo destruyen. Con 0,50: ganancia media por operación = 4,73 pb, comisiones ida/vuelta ≈ 8 pb + slippage ≈ 2 pb → **neto −5,27 pb por operación**.

### 2. Balanced accuracy — Corrección

Balanced accuracy 46,94% supera la referencia aleatoria de 3 clases (**33,33%**, no 50%). El modelo tiene algo de poder predictivo real, pero:
- Recall DOWN: 29,90%
- Recall NEUTRAL: 77,10%
- Recall UP: 33,81%

El modelo es bueno prediciendo NEUTRAL pero débil distinguiendo UP de DOWN.

### 3. Walk-forward interno (2022–2023, 4 semestres)

| Semestre | Balanced Acc. | Neto 0,50 | Buy & Hold |
|:---------|-------------:|----------:|-----------:|
| 2022 H1 | 45,44% | −38,62% | −56,89% |
| 2022 H2 | 47,00% | −31,11% | −17,13% |
| 2023 H1 | 44,73% | −4,47% | +84,03% |
| 2023 H2 | 42,48% | +7,24% | +38,62% |

Un semestre positivo de cuatro no es una ventaja estable. Umbrales inferiores pierden en los cuatro.

### MLflow

- Diagnóstico: run `624662df`, experimento `spot-diagnostics-v1`
- Walk-forward: run `23965d05`, experimento `spot-diagnostics-v1`

---

## Diagnóstico resumido

```
El modelo TIENE algo de señal predictiva (bal. acc. 46,94% > 33,33%)
                    │
                    ▼
Pero la ganancia media por operación (+4,73 pb) es MENOR
que los costes por operación (~10 pb)
                    │
                    ▼
Causa principal: ROTACIÓN EXCESIVA
  - 77,88% de las operaciones duran 1 sola vela (15 min)
  - Mediana de duración = 15 min para los tres umbrales
  - Cada entrada/salida cuesta ~10 pb → se necesitan
    operaciones que capturen movimientos mucho mayores
                    │
                    ▼
Solución: HORIZONTE MÁS LARGO + MENOS ROTACIÓN
```

---

## Siguiente paso: qué cambiar y en qué orden

El usuario plantea priorizar horizonte, objetivo y reglas de salida. Esto es correcto. Hay tres ejes para atacar el problema de rotación:

### Eje 1 — Horizonte del target (impacto alto, cambio simple)

El target actual predice el retorno de la **siguiente vela de 15m**. Con costes de ~10 pb, necesitas predecir movimientos > 10 pb para ser rentable. Un retorno de 15m rara vez supera eso de forma aprovechable.

**Alternativas a probar:**
- `target_return_next_1h` (4 velas): movimientos más grandes, más fáciles de superar costes
- `target_return_next_4h` (16 velas): aún mayor, pero la señal predictiva puede degradarse
- Target binario: `UP_1h > +0.5%` vs `NOT_UP` (elimina NEUTRAL, fuerza decisión clara)

Cada cambio de horizonte implica recalcular labels — pero las features de `dataset.py` no cambian.

### Eje 2 — Política de mantenimiento / salida (impacto alto, reduce rotación directamente)

Actualmente: señal UP → entra; no UP → sale en la siguiente vela. Esto causa el 77,88% de operaciones de 1 vela.

**Alternativas:**
- **Holding mínimo**: si entras, mantén al menos N velas (ej: 4 = 1 hora) antes de poder salir
- **Salida por cambio de señal**: solo salir si el modelo predice DOWN, no si predice NEUTRAL
- **Trailing stop**: salir solo si el drawdown desde el máximo de la operación supera X%
- **Hysteresis**: entrar si `p_up > 0.5`, salir solo si `p_up < 0.3` (banda)

Estas son modificaciones al backtester y la lógica de señales, no al modelo.

### Eje 3 — Regresión en lugar de clasificación (impacto medio, cambia el modelo)

En vez de UP/NEUTRAL/DOWN, predecir directamente `expected_return`. Solo operar si `expected_return > costes + margen`. Esto alinea la señal con la pregunta real: ¿vale la pena operar después de fricciones?

### Orden recomendado

```
1. Holding mínimo + salir solo por DOWN (no por NEUTRAL)
   → Se puede probar inmediatamente con el modelo actual
   → No requiere reentrenar nada
   → Mide cuánto reduce rotación y mejora el neto

2. Target 1h binario (UP_1h > +0.5% vs NOT)
   → Requiere recalcular labels + reentrenar
   → Horizon más largo = edge por operación mayor

3. Walk-forward con (1) + (2) en los 4 semestres internos
   → Si mejora consistentemente → avanzar
   → Si no → probar regresión + features adicionales

4. Features adicionales (funding, OI, lags) SOLO si
   las mejoras de horizonte/política no bastan
```

### Lo que hay que medir en cada variante

Para que la comparación sea justa, registrar siempre:

| Métrica | Por qué importa |
|---------|----------------|
| Retorno neto | ¿Gana dinero después de costes? |
| Número de operaciones | ¿Se redujo la rotación? |
| Duración media de operación | ¿Mantiene más tiempo? |
| Edge neto por operación (pb) | ¿Supera los ~10 pb de costes? |
| Exposición | ¿Está suficiente tiempo en el mercado? |
| Max drawdown | ¿Controla el riesgo? |
| Consistencia walk-forward | ¿Funciona en varios semestres? |

---

## Observación importante

> El modelo tiene retorno bruto positivo (+28,58% con umbral 0,50) y balanced accuracy por encima de random. **No es un modelo inútil — es un modelo cuya señal es demasiado débil y de demasiado corto plazo para sobrevivir a los costes de ejecución.** Esto es un problema de diseño de estrategia, no de calidad de features o de modelo. El diagnóstico confirma que la dirección correcta es cambiar horizonte y reducir rotación, no añadir complejidad.

---

## Estado del repositorio

```
src/
├── backtesting/
│   ├── engine.py              ✅ Sin cambios
│   ├── benchmarks.py          ✅ Sin cambios
│   ├── metrics.py             ✅ Sin cambios
│   ├── dataset.py             ✅ Sin cambios
│   ├── experiment.py          ✅ Sin cambios
│   └── run_backtest.py        ✅ Sin cambios
├── models/xgboost/
│   └── classifier.py          ✅ Sin cambios
│   (nuevos scripts de diagnóstico)
├── ... (resto sin cambios)

tests/                         ✅ 65 tests (61 → 65)
docs/
├── 001_walkthrough_repositorio_base.md
├── 002_walkthrough_infra_datos_features.md
├── 003_walkthrough_backtesting_xgboost.md
├── xgboost-diagnostics.md     ✅ Nuevo
├── backtesting.md
├── backtesting-dataset.md
├── data-ingestion.md
└── wsl.md
```
