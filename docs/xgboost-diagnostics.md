# Diagnóstico de exposición, costes y walk-forward interno

## Qué se ha comprobado

Se mantiene el modelo v1 y la regla **UP debe ser argmax**. Se comparan exclusivamente
los suelos de probabilidad 0,35 / 0,40 / 0,50 solicitados, sin buscar hiperparámetros
ni cambiar el valor predeterminado. Los pesos de clase afectan a la calibración:
`p_up=0,50` no garantiza un 50% de frecuencia observada de la clase UP.

En cada umbral se simulan tres escenarios con las mismas señales: sin fricciones,
solo comisiones, comisiones más slippage. Cada escenario recalcula su capital y sus
tamaños de posición. Sus diferencias de retorno incluyen capitalización; no equivalen
a sumar las comisiones pagadas a la equity del escenario neto.

Se guardan duración media/mediana, proporción de operaciones de una vela, exposición,
ganancia media/mediana por operación, confusión, recall por clase y frecuencias/retornos
observados por intervalo de `p_up`, además de las métricas anteriores. La exposición
se mide por velas observadas; la duración usa tiempo transcurrido y puede incluir huecos.

Balanced accuracy promedia el recall de las tres clases. La referencia aleatoria es
**1/3**, no 1/2; estar por encima no demuestra rentabilidad, significación estadística
ni una buena separación específica entre UP y DOWN. La accuracy direccional adicional
se calcula sobre resultados verdaderos no neutrales y cuenta las abstenciones NEUTRAL
como errores, sin ocultarlas mediante un filtro de predicciones.

## Diagnóstico exploratorio de 2024

Se recarga el modelo original, se reproducen sus probabilidades y se comprueban contra
el Parquet guardado. Se exige el mismo snapshot (los cuatro hashes). No se reentrena.
2024 queda explícitamente como diagnóstico exploratorio: no se escoge un umbral usando
este informe ni se presenta como una nueva prueba independiente.

| Suelo `p_up` | Exposición | Operaciones | Duración media | Retorno bruto | Solo comisiones | Retorno neto |
|---|---:|---:|---:|---:|---:|---:|
| 0,35 | 15,94% | 2.781 | 30,2 min | +134,17% | −74,69% | −85,49% |
| 0,40 | 10,96% | 2.093 | 27,6 min | +79,04% | −66,44% | −77,92% |
| 0,50 | 2,27% | 556 | 21,5 min | +28,58% | −17,59% | −26,26% |

Con 0,50, el 77,88% de las operaciones dura una vela. La ganancia bruta media por
operación es 4,73 puntos básicos (0,0473%); las comisiones de ida y vuelta rondan 8 pb,
y el slippage añade otros 2 pb. El resultado neto medio es −5,27 pb por operación.
La mediana de duración es 15 minutos para los tres umbrales. Bajar el umbral aumenta
la exposición pero también la rotación, sin cubrir las fricciones.

El recall es DOWN 29,90%, NEUTRAL 77,10%, UP 33,81%; balanced accuracy 46,94%.
Esto exige separar la predicción de neutralidad de la dirección; no permite afirmar
que todas las features carecen de información. El objetivo de una vela y salidas
frecuentes tampoco equivalen a una estrategia diseñada para mantener todo un rally anual.

Run: `624662df2322458188e702d52c109531`, experimento MLflow `spot-diagnostics-v1`.
Directorio: `data/experiments/validation_diagnostic-20260925T172952306250Z/`.

## Cuatro folds internos, 2022–2023

Entrenamiento expansivo desde 2020 hasta el inicio de cada semestre, evaluación en
ese semestre. Se purgan labels cuyo final alcanza el corte de entrenamiento o el final
del semestre. Las señales no disponibles implican efectivo, igual que en el baseline.
Cada fold entrena un XGBoost independiente con los mismos 500 árboles y parámetros v1;
los tres umbrales comparten sus probabilidades. No hay early stopping en evaluación.

El lector verifica el snapshot completo, pero estos folds solo reciben filas de la
partición original **train**, nunca evalúan 2024 ni test 2025–2026. Se liquida al final
de cada semestre y se reinicia con 10.000 USDT: los retornos siguientes son por fold,
no una curva continua de dos años.

| Semestre | Train / evaluación | Balanced accuracy | Neto 0,35 | Neto 0,40 | Neto 0,50 | Buy & Hold neto |
|---|---:|---:|---:|---:|---:|---:|
| 2022 H1 | 69.221 / 17.375 | 45,44% | −81,21% | −73,43% | −38,62% | −56,89% |
| 2022 H2 | 86.597 / 17.663 | 47,00% | −53,91% | −43,66% | −31,11% | −17,13% |
| 2023 H1 | 104.261 / 17.319 | 44,73% | −38,65% | −20,30% | −4,47% | +84,03% |
| 2023 H2 | 121.581 / 17.663 | 42,48% | −25,11% | −18,77% | +7,24% | +38,62% |

No hay rentabilidad consistente con esta política. Un semestre positivo tampoco valida
una ventaja estable. El resultado no identifica por sí solo la causa como «las features»:
pueden influir objetivo, horizonte, calibración, modelo y política de mantenimiento/salida.

Run: `23965d0548d342faa18fc5c656fd9575`, experimento MLflow `spot-diagnostics-v1`.
Directorio: `data/experiments/train_internal_walk_forward-20260925T173013125662Z/`.

## Reproducir

```bash
DATASET=data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z
BASELINE=data/experiments/xgboost-20260925T171304191536Z
make diagnose-xgboost DATA_ARGS="--dataset $DATASET --baseline $BASELINE"
make walk-forward DATA_ARGS="--dataset $DATASET"
```

Cada comando crea un directorio nuevo y registra en MLflow el protocolo previo,
hashes, versiones, tablas, curvas, operaciones y predicciones; walk-forward guarda
también cada modelo. `--no-mlflow` permite ejecución local. `--output` fija un destino
nuevo. No existe selección automática de umbral ni promoción del modelo. El protocolo
walk-forward actual fija estos cuatro semestres y requiere train hasta enero de 2024.

## Siguiente experimento

Priorizar un objetivo/horizonte y una política de salida capaces de superar los costes:
comparar retorno esperado neto o clasificación con margen de costes, y una regla causal
de mantenimiento con menos rotación. Cambiar una familia de hipótesis cada vez y medirla
en los folds internos, incluyendo un baseline de efectivo. Las nuevas features (lags,
funding, OI, sentimiento) requieren disponibilidad histórica en el instante de decisión;
funding/OI de derivados no son costes ni datos nativos de esta operativa spot.

Los folds usados para elegir variantes pasan a ser desarrollo; no confundir mejoras
tras muchos intentos con evidencia independiente. Mantener reservado test y no saltar
a deep learning. Este cambio implementa el diagnóstico, no esas nuevas variantes.
