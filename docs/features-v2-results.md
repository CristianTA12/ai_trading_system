# Features v2: resultado de la comparación preregistrada

Fecha local: 26-09-2026 (ejecución iniciada 25-09-2026 22:04 UTC).
El [protocolo](features-v2-protocol.md) quedó registrado en el commit `a99a2ec`
antes de entrenar. Se ejecutó una única definición de v2, sin cambiar ventanas,
features, umbrales o modelo tras ver resultados.

## Decisión

**No supera el criterio de al menos 3/4 semestres con retorno neto positivo.**
V2 logra 2/4; v1 con cobertura idéntica también logra 2/4. No se promueve v2.
V2 obtiene menor retorno neto que el control emparejado en los cuatro semestres.

| Semestre | V1 histórico, cobertura original | V1 reentrenado, filas emparejadas | V2, mismas filas |
|---|---:|---:|---:|
| 2022 H1 | −33,09% | −22,02% | −49,58% |
| 2022 H2 | −36,36% | −6,74% | −33,97% |
| 2023 H1 | +9,68% | +3,86% | +1,97% |
| 2023 H2 | +12,04% | +6,97% | +1,40% |
| Semestres positivos | 2/4 | 2/4 | **2/4** |

Todos utilizan el target original de 15m, tres clases, holding mínimo 1h y entrada
UP argmax con `p_up >= 0,50`. Las cifras incluyen comisiones y slippage. Cada semestre
comienza con 10.000 USDT. El control emparejado se reentrena en las mismas filas de
train y emite predicciones en los mismos timestamps que v2; por eso sus resultados
no coinciden con los del control histórico de cobertura completa.

Media neta por operación de v2: **−13,80 / −17,08 / +2,01 / +1,55 pb**, respectivamente.
Las cinco variables adicionales no han producido la mejora esperada con esta receta.
Esto no demuestra que el régimen sea irrelevante ni identifica por separado el efecto
de cada feature; el experimento evalúa el bloque completo, un modelo y una semilla fijos.

## Definición y cobertura efectiva

25 columnas: las 20 v1 conservadas exactamente, más drawdown al máximo de 2880 velas,
lags 1/4 del retorno, lag 1 del RSI y eficiencia direccional de 96 velas.
El drawdown requiere 30 días continuos y reinicia después de huecos. La mayor historia
necesaria reduce el total utilizable de train de **139.245 a 101.072 filas**.

| Fold | Train v1 original | Train de ambos brazos | Predicciones originales | Predicciones de ambos brazos |
|---|---:|---:|---:|---:|
| 2022 H1 | 69.221 | 36.011 | 17.375 | 15.243 |
| 2022 H2 | 86.597 | 51.254 | 17.663 | 17.663 |
| 2023 H1 | 104.261 | 68.918 | 17.319 | 14.489 |
| 2023 H2 | 121.581 | 83.408 | 17.663 | 17.663 |

En 2022 H1 la primera predicción elegible llega el 23 de enero a las 05:00 UTC, por
el warmup posterior a un hueco. Las velas de ejecución abarcan todo el semestre;
ambos modelos quedan en efectivo cuando no hay señal, sin eliminar esas fechas de
la curva de capital. Los huecos y ventanas explican parte de la diferencia respecto
al control histórico; el control emparejado permite separar ese cambio de cobertura
de la adición de columnas.

Los modelos se entrenan con ventanas expansivas anteriores a cada semestre y se purgan
labels que alcanzan la frontera. **2024 no se ha reevaluado y test 2025–2026 sigue reservado.**
No se ha introducido un filtro manual que impida operar por drawdown o tendencia:
son predictores, no reglas de exclusión del mercado.

## Reproducir y revisar

```bash
DATASET=data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z
make experiment-regime DATA_ARGS="--dataset $DATASET"
```

Opciones: `--output` (directorio nuevo), `--tracking-uri`, `--no-mlflow`.
El comando no modifica el snapshot original. Guarda protocolo, definición preregistrada,
features v2 de train, cobertura, ocho modelos, predicciones, posiciones, métricas,
clasificación, importancia de variables, operaciones y curvas brutas/netas.

- Directorio: `data/experiments/regime-v2-20260925T220422627478Z/`.
- MLflow: experimento `spot-regime-v2`, run `7324e79ef04a4424b5429da7408686d0`.
- Decisión guardada: `v2_passes_preregistered_gate=false`, `promoted=false`.
- 78 tests pasan, incluidos causalidad frente a cambios futuros/truncamiento, máximos
  móviles, lags, reinicio tras huecos y alineación de ambos brazos.

La decisión se mantiene aunque una lectura posterior de los diagnósticos sugiera otras
variantes. Cualquier ablación por familia, ventana alternativa o filtro explícito de
régimen será otro experimento con protocolo propio, sin reutilizar el criterio como
justificación para ajustar hasta obtener tres semestres positivos.
