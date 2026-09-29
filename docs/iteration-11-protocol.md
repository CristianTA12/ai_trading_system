# Protocolo preregistrado — Iteración 11: funding liquidado

Fecha: 2026-09-29. Registrar este documento y el criterio vigente en Git antes
de entrenar. Esta receta incorpora la decisión propuesta por el usuario:
aceptar el desfase de 15 minutos como supuesto explícito para investigación.
No acredita disponibilidad histórica ni ausencia inequívoca de leakage.

## Hipótesis y alcance

El funding aporta contexto de posicionamiento de derivados que las 20 features
técnicas v1 no contienen y podría reducir operaciones en entornos desfavorables.
Se evalúa un único bloque de tres variables, sin selección posterior ni ablaciones
dentro de esta iteración. El activo negociado sigue siendo BTC/USDT spot; funding
es información externa y no un flujo de caja cobrado o pagado por la estrategia.

## Datos y disponibilidad temporal

- Dataset v1: `data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z`.
  SHA-256 de features: `97b7422532ada297de2f0e83665adeda3594a31b932a155b3028b7c00cd995a8`.
  Comprobar también los hashes de bars, labels y splits contra su metadata.
- Funding: snapshot auditado en `data/audits/derivatives-20260929/funding/`,
  48 ZIP mensuales, 4.383 eventos de 2020–2023. Verificar sus checksums y reconstruir
  el snapshot antes de usarlo. No descargar datos adicionales.
- SHA-256 `observations.parquet`:
  `ed8b4a2dcff5db65c3ecefaa98a5d1c1bd8381f04d0e91666c059712d409b47a`.
- SHA-256 `manifest.csv`:
  `f8c804975a854c46f9f2b412ba1ae4e6acf645a671931a8af1eb7d1c573c99e5`.
- Conservar UTC y milisegundos originales. Asumir
  `assumed_available_at = event_time + 15min`, con elegibilidad estricta
  `assumed_available_at < decision_at`. Join as-of hacia atrás.
- Caducar si `decision_at - assumed_available_at > 8h`; igualdad válida.
  Edad total máxima: 8h15m. Sin backfill ni relleno indefinido.
- Un evento a las 08:00 se incorpora a las 08:30, nunca a las 08:15.
- Los hashes prueban integridad del snapshot, no cuándo se publicó cada valor
  ni si fue revisado. Los resultados quedan condicionados a estos supuestos.
  La captura futura guardará evento, recepción, fuente, versión y checksum;
  validará el comportamiento futuro, sin demostrar la disponibilidad de 2020–2023.

## Features fijas: 20 v1 + 3 funding = 23

| Feature | Definición sobre eventos distintos, antes del join |
|---|---|
| `funding_last_settled` | Última tasa liquidada elegible, en unidades originales |
| `funding_delta_event` | Tasa del último evento menos la del anterior |
| `funding_mean_3_events` | Media aritmética de las tres últimas liquidaciones |

Sin normalización, clipping ni ajuste por outcomes. Los eventos deben ser únicos,
ordenados, finitos y de intervalo 8h. Un hueco en los slots nominales reinicia
delta/media; las fechas originales se conservan para elegibilidad. Datos inválidos
o duplicados provocan error, no se elige una versión arbitraria.

Warmup: tres eventos; abarcan 16h entre primero y tercero, con disponibilidad
posterior al tercero. No equivale automáticamente a perder 24h de barras.
La medición previa al entrenamiento elimina 16 filas v1 (4h), desde la primera
fila v1 a las 12:30 hasta la primera completa a las 16:30 del 2020-01-01 UTC.

| Fold | Train original | Train emparejado | Eval original = emparejada |
|---|---:|---:|---:|
| 2022 H1 | 69.221 | 69.205 | 17.375 |
| 2022 H2 | 86.597 | 86.581 | 17.663 |
| 2023 H1 | 104.261 | 104.245 | 17.319 |
| 2023 H2 | 121.581 | 121.565 | 17.663 |

Requisito: cobertura >=95% tanto en train como eval de cada fold. Usar complete
cases idénticos en ambos brazos; conservar todas las velas de ejecución.
Si falta señal, pasar a efectivo en la siguiente apertura observada, incluso
durante el holding. No borrar fechas de equity por falta de features.

## Modelo, target y política

Clasificador XGBoost existente: `multi:softprob`, tres clases,
`n_estimators=500`, `max_depth=6`, `learning_rate=0.05`, `subsample=0.8`,
`colsample_bytree=0.8`, `tree_method=hist`, `device=cpu`, `n_jobs=4`.
Pesos de clase calculados exclusivamente con cada train: N/(3*N_clase).
Sin early stopping, búsqueda de hiperparámetros ni selección de semillas.

Target existente: retorno `close[t]/open[t]-1` de los siguientes 15 minutos.
DOWN < -0,0025; UP > 0,0025; extremos e intervalo interior son NEUTRAL.
Entrada: UP argmax y `p_up >= 0,50`. Holding mínimo 60 minutos desde entrada.
Tras el holding, salir cuando deja de cumplirse la condición de entrada.
Liquidar al final del fold. Sin posiciones entre folds. Capital inicial por
fold: 10.000 USDT, una posición long/flat al 100%, sin apalancamiento.

Control `v1_matched`: mismo clasificador y política con las 20 features v1,
mismas filas de train/eval, labels, pesos de clase, semillas y velas.
Referencias adicionales: Buy & Hold y efectivo con costes base.

## Evaluación y decisión

- Folds: 2022 H1/H2 y 2023 H1/H2, train expansivo desde 2020.
- Purga estricta `timestamp + 15min < frontera` en train y eval.
- Semillas secuenciales: **42, 123, 456, 789, 2026**, sin seleccionar la mejor.
- Costes por ejecución: taker 0,0004; slippage base 0,0001 y stress 0,0002.
- Stress reutiliza predicciones y reglas, recalculando ejecuciones/equity.
  Escenario bruto (fee/slippage cero) solo diagnóstico.
- Criterio inalterado: [risk-return-v1.yaml](risk-return-v1.yaml), SHA-256
  `12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
- Retorno compuesto >0, DD por fold y concatenado <=15%, consistencia en >=3/4
  folds (Sharpe > B&H y DD <= B&H, con excepción cash definida en el criterio),
  retorno compuesto stress >0; todas las reglas en >=4/5 semillas.
- Evaluar automáticamente ambos brazos. Gate histórico >=3/4 retornos positivos
  solo como referencia. La mejora frente al control se reporta por semilla/fold,
  sin convertir una mejora relativa en aprobación ni inferir significación.
- **2024 no se reevalúa; test 2025–2026 reservado.** El loader de train filtra
  observaciones anteriores a 2024; el hash completo solo verifica integridad.

Si funding falla, registrar rechazo con todas las semillas. Si supera, congelar
receta y diseñar protocolo final antes de abrir test. No abrirlo automáticamente.
El experimento sigue siendo exploratorio tras múltiples decisiones en estos folds;
ni cinco semillas ni el retraso supuesto eliminan ese sesgo.

## Trazabilidad y artifacts

Guardar protocolo/criterio y hashes, commit previo al entrenamiento, hashes de
código/datasets, versiones de dependencias, cobertura, features y tiempos del join,
predicciones con retornos reales, modelos UBJ y verificación de recarga, importancias,
targets, fills/trades/equity por fold/semilla/escenario, curvas concatenadas,
diagnósticos de clasificación y ejecución, comparación CSV/JSON y ambos veredictos.
Registrar el conjunto en MLflow local. No sobrescribir ejecuciones previas.
Cambiar receta exige nuevo preregistro antes de ver nuevos resultados.
