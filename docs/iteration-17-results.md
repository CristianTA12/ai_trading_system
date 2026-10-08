# Iteración 17 — Flujo agresor: rechazo, 1/5 frente a 2/5

Ejecución: 2026-10-08. Cierre: 2026-10-09.
Preregistro [iteration-17-protocol.md](iteration-17-protocol.md), commit
`a2ebd87`; implementación `7442023`, anteriores al entrenamiento.

**El paquete de dos features de flujo no supera risk-return-v1.** Pasa solo
la semilla 2026; el control v1 pasa con 456 y 2026. Se exigían cuatro de cinco.
El resultado sigue condicionado a representatividad histórica de los datos
y disponibilidad asumida dentro de 15 minutos tras el cierre del agregado.
No se acredita latencia histórica real. No hay promoción ni apertura del test.

## Comparación congelada

20 features v1 frente a v1 más desequilibrio agresor de 15m y 1h. Mismo target
4h ±1%, XGBoost, gate SMA50/200, holding mínimo 4h, entrada y salida it.13,
costes, filas y semillas. Sin SP500, funding ni salida DOWN de it.16.
Se entrenaron **40 modelos** y ejecutaron **128 backtests**.

Todos los train originales se conservan. Evaluación H1 pierde dos filas
por flujo ausente en ambos brazos; el resto permanece. No se eliminan
barras de ejecución. Los 20 controles reentrenados reproducen exactamente
las probabilidades antiguas sobre el subconjunto común; sus backtests se
recalculan desde cero, sin usar métricas it.13 como sustituto del control.

## Resultado por semilla

Retornos compuestos netos de cuatro folds; DD de curva concatenada.

| Semilla | Flujo base | Flujo stress | DD flujo | Consistencia | Flujo cumple | Control base | Control cumple |
|---|---:|---:|---:|:---:|:---:|---:|:---:|
| 42 | +14,89% | +11,72% | 13,05% | 2/4 | No | +20,19% | No |
| 123 | +12,91% | +9,97% | **16,35%** | 2/4 | No | +19,70% | No |
| 456 | +17,89% | +14,75% | 10,67% | 2/4 | No | +29,90% | Sí |
| 789 | +6,59% | +3,65% | 13,55% | 2/4 | No | +14,58% | No |
| 2026 | +33,82% | +30,60% | 9,95% | 3/4 | Sí | +26,29% | Sí |

El retorno compuesto empeora en 4/5 semillas. El retorno por fold mejora
en 7/20 comparaciones; ese recuento no implica que todas las restantes
empeoren, pues hay empates, incluido el semestre completamente en cash.

| Gate | Flujo | Control |
|---|:---:|:---:|
| Compuesto base positivo | 5/5 | 5/5 |
| Riesgo absoluto | 4/5 | 5/5 |
| Consistencia ≥3/4 | 1/5 | 2/5 |
| Compuesto stress positivo | 5/5 | 5/5 |
| Todos simultáneamente | **1/5** | **2/5** |

Ambos pasan consistencia en 2022 H1 y en 2022 H2 por excepción cash, en
todas las semillas. Ninguno pasa H1 2023. En H2 2023 flujo pasa con 2026;
control con 456 y 2026. La semilla 123 de flujo supera el DD permitido
tanto en H1 como en la concatenación (16,35%).

## H1 2023 y operaciones

B&H: +84,03%, Sharpe 2,7343. No se sustituye el benchmark por uno de menor
exposición para aprobar los resultados.

| Semilla | Retorno flujo H1 | Sharpe flujo | Sharpe control | DD flujo H1 |
|---|---:|---:|---:|---:|
| 42 | +6,15% | 0,6390 | 0,7962 | 13,05% |
| 123 | −4,05% | −0,2518 | 1,2641 | 16,35% |
| 456 | +2,02% | 0,2879 | 1,3690 | 10,67% |
| 789 | +2,98% | 0,3647 | 0,2249 | 11,15% |
| 2026 | +14,27% | 1,3526 | 0,9553 | 9,95% |

| Métrica descriptiva agregada | Flujo | Control |
|---|---:|---:|
| Operaciones | 669 | 697 |
| Exposición media | 3,09% | 3,23% |
| Beneficio bruto medio por operación | 23,17 pb | 25,64 pb |
| Beneficio neto base medio | 13,16 pb | 15,62 pb |
| Beneficio neto stress medio | 11,15 pb | 13,61 pb |

Beneficio por operación ponderado por número de operaciones; exposición
media simple de 20 pares semilla/fold. No representan una cartera conjunta
ni 20 muestras independientes de mercado. La reducción del beneficio bruto
indica que los costes no son la única diferencia desfavorable de esta prueba.

## Corrección del verificador

El primer replay llegó a la comprobación final de recuento y falló porque
arrastraba el total fijo de 150 predicciones sin outcome de it.15.
Las dos filas excluidas por flujo en H1 son 2023-03-24 12:00 y 12:15 UTC;
ambas carecen también de outcome completo. Quedan 13 por brazo/semilla,
**130 en total**. La disponibilidad del flujo, no el outcome, determina
la exclusión; las 13 restantes siguen produciendo señales y solo se omiten
del scoring. Las pruebas de emparejamiento cubren explícitamente este caso.

Se cambia únicamente el verificador para derivar el recuento desde labels
reconstruidos e índices elegibles, en lugar de copiar un número histórico.
No se reentrenan modelos, no se modifican predicciones, reglas, backtests
ni veredictos para resolver el fallo. El código de ejecución original queda
identificado en `protocol.json`; la corrección posterior se registra aparte.

Suite previa: **250 tests pasan, dos de integración omitidos**. Tras la
corrección pasan los seis tests de emparejamiento y features de flujo.
La verificación completa reconstruye features mediante sumas escalares,
recarga 40 modelos, reproduce probabilidades, coteja labels/gate, hace replay
independiente de política y recalcula métricas y decisiones de 128 backtests.
La parte de métricas/evaluación reutiliza las funciones del proyecto;
no es un segundo motor de ejecución independiente.

## Cierre

Cerrar este paquete 15m/1h. No escoger la semilla 2026 ni probar otros lags,
ventanas o umbrales en esta iteración. El dato recuperado es válido para
investigar, pero estas features no demuestran una mejora estable de la receta.
No generalizar el rechazo a toda microestructura: tamaños, secuencias y libro
de órdenes no han sido evaluados aquí. Tampoco inferir que ahora deban probarse
automáticamente; requieren una hipótesis económica nueva y revisión de coste.

El siguiente punto es otra decisión de arquitectura, no una it.18 automática.
Los folds de desarrollo ya han sido consultados repetidamente. Se mantiene
el mandato, el criterio y el test 2025–2026 cerrado; 2024 tampoco se ha leído
ni evaluado en este experimento.

Artifacts: `data/experiments/iteration-17-20261008-aggressor-flow/`.
[MLflow, experimento 19](http://localhost:5000/#/experiments/19/runs/dd5f10958b714f87b54424889db4164e).

```bash
python -m scripts.verify_aggressor_experiment data/experiments/iteration-17-20261008-aggressor-flow
```
