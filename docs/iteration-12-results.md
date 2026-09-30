# Iteración 12 — Filtro diario de régimen: mejora de riesgo, receta rechazada

Informe: 2026-09-30 (hora local). Preregistro: `8778570`, fechado 2026-09-29.
Implementación: `b76c3c2`. **Resultado: 0/5 semillas cumplen risk-return-v1.**
El control también obtiene 0/5 y reproduce exactamente la iteración 11.
No se reevalúa 2024 ni el test 2025–2026. No se promueve ninguna receta.

La intervención elegida tras la revisión del arquitecto fue un filtro externo:
**permitir largos solo con SMA50 diaria > SMA200 diaria**. Las probabilidades,
los modelos v1 y los costes permanecen congelados. No se cambió simultáneamente
el horizonte, no se entrenaron modelos nuevos ni se optimizaron ventanas.

## Resultado principal

En estos folds el filtro mejora sustancialmente riesgo y retorno compuesto frente
al control. No es otro rechazo con las mismas características: **rentabilidad
base pasa de 1/5 a 4/5 semillas y riesgo pasa de 0/5 a 5/5**. Sin embargo,
ninguna alcanza los tres semestres de consistencia requeridos y solo tres
mantienen rentabilidad positiva bajo stress.

| Semilla | Control neto | Con filtro neto | Con filtro stress | DD concatenado filtro | Consistencia |
|---|---:|---:|---:|---:|:---:|
| 42 | −24,32% | +15,69% | +11,98% | 5,70% | 2/4 |
| 123 | −23,24% | +1,72% | −1,67% | 7,66% | 2/4 |
| 456 | +2,78% | +7,84% | +4,32% | 7,30% | 2/4 |
| 789 | −43,14% | −0,99% | −4,38% | 9,48% | 2/4 |
| 2026 | −23,21% | +17,06% | +13,42% | 5,52% | 2/4 |

| Condición, candidato con filtro | Semillas que cumplen |
|---|:---:|
| Retorno compuesto base >0 | 4/5 |
| DD <=15% por fold y concatenado | 5/5 |
| Consistencia >=3/4 folds | 0/5 |
| Retorno compuesto stress >0 | 3/5 |
| Todas conjuntamente | **0/5** |

En todas las semillas, 2022 H1 cumple la comparación de Sharpe/DD y 2022 H2
cumple la excepción de efectivo íntegro con B&H negativo. En ambos semestres
de 2023 el Sharpe queda por debajo de B&H, aunque el drawdown sea menor.
Consistencia no equivale a contar semestres con retorno positivo.

## Resultados por fold y efecto del gate

| Semilla | Filtro 2022 H1 | Filtro 2022 H2 | Filtro 2023 H1 | Filtro 2023 H2 |
|---|---:|---:|---:|---:|
| 42 | +0,7899% | 0% | +10,24% | +4,12% |
| 123 | +0,0041% | 0% | +3,61% | −1,84% |
| 456 | +1,4364% | 0% | +8,46% | −1,98% |
| 789 | +1,2869% | 0% | −3,52% | +1,32% |
| 2026 | +3,4614% | 0% | +10,18% | +2,69% |

Más decimales en 2022 H1 evitan confundir el pequeño retorno positivo de 123 con
cash. En ese semestre sí hay operaciones. En 2022 H2 no hay ninguna posición
ni fill en todo el semestre, comprobado en los registros de ejecución.

| Fold | Cobertura válida del filtro | Fracción de velas con gate abierto |
|---|---:|---:|
| 2022 H1 | 100% | 7,74% |
| 2022 H2 | 100% | 0% |
| 2023 H1 | 100% | 78,99% |
| 2023 H2 | 100% | 73,91% |

No se eligió cash por conocer el retorno semestral. El filtro estaba abierto al
inicio de 2022 y se cerró el **15-01-2022 a las 00:15 UTC**. Reabrió el
**08-02-2023 a las 00:15**, cerró el **13-09-2023 a las 00:15** y volvió a abrir
el **31-10-2023 a las 00:15**. Son consecuencias de la regla fija y sus datos
pasados, no fechas elegidas como parámetros.

Operaciones sumadas entre los cinco experimentos: **830 frente a 4.047**,
reducción del **79,49%**. Exposición media simple por fold/semilla: **0,9735%
frente a 4,9566%**. No son operaciones de una cartera conjunta de cinco semillas.
El candidato mejora el retorno compuesto del control en las cinco semillas,
pero recorta el retorno de 2023 H1 en todas ellas. La reducción de exposición
no demuestra por sí sola que seleccione mejor las oportunidades restantes.

## Referencia: solo filtro, sin XGBoost

Se incluyó una estrategia determinista long/flat al 100% según el gate, sin
holding mínimo, para distinguir el filtro de la selección del modelo.

| Fold | Retorno neto solo filtro | Máximo DD |
|---|---:|---:|
| 2022 H1 | −7,05% | 16,60% |
| 2022 H2 | 0% | 0% |
| 2023 H1 | +30,96% | 22,01% |
| 2023 H2 | +3,79% | 21,02% |

Compuesto base **+26,34%**, stress **+26,24%**, DD concatenado **24,21%**.
Solo cuatro operaciones en los cuatro folds. Captura más rentabilidad, pero
incumple el límite de riesgo del 15%; no es una alternativa aprobada. No se
replican cinco copias idénticas para aparentar estabilidad entre semillas.
XGBoost más filtro tiene mucha menos exposición que esta referencia, por lo que
la diferencia no identifica aisladamente información predictiva del modelo.

## Causalidad, reproducción y validación

- [Protocolo](iteration-12-protocol.md) y [244 hashes de inputs](iteration-12-inputs.json)
  registrados antes de calcular los nuevos resultados. Sin cambios post-hoc.
- Cierre diario: cierre de la vela completa de las 23:45 UTC. Si falta, NaN;
  sin sustituir por un cierre intradiario anterior. Medias sobre 50/200 días
  calendario completos en cierres, sin saltar días ausentes.
- `daily_available_at < decision_at`; primera aplicación a las 00:15 siguientes,
  caducidad 24h. Gate cerrado o señal ausente fuerza efectivo incluso dentro del
  holding. Una reapertura exige entrada nueva; no recupera una posición latente.
- Mismas predicciones y velas en ambos brazos; mismos costes taker 4 pb y slippage
  1 pb por ejecución, stress 2 pb. Cada escenario recalcula ejecución y capital.
- **20 modelos existentes recargados**, probabilidades reproducidas exactamente;
  **0 modelos entrenados**. Targets, equity, fills y trades del control reproducen
  los anteriores en todos los escenarios y su veredicto coincide exactamente.
- **140 backtests**: 120 para los dos brazos estocásticos y 20 de referencias.
- **156 tests pasan, 2 omitidos** por requerir DB; ocho casos nuevos comprueban
  warmup/frontera de medianoche, invariancia futura, ausencia/caducidad del cierre,
  igualdad y cruce bajista, salida prioritaria, reapertura, señales ausentes y
  exclusión de precios intradiarios del cálculo diario. Ruff y hooks pasan.
- El verificador reproduce independientemente la política barra a barra sin
  llamar al generador de targets, comprueba ausencia de posición con gate cerrado,
  recalcula métricas desde los registros y obtiene los mismos veredictos.

Artifacts: `data/experiments/iteration-12-20260929-regime-gate/`.
MLflow: experimento **8**, `spot-iteration-12-regime-gate`, ejecución
[`813c7e710e5648d6addfccdcdfb0104b`](http://localhost:5000/#/experiments/8/runs/813c7e710e5648d6addfccdcdfb0104b).

```bash
make experiment-regime-gate
python scripts/verify_regime_gate_experiment.py data/experiments/iteration-12-20260929-regime-gate
```

El runner fija inputs por preregistro y crea un directorio nuevo. Acepta `--output`,
`--tracking-uri` y `--no-mlflow`; no expone una búsqueda de ventanas o semillas.

## Matices de la revisión del arquitecto

La revisión acierta al proponer aislar régimen y horizonte y conservar criterio
y test reservado. Algunas conclusiones van más allá de los datos:

1. Los 0/5 de ambos brazos rechazan recetas; no demuestran que las features sean
   inocuas ni que la estrategia sea la única causa. Funding empeoró el retorno
   relativo en 13/20 comparaciones fold/semilla: «no introduce ruido» no está probado.
2. Long-only permite cash y puede capturar rebotes durante un período bajista;
   no es matemáticamente imposible ganar o limitar pérdidas en ese entorno.
3. 2023 H2 tuvo B&H de **+38,62%** y funding perdió con tres semillas; el patrón
   «funciona siempre en bull» no describe todos los resultados.
4. Una variable de 8h puede aportar contexto a decisiones de 15m; la diferencia
   de frecuencia no basta para descartarla. Su valor económico sigue sin probarse.
5. El histórico spot 2025–2026 ya existe descargado/exportado. Lo que se preserva
   es su **no evaluación**; no sería correcto afirmar que nunca fue descargado.
6. Ya existen tests que llaman directamente a `compute_metrics` en
   `tests/unit/test_backtesting.py`, aunque se podría ampliar la cobertura de
   fórmulas. No fue necesario refactorizar métricas ni el framework para esta prueba.
7. Un backtest con supuestos declarados no permite certificar ausencia absoluta
   de errores metodológicos. La disponibilidad histórica de funding continúa
   siendo un supuesto y los folds siguen acumulando decisiones exploratorias.

## Próxima decisión

El filtro resuelve el gate de riesgo **en estos folds**, pero no la consistencia
ni la estabilidad de rentabilidad bajo costes. No modificar SMA, semillas, costes
o criterio para convertir este resultado en aprobado; tampoco abrir test.

La siguiente línea propuesta es **una receta de horizonte 4h**, separada de esta
ejecución: hipótesis sobre movimientos capturables netos de costes, target/política
coherentes y protocolo nuevo. Fijar un solo horizonte y un control que permita
interpretar el cambio; no barrer 4h/8h/24h y elegir por el resultado. Mantener
costes taker hasta contar con un modelo de ejecución maker verificable.
Todavía no se fija ni ejecuta la iteración 13. Esta prueba no demuestra que un
horizonte mayor vaya a funcionar ni elimina el sesgo por reutilizar los folds.
