# Políticas de salida y target binario de una hora

## Protocolo fijado antes de comparar resultados

Se mantienen las 20 features v1, el capital inicial, costes y parámetros del XGBoost.
No se buscan umbrales ni hiperparámetros. No se promueve automáticamente ninguna política.
El test 2025–2026 sigue reservado. Son dos experimentos secuenciales:

1. Reutilizar los modelos y probabilidades ya guardados de los cuatro semestres internos
   y del diagnóstico exploratorio de 2024. No hay entrenamiento en esta etapa. El código
   recarga cada modelo, reproduce sus probabilidades y las compara con el Parquet original.
2. Entrenar un binario UP/NOT-UP a una hora dentro de cada uno de los cuatro folds.
   Esta etapa no evalúa 2024. Mantiene train expansivo, sin early stopping ni búsqueda.

## Cuatro salidas para el modelo original

La entrada se mantiene en **UP como argmax y p_up >= 0,50**. No se compra porque
NEUTRAL deje de ser una salida, ni se rebalancea una posición abierta.

| Política | Mínimo de holding | Condición de salida |
|---|---:|---|
| baseline | 0 | Deja de cumplirse la condición de entrada |
| hold_60m | 60 minutos | Deja de cumplirse la condición de entrada |
| exit_down | 0 | DOWN es argmax, sin otro umbral de confianza |
| hold_60m_exit_down | 60 minutos | DOWN es argmax, sin otro umbral de confianza |

Con `exit_down`, NEUTRAL y UP con confianza insuficiente mantienen una posición existente.
El mínimo se mide desde la ejecución de entrada, en tiempo transcurrido, no en número
de filas. Durante ese mínimo se ignoran señales de salida; no se acumulan para ejecutarlas
después. A partir del minuto 60 se aplica la señal disponible en ese momento.

Dos excepciones explícitas: una señal ausente fuerza efectivo en la siguiente apertura
observada; la posición final se liquida al terminar el período. Ambas pueden producir
operaciones de menos de una hora. No se anticipan huecos ni se fabrican precios de salida.
Las decisiones se generan secuencialmente usando solo señales disponibles, nunca retornos
futuros. El motor de ejecución sigue aplicando capital, comisiones y slippage.

## Nuevo target binario

En cada timestamp de decisión `t`, el retorno objetivo es:

```text
return_1h = close(t + 45 minutos) / open(t) - 1
label_end = t + 60 minutos
UP = return_1h > 0,005
NOT-UP = return_1h <= 0,005
```

Se exigen cuatro velas consecutivas de 15m; no se cruzan huecos. El label se conoce
cuando cierra la cuarta vela. Features y decisiones siguen teniendo frecuencia de 15m;
el horizonte del objetivo es una hora. Los objetivos se solapan y no son observaciones
independientes para inferencia estadística.

Las etiquetas incompletas se excluyen de train y de las métricas de clasificación.
**No se suprime una predicción porque falte un precio futuro**: eso permitiría anticipar
huecos. La disponibilidad de señales en evaluación depende de las features disponibles,
no de la disponibilidad posterior del resultado a una hora. La purga por fronteras de
semestre sí elimina decisiones cuyo horizonte alcanza el corte, conocido de antemano.

Los cuatro folds usan 2022 H1/H2 y 2023 H1/H2. Se exige `label_end < corte` tanto al
entrenar como al evaluar; la purga pasa de 15 a 60 minutos. Pesos inversos de frecuencia
calculados exclusivamente con las clases de train. Se mantienen 500 árboles, profundidad
6, learning rate 0,05, subsample/colsample 0,8, hist CPU, cuatro workers y semilla 42.

Entrada binaria con `p_up >= 0,50`, salida con `p_up < 0,50`. Se comparan control inmediato
y holding mínimo de 60 minutos. NOT-UP incluye neutralidad y bajadas: **no equivale a DOWN**.
Por ello no se presenta una regla «solo DOWN» para el binario. Las probabilidades ponderadas
por clase siguen sin estar calibradas. No se optimiza su umbral con los resultados.

## Métricas, controles y artifacts

Cada política se ejecuta sin costes y con costes completos, recalculando su propio capital.
Se guardan operaciones, fills y equity de ambos escenarios. Se añaden Buy & Hold, EMA y
efectivo como controles netos. Las tablas incluyen retorno, drawdown, exposición, número
de operaciones, comisiones, slippage, duración y media/mediana de retorno por operación.
La media en pb es aritmética sobre operaciones cerradas; un valor positivo no garantiza
retorno compuesto positivo ni significación estadística.

Cada semestre comienza con 10.000 USDT y liquida al final: no se concatenan las curvas
como si hubiera una posición continua entre folds. Para el binario se registra también
prevalencia UP, matriz de confusión, balanced accuracy (azar: 50%), precision/recall UP,
ROC AUC, average precision y log loss, usando solo objetivos completos.

Los artifacts incluyen protocolo previo, hashes de inputs/código, versiones de librerías,
predicciones, posiciones objetivo, métricas y curvas. El binario guarda modelos y labels
de una hora en un directorio nuevo; no modifica los Parquet originales.

## Ejecutar en Ubuntu o WSL

```bash
DATASET=data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z
BASELINE=data/experiments/xgboost-20260925T171304191536Z
FOLDS=data/experiments/train_internal_walk_forward-20260925T173013125662Z
make experiment-exits DATA_ARGS="--dataset $DATASET --baseline $BASELINE --fold-baseline $FOLDS"
make experiment-hourly DATA_ARGS="--dataset $DATASET"
```

Ambos comandos aceptan `--output` (debe ser nuevo), `--tracking-uri` y `--no-mlflow`.
El experimento MLflow es `spot-exit-horizon-v1`. Los resultados se escriben en
`data/experiments/exits-*` y `data/experiments/hourly-*`.

## Resultados verificados, 25-09-2026

Retornos netos con los modelos originales de 15m, **sin reentrenar**:

| Período | Salida original | Holding 1h | Solo DOWN | Holding 1h + DOWN |
|---|---:|---:|---:|---:|
| 2022 H1 | −38,62% | −33,09% | −33,07% | −34,93% |
| 2022 H2 | −31,11% | −36,36% | −14,25% | −28,02% |
| 2023 H1 | −4,47% | +9,68% | −14,17% | −5,26% |
| 2023 H2 | +7,24% | +12,04% | −0,32% | +10,47% |
| 2024 exploratorio | −26,26% | +17,36% | +15,32% | +65,41% |

En 2024, holding 1h + DOWN reduce operaciones de 556 a 408, cambia la mediana de duración
de 15 a 75 minutos, eleva exposición del 2,27% al 12,72%, y lleva la media neta por
operación de −5,27 a +13,02 pb. Máximo drawdown 15,88%, frente a 28,74% del original.
Holding 1h solo: 448 operaciones, mediana 60 minutos, +4,10 pb netos por operación.
Son mejoras exploratorias; ninguna de las cuatro políticas obtiene retornos positivos
en todos los semestres internos. El holding de 1h gana en ambos semestres de 2023 y
pierde en ambos de 2022.

Resultados del **nuevo binario 1h**:

| Semestre | Train / predicciones | Salida inmediata neta | Holding 1h neto | Operaciones holding | Media neta por operación |
|---|---:|---:|---:|---:|---:|
| 2022 H1 | 69.173 / 17.372 | −67,79% | −54,93% | 1.041 | −6,85 pb |
| 2022 H2 | 86.549 / 17.660 | −58,55% | −42,69% | 808 | −6,37 pb |
| 2023 H1 | 104.213 / 17.316 | −21,02% | −1,32% | 551 | +0,11 pb |
| 2023 H2 | 121.530 / 17.660 | −34,99% | −20,28% | 372 | −5,78 pb |

En 2023 H1, tres predicciones no tienen objetivo futuro completo por un hueco; se
conservan sus señales y solo se excluyen esas tres filas del scoring de clasificación.
El resto de folds tiene objetivo completo para todas sus predicciones. La media aritmética
ligeramente positiva por operación en 2023 H1 convive con retorno compuesto negativo;
no sustituye la evaluación de la curva de capital.

Balanced accuracy binaria 60,73% / 61,62% / 59,88% / 57,91%, y ROC AUC
0,664 / 0,699 / 0,711 / 0,753. Hay capacidad de discriminación observada, pero no se
traduce en rentabilidad con esta política. Predecir `UP > 0,5%` no estima directamente
la ganancia esperada ni las pérdidas de la clase NOT-UP. Los pesos de clase y el umbral
fijo de 0,50 también forman parte de esta configuración; no se concluye que el horizonte
de 1h sea inviable en general ni que la causa esté demostrada en las features.

Conclusión: las dos palancas se han probado y no satisfacen el criterio de ventaja neta
consistente en los folds internos. No se promueve una política. La siguiente iteración
puede explorar features adicionales de tendencia/régimen, volatilidad y lags, manteniendo
estas variantes como controles y registrando cada hipótesis antes de medirla. Los datos
externos necesitarán timestamps de disponibilidad histórica; test sigue reservado.

Artifacts locales:

- `data/experiments/exits-20260925T214555492172Z/`
- `data/experiments/hourly-20260925T214718726464Z/`

MLflow, experimento `spot-exit-horizon-v1`:

- Salidas: `b36f2b0eed65495aa7667b71dcd494b6`.
- Binario 1h: `595252fe3ce7401db5ecf87db1f82471`.
