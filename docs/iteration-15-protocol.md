# Preregistro — Iteración 15: contexto SP500 bajo supuestos explícitos

Fecha: 2026-10-06. Registrar en Git antes de entrenamiento o backtests.
Estado: preparación autorizada; hipótesis temporales aceptadas expresamente
por el usuario después de la auditoría SP500. No hay resultados del candidato.

## Hipótesis y límite de interpretación

El retorno reciente y la tendencia del S&P 500 pueden aportar contexto externo
al clasificador BTC 4h que no contienen las 20 features v1. Se prueba un único
paquete de tres features, sin seleccionar subconjuntos ni barrer retardos.

Dos supuestos aceptados: (1) el snapshot actual representa los valores que
se habrían conocido históricamente; (2) cada observación es utilizable desde
su fecha a las 00:00 UTC más 48 horas. Ninguno está demostrado por FRED.
La API rechaza vintages SP500 porque la serie no existe en ALFRED.
Esto introduce una excepción explícita al requisito de evidencia real de E1
para investigación exploratoria, no declara causalidad histórica probada.
El resultado, positivo o negativo, queda condicionado a ambos supuestos.

## Fuentes y features congeladas

SP500: `data/external/macro-audit-20261006-retry/SP500.csv`, observaciones
2019-11-01–2023-12-31. SHA256:
`5921ef639046179df0d2c1029ee977d5d42fc3173c861a69e72273d059faf8eb`.
Se conserva el raw, incluidos nulos de días sin cierre. No nuevas descargas
ni actualización silenciosa del snapshot durante el experimento.

23 features: las 20 v1 sin cambios más:

- `sp500_return_1d = C_i/C_(i-1)-1`: dos observaciones no nulas distintas;
  significa retorno entre sesiones observadas, no necesariamente 24 horas.
- `sp500_sma_distance_20 = C_i/mean(C_(i-19),...,C_i)-1`: 20 cierres distintos,
  incluido el último; sin normalización aprendida.
- `sp500_data_age_hours`: horas desde la fecha del cierre etiquetada a las
  00:00 UTC hasta la decisión BTC. No equivale a horas desde el cierre real.

Calcular retorno y SMA antes del as-of, nunca sobre valores repetidos por barra.
Descartar nulos para construir eventos; no rellenarlos con retornos cero.
Join hacia atrás estricto `assumed_available_at < decision_at`; igualdad excluida.
Caducidad 168 h desde la fecha de observación UTC, inclusive. En fin de semana
se conserva el último evento elegible y aumenta su edad. Sin backfill desde
el futuro. Warmup mínimo de 20 eventos, cubierto con el histórico desde noviembre.
Features no disponibles/caducadas excluyen el timestamp en ambos brazos.

## Filas, control y política

Referencia íntegra: [it.13](iteration-13-protocol.md), no it.14 rechazada.
BTC snapshot y hashes iguales a it.13; solo train expansivo 2020–2023, folds
2022 H1/H2 y 2023 H1/H2; sin evaluar 2024 ni test 2025–2026.
Medir antes de entrenar cobertura macro >=95% de las filas originales de it.13
en train y evaluación de cada fold. Mantener también los controles de cobertura
v1 y gate de it.13. Si falla cualquier requisito, abortar sin cambiar el lag.

Candidato `sp500_regime`: 23 features. Control `v1_regime`: 20 features.
Ambos usan exactamente las mismas filas elegibles y semillas
42, 123, 456, 789, 2026. La elegibilidad macro no depende del outcome.
Ausencia de label futuro solo afecta train/scoring, nunca quita una señal
de evaluación que tenga features disponibles.

Si se conservan todas las filas originales, reutilizar los 20 modelos control
de it.13 tras verificar librerías, hashes y probabilidades idénticas al recargarlos.
Exigir reproducción exacta de equity/fills/trades del control en bruto/base/stress.
Si hay recorte, reentrenar los 20 controles sobre las filas comunes; no comparar
directamente contra métricas originales como si fueran un control emparejado.
En ambos casos entrenar 20 modelos candidatos; no escoger semillas.

Preparación previa al entrenamiento: 100% de cobertura macro en los ocho
conjuntos train/evaluación; todas las filas originales conservadas. Train:
68.981, 86.357, 104.021 y 121.326. Evaluación: 17.360, 17.648, 17.304 y 17.648,
en el orden de folds anterior. Edad máxima elegible 144 h. Por tanto se fija
la rama de reutilización del control; si el runner detecta cualquier recorte,
aborta en vez de cambiar silenciosamente al reentrenamiento.

Target `close(t+3h45m)/open(t)-1`, 16 barras completas; label_end=t+4h,
purga estricta, clases DOWN<-0,01 y UP>0,01, extremos NEUTRAL.
XGBoost: 500 árboles, depth 6, learning rate 0,05, subsample/colsample 0,8,
hist CPU, cuatro workers, mismos pesos N/(3*n_clase) en train. Sin tuning.
Entrada argmax UP y p_up>=0,5; gate diario SMA50>SMA200 sin cambios;
holding mínimo 240 min. Gate cerrado/señal ausente fuerza cash incluso antes
de 4h, sin cooldown, liquidación al final de fold. Capital 10.000 por fold,
long/flat 100%, sin apalancamiento. Taker 0,0004 por lado, slippage base
0,0001/stress 0,0002; bruto cero fricción. Benchmarks B&H/cash como it.13.

## Veredicto y entregables

`risk-return-v1.yaml` SHA256
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a` sin cambios.
En >=4/5 semillas: compuesto base>0, DD<=15% por fold y concatenado,
>=3/4 folds con Sharpe>B&H y DD<=B&H, excepción cash vigente y stress compuesto>0.
Evaluar ambos brazos; solo el candidato puede superar esta prueba condicional.
H1 2023 no es un criterio separado. No cambiar umbral de entrada, medias,
features, costes, benchmark ni criterio después de ver resultados.

Guardar modelos, predicciones, features macro/edades/eligibilidad, índices,
targets, equity/fills/trades, métricas, cobertura, versiones, hashes, protocolo
y commits en carpeta nueva y MLflow. Verificador independiente de alineación
temporal y fórmulas; validación del control y del evaluador antes de promoción.

Si falla, registrar rechazo sin probar otra combinación en esta iteración.
Si pasa, resultado exploratorio condicionado: no sustituye evidencia temporal
real ni permite abrir automáticamente el test o desplegar. Los folds ya fueron
usados repetidamente y no constituyen un holdout independiente.
