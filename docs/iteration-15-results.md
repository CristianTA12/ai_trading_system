# Iteración 15 — SP500: mejora económica, rechazo por consistencia

Fecha: 2026-10-07. **Candidato 1/5 semillas; control 2/5. Se exigen 4/5:
no hay promoción.** El retorno compuesto mejora y el drawdown concatenado
disminuye en las cinco semillas, pero 2023 H1 no supera el Sharpe de B&H
en ninguna y 2023 H2 solo pasa en una.

Preregistro [iteration-15-protocol.md](iteration-15-protocol.md), commit
`e02b46e`; implementación `fc84441`. Ambos anteriores al entrenamiento.
El usuario aceptó explícitamente la representatividad del snapshot actual
SP500 y la disponibilidad asumida desde su fecha UTC +48 h. Todo resultado
queda condicionado a esas hipótesis; la disponibilidad real no está probada.

## Experimento completado

20 modelos nuevos con 23 features: las 20 v1, retorno entre sesiones SP500,
distancia a SMA20 de sesiones y edad de observación. Se reutilizaron los
20 controles de it.13 con 20 features. Cinco semillas y cuatro folds;
target 4h ±100 pb, holding 240 min, gate SMA50/200 y costes sin cambios.

La cobertura macro fue 100% sobre todas las filas originales, sin recortes.
Verificación independiente de 450.645 filas train/evaluación, incluidas
las ventanas de train solapadas: no son 450.645 observaciones independientes.
El control reprodujo probabilidades y 60 backtests antes de entrenar candidatos;
los 128 backtests finales incluyen ambos brazos y B&H/cash. Ningún test reservado
ni observación BTC de 2024 se evaluó.

## Resultado por semilla

Retornos netos compuestos de los cuatro folds 2022–2023. DD de la curva
concatenada; posiciones y capital reiniciados por fold como en it.13.

| Semilla | SP500 base | SP500 stress | DD SP500 | Consistencia | Cumple todo | Control base | Control cumple |
|---|---:|---:|---:|:---:|:---:|---:|:---:|
| 42 | +24,48% | +21,89% | 6,84% | 2/4 | No | +20,19% | No |
| 123 | +34,18% | +31,44% | 8,81% | 3/4 | Sí | +19,70% | No |
| 456 | +29,99% | +27,11% | 9,61% | 2/4 | No | +29,90% | Sí |
| 789 | +34,69% | +31,87% | 6,78% | 2/4 | No | +14,58% | No |
| 2026 | +27,92% | +25,36% | 7,60% | 2/4 | No | +26,29% | Sí |

| Gate risk-return-v1 | SP500 | Control v1 |
|---|:---:|:---:|
| Compuesto base positivo | 5/5 | 5/5 |
| DD ≤15%, cada fold y concatenado | 5/5 | 5/5 |
| Consistencia ≥3/4 folds | 1/5 | 2/5 |
| Compuesto stress positivo | 5/5 | 5/5 |
| Todos simultáneamente | **1/5** | **2/5** |

Ambos pasan 2022 H1 en cinco semillas y 2022 H2 por excepción cash.
2023 H1 falla en todas. En 2023 H2 pasa SP500 con 123; el control pasa con
456 y 2026. No se selecciona 123 ni se combinan semillas entre folds.

## El bloqueo H1 mejora, pero no se resuelve

B&H 2023 H1: +84,03%, Sharpe 2,7343. SP500 mejora retorno y Sharpe frente
al control en las cinco semillas; aun así queda por debajo del benchmark.

| Semilla | Retorno SP500 | Sharpe SP500 | Sharpe control | DD SP500 | Trades SP500 / control |
|---|---:|---:|---:|---:|---:|
| 42 | +10,60% | 1,1736 | 0,7962 | 6,84% | 59 / 74 |
| 123 | +15,06% | 1,4929 | 1,2641 | 8,81% | 58 / 77 |
| 456 | +17,89% | 1,5547 | 1,3690 | 7,75% | 67 / 82 |
| 789 | +18,51% | 1,8906 | 0,2249 | 6,78% | 60 / 75 |
| 2026 | +13,84% | 1,5149 | 0,9553 | 7,60% | 60 / 81 |

La exposición H1 pasa aproximadamente de 6,93–7,68% con v1 a 5,52–6,28%
con SP500. La menor exposición no implica matemáticamente menor Sharpe;
estos resultados tampoco demuestran que incrementarla vaya a resolverlo.
En H2, el retorno SP500 queda por debajo del control en cuatro semillas.

## Comparación descriptiva de operaciones

Agregado de 20 pares semilla/fold; semillas sobre el mismo mercado, no muestras
independientes. Edge medio ponderado por operaciones; exposición media simple
de los 20 folds, no una cartera combinada.

| Métrica | SP500 | Control |
|---|---:|---:|
| Operaciones | 527 | 697 |
| Media bruta por operación | 36,32 pb | 25,64 pb |
| Media neta base por operación | 26,29 pb | 15,62 pb |
| Media neta stress por operación | 24,28 pb | 13,61 pb |
| Exposición media | 2,48% | 3,23% |

Un 24,39% menos de operaciones y mayor retorno por operación no bastan para
aprobar la receta. El rechazo tampoco prueba que el contexto SP500 carezca
de información: el paquete mejora varias métricas, pero incumple el objetivo
preregistrado. No se atribuye el efecto a una feature aislada ni se hacen
ablaciones retrospectivas dentro de esta iteración.

## Verificación y decisión

Suite completa: **224 tests pasan, 2 de integración omitidos**. Verificador
independiente: 128 backtests, 40 modelos recargables (20 nuevos y 20 copiados),
política reconstruida, clases y métricas recalculadas, hashes fuente intactos,
índices emparejados y veredictos coincidentes. Se preservan las 150 predicciones
sin outcome puntuable sumadas sobre ambos brazos y cinco semillas.

**Rechazar esta receta y cerrar it.15.** No abrir test, paper trading ni live.
Con it.14 e it.15 rechazadas, activar la revisión de arquitectura de Fase F,
caso 1, del [plan](implementation_plan_fase4b_ai_trading.md). La pregunta útil
es cómo definir y evaluar una estrategia de exposición/alpha coherente con
los resultados, no relajar a posteriori el criterio de esta receta. Cualquier
nueva intervención necesita hipótesis y protocolo propios; no se lanza aquí
otro umbral, lag, feature, semilla o algoritmo.

## Artifacts y reproducción

Carpeta: `data/experiments/iteration-15-20261007-sp500/`.
[MLflow, experimento 13](http://localhost:5000/#/experiments/13/runs/4cd9ec87cbba40e1b1c0304677c0979a).
Preparación: `data/experiments/iteration-15-preparation-20261006/`.

```bash
python -m scripts.verify_sp500_experiment data/experiments/iteration-15-20261007-sp500
# Solo para una reproducción autorizada, siempre en carpeta nueva:
python -m src.training.sp500_experiment --output data/experiments/<carpeta-nueva>
# La opción --preflight-only verifica el control sin entrenar candidatos.
```
