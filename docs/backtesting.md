# Backtesting y primer XGBoost

El experimento usa el snapshot Parquet de la fase de features. Verifica los cuatro
SHA-256, las columnas y las fronteras temporales antes de entrenar. No consulta
TimescaleDB ni descarga datos durante el backtest. Funciona en Ubuntu nativo y WSL.

## Ejecutar

Desde la raíz del repositorio, con el entorno Python activado:

```bash
DATASET=data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z
make backtest DATA_ARGS="--dataset $DATASET"
make train-xgboost DATA_ARGS="--dataset $DATASET"
```

`train-xgboost` ya ejecuta los benchmarks; no necesitas ejecutar ambos para obtener
la comparación. El primero permite revisar solo benchmarks sin entrenar.
También existen `trading backtest` y `trading train-xgboost` con las mismas opciones.
Consulta `make train-xgboost DATA_ARGS="--help"`. Los parámetros de este experimento
se fijan en los dataclasses y se modifican por CLI; no lee `config/settings.yml`.

En WSL el venv actual se activa con
`source ~/.venvs/ai-trading-system/bin/activate`. En Ubuntu utiliza tu venv habitual.
Los procesos Python se ejecutan en el host, los servicios con `make up`.

## Contrato de ejecución

- BTC/USDT **spot, largo o efectivo**, una posición, sin crédito ni posiciones cortas.
- Capital inicial 10.000 USDT; cada entrada invierte el efectivo disponible incluyendo
  su comisión. `--position-fraction` permite invertir menos; no rebalancea mientras
  mantiene una posición. La comparación predeterminada usa el 100% en todas las estrategias.
- Eventos secuenciales OPEN/CLOSE. Una variable calculada con la vela que acaba en
  `t` puede ejecutar en la apertura de `t`. No usa el cierre futuro para decidir.
- Compras a `open * (1 + slippage)`, ventas a `open * (1 - slippage)`; última posición
  liquidada al último cierre, con los mismos costes. Slippage predeterminado 0,01%
  **por lado**, configurable con `--slippage` como fracción decimal.
- Comisiones solicitadas para la simulación: taker 0,04%, maker 0,02% **por ejecución**.
  No son una comprobación de la tarifa vigente de una cuenta real. Todas las operaciones
  usan taker por defecto. `--liquidity maker` solo cambia la comisión para sensibilidad:
  **no modela órdenes límite ni garantiza ejecución maker**.
- Objetivos 1/0 disponibles en la apertura. Si no existe señal se pasa a efectivo en
  la siguiente apertura observada. No interpola velas, no anticipa huecos; una posición
  abierta puede atravesarlos. La curva se valora solo con precios observados.
- Sin latencia, spread separado, impacto de mercado, tamaño mínimo, redondeo de lotes,
  fills parciales, stops ni conexión con el risk manager de ejecución real. Los resultados
  son una primera simulación de investigación, no una prueba de ejecución real.

## Benchmarks y métricas

Buy & Hold compra en la primera apertura y vende al cierre final. EMA mantiene largo
cuando EMA20 > EMA50; reutiliza las distancias causales del dataset, que reinician tras
huecos. Random sortea posición 0/1 equiprobable en cada apertura: semillas 42–71,
percentiles 5/50/95 y resultado individual de cada semilla. Su elevada rotación penaliza
mucho los costes; superarlo no demuestra una ventaja estadística. No iguala la rotación
ni la exposición del modelo. La curva random mostrada corresponde a la semilla 42.

Todas usan las mismas velas de validación, capital y costes. Sharpe y Sortino se calculan
con retornos diarios UTC, anualización `sqrt(365)` y tipo libre de riesgo cero. Sharpe
usa desviación muestral; Sortino, raíz del promedio de retornos negativos al cuadrado
(incluye ceros para los días no negativos). Se conservan días internos sin observaciones
con la última valoración, sin extender el período. El máximo drawdown es positivo y
se mide al cierre de las velas, incluyendo el capital inicial, no intravela.

Profit Factor y Win Rate usan operaciones cerradas **netas de ambos costes**; una
operación es el ciclo completo entrada/salida. Si no hay pérdidas el Profit Factor
es `null`; ratios sin denominador y win rate sin operaciones también son `null`.
Las comisiones y el slippage están separados para auditoría, pero ambos ya reducen
la equity: no deben restarse otra vez. Se incluyen exposición por número de velas,
turnover, equity final y número de operaciones.

## Modelo y separación temporal

Train: 2020–2023; validation: 2024. **Test 2025–2026 permanece reservado**.
El lector verifica los archivos completos pero solo entrega train/validation al
experimento. Comprueba que cada label termina antes del siguiente corte.

XGBoost clasifica el retorno bruto de apertura a cierre de la siguiente vela de 15m:
DOWN < −0,25%, UP > +0,25%, NEUTRAL incluye ambos límites. Usa las 20 variables del
snapshot; los precios futuros y labels no entran en los predictores. Pesos inversos
de clase calculados exclusivamente con train. 500 árboles, profundidad 6, learning rate
0,05, subsample/colsample 0,8, hist CPU con 4 workers y semilla 42. No se usa validation
para early stopping ni selección de hiperparámetros.

Solo entra/mantiene largo si la clase más probable es UP y `p_up >= 0,5`. El resto
sale/permanece en efectivo. Los pesos de clase hacen que estas probabilidades no estén
calibradas; el umbral es una primera regla fija. Una sucesión de señales UP mantiene
la posición más de una vela. Filas purgadas o sin predicción implican efectivo;
los benchmarks pueden operar en todo el período de validación.

## Resultados y MLflow

Cada ejecución crea un directorio nuevo en `data/experiments/` y rechaza sobrescribirlo.
Guarda recipe con hashes/versiones/parámetros, comparativa JSON/CSV, curva y drawdown PNG,
fills/trades/equity Parquet, distribución random y, si entrena, predicciones, matriz de
confusión, importancia de variables y `model.ubj`. El modelo nativo conserva el orden
de las variables; el recipe contiene su contrato. Los artifacts no se suben a Git.

MLflow registra métricas con prefijos `xgboost.*`, `buy_hold.*`, `ema_20_50.*`, `random.*`
y `classification.*`, parámetros y todos los artifacts. Accede a http://localhost:5000,
experimento `spot-baseline-v1`. Cada run contiene toda la comparación. Para trabajar
sin servidor usa `--no-mlflow`; si falla el registro remoto el comando falla y conserva
los resultados locales para diagnóstico.

Compose usa `--serve-artifacts --artifacts-destination /mlflow/artifacts` para subir
desde WSL/Ubuntu por HTTP. Tras actualizar, ejecuta `docker compose up -d --no-deps mlflow`.
Los experimentos antiguos que apuntan a `/mlflow/artifacts` mantienen su configuración;
crea otro nombre con `--experiment` si ese nombre ya existe con almacenamiento local.
El volumen nativo `/data/mlflow` y el override WSL se conservan. Desde PowerShell usa
`docker compose -f docker-compose.yml -f docker-compose.wsl.yml up -d --no-deps mlflow`.

## Interpretación y siguiente paso

La primera comparación es descriptiva sobre un único año de validación. Comparar contra
Buy & Hold, costes y drawdown antes de buscar más complejidad. Una mejora posterior
debe elegirse con validación walk-forward interna de train; repetir ajustes sobre 2024
convierte ese año en conjunto de desarrollo. Mantener el test reservado hasta fijar
el procedimiento y los costes. Esta fase no implementa todavía walk-forward ni trading real.

## Primera ejecución verificada (25-09-2026)

Snapshot `btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z`:
139.245 filas train, 35.135 predicciones de validación, 35.136 velas de ejecución.
Parámetros predeterminados, 10.000 USDT iniciales, 366 retornos diarios en 2024.

| Estrategia | Retorno neto | Sharpe | Máximo drawdown | Operaciones | Comisiones USDT |
|---|---:|---:|---:|---:|---:|
| Buy & Hold | +121,08% | 1,755 | 32,44% | 1 | 12,85 |
| EMA20/50 | +13,40% | 0,506 | 31,04% | 339 | 2.871,13 |
| Random, semilla 42 | −99,95% | −22,369 | 99,96% | 8.774 | 9.612,51 |
| XGBoost | −26,26% | −1,683 | 28,74% | 556 | 3.741,34 |

XGBoost: Profit Factor 0,763; Win Rate 52,34%; exposición 2,27% de las velas;
slippage acumulado 935,34 USDT. Accuracy 66,59%, balanced accuracy 46,94%, macro F1
45,21%; predecir siempre la clase mayoritaria de train logra 76,74% de accuracy en
validation. Los resultados no demuestran una señal rentable después de costes.

La mediana del retorno de las 30 semillas random es −99,98%: este baseline de alta
rotación ilustra el efecto de los costes y no sirve por sí solo para aprobar el modelo.

Run MLflow verificado: `44411da11bd44042800f409f39de1990`, experimento `spot-baseline-v1`.
Artifacts locales: `data/experiments/xgboost-20260925T171304191536Z/`.
Modelo, informe y equity descargados por HTTP desde MLflow y comparados por SHA-256
contra los archivos locales. El run anterior está marcado como sustituido por una
corrección en los límites diarios de Sharpe/Sortino; las operaciones y retornos coinciden.
