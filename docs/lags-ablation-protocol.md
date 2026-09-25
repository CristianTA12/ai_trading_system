# Ablación de lags: protocolo previo a resultados

Definición fijada el 26-09-2026 antes de entrenar o evaluar esta ablación.
Hipótesis: añadir contexto secuencial corto a v1 puede mejorar el resultado sin el
warmup largo del bloque v2. Se evalúa una única receta y una semilla fija.

## Variables y warmup

Se conservan exactamente las 20 columnas v1 y se añaden estas tres (23 en total):

| Nombre en código | Definición sobre features disponibles al cierre |
|---|---|
| `return_1_lag_1` | `return_1.shift(1)` |
| `return_1_lag_4` | `return_1.shift(4)` |
| `rsi_14_cutler_lag_1` | `rsi_14_cutler.shift(1)` |

Son los mismos lags definidos en v2; no se cambian sus fórmulas ni se añade drawdown,
ADX o eficiencia direccional. El lag máximo requiere **cuatro velas previas adicionales
al warmup de v1**, no una. Los lags se reinician tras cada hueco de las velas de 15m;
no se comprimen huecos usando simplemente la fila anterior del Parquet ni se rellenan
valores ausentes. Se medirá la pérdida real de cobertura antes de interpretar resultados.

## Comparación y condiciones fijas

- Candidato: 20 v1 + tres lags.
- Control: v1 reentrenado con idénticas filas de train, labels, pesos de clase y timestamps
  de predicción. Se usan todas las velas de ejecución del semestre, pasando a efectivo
  cuando no hay señal; no se borran de la curva fechas sin features.
- Referencias por semestre: Buy & Hold neto y efectivo (retorno cero, Sharpe indefinido).
- Target original 15m, DOWN/NEUTRAL/UP con umbrales ±0,25%.
- XGBoost sin cambios: 500 árboles, profundidad 6, learning rate 0,05,
  subsample/colsample 0,8, hist CPU, cuatro workers, semilla 42. Pesos inversos de clase
  calculados solo con train. Sin early stopping ni ajuste en el semestre evaluado.
- Entrada UP argmax y p_up >= 0,50. Holding mínimo 60 minutos y después salida cuando
  deja de cumplirse la entrada. Misma excepción por falta de señal y cierre del período.
- Capital inicial 10.000 USDT por semestre, taker 0,04% y slippage 0,01% por ejecución.
- Cuatro folds expansivos: 2022 H1/H2 y 2023 H1/H2. Purga de labels cuyo final alcanza
  el siguiente corte. Los lags pueden usar historia causal anterior al inicio del fold.
- No se evalúa 2024 ni test 2025–2026. El snapshot original permanece intacto.

## Métricas y criterio histórico

Comparación principal: Sharpe diario (365 días, libre de riesgo cero), máximo drawdown
y retorno neto por semestre frente al control emparejado. Referencias B&H y efectivo.
También se registran operaciones, exposición, costes, duración, media neta por operación,
clasificación y retornos brutos como diagnóstico, sin convertirlos después en nuevos gates.

Se conserva el criterio histórico **retorno neto estrictamente positivo en ≥3/4 semestres**.
Cero no cuenta. Se guardan los recuentos de ambos brazos y el resultado del criterio.
No se redefine retroactivamente el criterio a partir de Sharpe o drawdown, no se hace
búsqueda de lags/umbrales y no se promueve automáticamente ninguna estrategia.

Si el resultado mejora, será evidencia para esta receta concreta y este control, no una
prueba universal de causalidad ni de robustez estadística. La comparación contra v2,
que tenía otra cobertura de train, no aislará por sí sola el coste del warmup frente
al efecto del drawdown/tendencia: separar esos factores exigiría otro brazo/protocolo.

## Registro

Este documento se registra en Git antes de ejecutar modelos. Cada run guarda su copia,
hashes de datos/código, versiones, features de train, cobertura, ocho modelos,
predicciones, posiciones, métricas brutas/netas, operaciones y gráficos en MLflow.
La documentación de resultados será independiente; no se modifica este protocolo tras
observar resultados. El walkthrough 007 queda a cargo del usuario.
