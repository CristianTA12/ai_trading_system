# Iteración 16 — Persistencia hasta DOWN: rechazo, 2/5 semillas

Fecha: 2026-10-07. **Candidato 2/5, control it.15 1/5; requisito 4/5.**
No hay promoción. Mayor exposición y mayor retorno medio por operación no
resuelven la consistencia de 2023 H1; además reaparece un fallo de riesgo.

Preregistro [iteration-16-protocol.md](iteration-16-protocol.md), commit
`7d4d106`; implementación `f296f80`, ambos anteriores a la evaluación.
Se reutilizaron los 20 modelos SP500 de it.15: **cero modelos nuevos**.
Se conservaron todos los supuestos temporales de SP500, sin acreditar por
ello disponibilidad histórica real.

## Qué se aisló

Misma entrada UP argmax y p_up≥0,5, mismo gate SMA50/200, holding mínimo
240 min, señales, cinco semillas, cuatro folds, capital y costes.
Solo cambió la salida tras el mínimo: DOWN argmax en vez de pérdida de la
condición de entrada. NEUTRAL y UP con confianza insuficiente mantienen long.
Gate cerrado, señales ausentes y liquidación final conservan sus reglas.

Los 20 modelos reprodujeron sus probabilidades exactamente. Los 60 backtests
de control reprodujeron targets/equity/fills/trades de it.15 **antes** del
primer backtest candidato. Se completaron 128 backtests: 120 de brazos y
ocho benchmarks B&H/cash. No se consultaron BTC 2024 ni test 2025–2026.

## Veredicto por semilla

Retorno compuesto neto de cuatro folds; DD de la curva concatenada.

| Semilla | DOWN base | DOWN stress | DD DOWN | Consistencia | Cumple todo | Control base | Control cumple |
|---|---:|---:|---:|:---:|:---:|---:|:---:|
| 42 | +16,61% | +14,80% | 10,32% | 2/4 | No | +24,48% | No |
| 123 | +54,12% | +51,67% | 8,24% | 3/4 | Sí | +34,18% | Sí |
| 456 | +33,74% | +31,40% | **17,03%** | 3/4 | No | +29,99% | No |
| 789 | +43,76% | +41,33% | 8,42% | 3/4 | Sí | +34,69% | No |
| 2026 | +15,99% | +14,24% | 11,73% | 2/4 | No | +27,92% | No |

| Gate risk-return-v1 | DOWN | Control it.15 |
|---|:---:|:---:|
| Compuesto base positivo | 5/5 | 5/5 |
| DD≤15%, cada fold y concatenado | 4/5 | 5/5 |
| Consistencia≥3/4 folds | 3/5 | 1/5 |
| Compuesto stress positivo | 5/5 | 5/5 |
| Todos simultáneamente | **2/5** | **1/5** |

Los dos brazos pasan 2022 H1 en todas las semillas y 2022 H2 por excepción
cash. Ninguno pasa H1 2023. DOWN pasa H2 2023 con 123, 456 y 789; el control
solo con 123. El fallo de riesgo de 456 es **concatenado**: su DD H1 es
14,81%, pero eso no basta para cumplir el límite de toda la curva.

## Qué ocurrió en 2023 H1

B&H permanece en +84,03%, Sharpe 2,7343. Mayor exposición no garantiza mayor
Sharpe: DOWN mejora retorno y Sharpe de H1 solo en dos de las cinco semillas.

| Semilla | Retorno DOWN | Sharpe DOWN | Sharpe control | Exposición DOWN / control | Días con retorno distinto de cero DOWN / control |
|---|---:|---:|---:|---:|---:|
| 42 | +7,14% | 0,8298 | 1,1736 | 13,24% / 5,66% | 51 / 42 |
| 123 | +16,45% | 1,5408 | 1,4929 | 20,06% / 5,52% | 70 / 47 |
| 456 | +7,07% | 0,6912 | 1,5547 | 21,47% / 6,28% | 73 / 51 |
| 789 | +20,55% | 2,0118 | 1,8906 | 19,61% / 5,66% | 68 / 49 |
| 2026 | +4,94% | 0,5826 | 1,5149 | 19,19% / 5,66% | 65 / 46 |

Los días se cuentan con los mismos bins diarios UTC del evaluador; no son
días independientes de entrenamiento. La política sí cambia participación
y persistencia, pero eso no demuestra mejor selección de los intervalos.
En H2 mejora el retorno en cuatro semillas, incluida 123 (+23,99% frente
a +10,64%); en 2026 empeora ligeramente (+4,73% frente a +5,17%).

## Operaciones y duración

Agregado descriptivo de cinco semillas y cuatro folds. Medias de edge
ponderadas por operaciones; exposición media simple de 20 pares semilla/fold.
No constituyen 20 muestras de mercado independientes ni una cartera combinada.

| Métrica | DOWN | Control it.15 |
|---|---:|---:|
| Operaciones | 407 | 527 |
| Exposición media | 9,92% | 2,48% |
| Edge bruto medio por operación | 46,18 pb | 36,32 pb |
| Edge neto base medio | 36,14 pb | 26,29 pb |
| Edge neto stress medio | 34,13 pb | 24,28 pb |
| Duración media por operación | 1.280,71 min | 246,66 min |
| Mediana de duración | 465 min | 240 min |
| Duración máxima | 12.195 min | 585 min |

La duración media crece a 21,35 h y el máximo a 8,47 días: 4h era el mínimo,
no un máximo. Las 407 salidas candidatas se desglosan en 401 DOWN y seis por
predicción ausente. El control conserva 106 DOWN, 253 NEUTRAL, 167 UP con
confianza insuficiente y una predicción ausente.
No se añade ahora un máximo de holding: sería una variante elegida después
de ver los resultados, fuera de este protocolo.

## Verificación y cierre

Suite completa: **238 tests pasan, dos de integración omitidos**. Ocho tests
nuevos cubren persistencia, límites de holding, DOWN no acumulado, gate,
señal ausente, reentrada, empate argmax y liquidación final.
El verificador independiente reconstruye la posición barra a barra, entradas,
métricas y veredictos de 128 backtests; confirma modelos copiados idénticos,
predicciones emparejadas, control exacto e integridad de los artifacts it.15.
Las 150 predicciones sin outcome completo, sumadas sobre dos brazos y cinco
semillas, siguen presentes para la política y ausentes solo del scoring.

**Rechazar it.16 y cerrar esta prueba de persistencia.** No seleccionar 123/789,
no barrer umbrales DOWN, holding ni confianza y no redefinir el benchmark para
aprobar lo observado. It.13, it.15 e it.16 continúan siendo investigación
rechazada, con distintos compromisos entre retorno y riesgo.

El siguiente paso es la decisión de arquitectura prevista en Fase F:
mantener el mandato de alpha frente a B&H y diseñar una familia realmente
distinta, o definir expresamente otro objetivo de control de exposición con
protocolo y benchmark propios. La segunda opción no cambia el veredicto de
estas iteraciones. No se lanza una iteración 17 automática ni se abre el test.

## Artifacts

`data/experiments/iteration-16-20261007-down-exit/`, incluidos
`verification.json` y `policy_diagnostics.json` por fold/semilla.
[MLflow, experimento 15](http://localhost:5000/#/experiments/15/runs/7060155ca3574be4bc4b136f67b8fbf5).

```bash
python -m scripts.verify_down_exit_experiment data/experiments/iteration-16-20261007-down-exit
```
