# It.19 — Histéresis rechazada; cierre de la familia incremental

Fecha: 2026-10-28. **Candidata rechazada: 0/5 semillas; se requieren 4/5.**
Control original 2/5; control DOWN sin umbral 1/5. Ninguna receta promovida.
[Preregistro](iteration-19-protocol.md) `203ac73`, implementación `c64c222`,
ambos anteriores a la evaluación. Probabilidades v1 de it.13 congeladas,
sin entrenamiento ni búsqueda de umbrales. Decisiones cada 15m y mínimo 4h.

## Resultado completo

Retornos compuestos de los cuatro folds; DD calculado sobre curva concatenada.
La candidata mantiene hasta DOWN argmax con p_down>=0,50, salvo cash forzado
por gate cerrado/ausente o predicción ausente. Entrada UP argmax y p_up>=0,50.

| Semilla | Original neto | DOWN neto | Histéresis neto | Histéresis stress | Histéresis DD | Consistencia |
|---|---:|---:|---:|---:|---:|---:|
| 42 | +20,19% | +29,51% | +37,68% | +35,73% | 18,07% | 2/4 |
| 123 | +19,70% | +21,49% | +53,32% | +51,19% | 21,83% | 2/4 |
| 456 | +29,90% | +42,58% | +27,95% | +26,02% | 19,43% | 2/4 |
| 789 | +14,58% | +25,84% | +46,12% | +44,26% | 17,58% | 2/4 |
| 2026 | +26,29% | +48,60% | +32,35% | +30,53% | 18,09% | 2/4 |

La candidata pasa rentabilidad y stress en 5/5; falla riesgo y consistencia
en 5/5. El control DOWN pasa riesgo, rentabilidad y stress en 5/5, pero solo
la semilla 456 pasa consistencia. No se selecciona retrospectivamente ese brazo.

| Métrica | Original | DOWN sin umbral | Histéresis |
|---|---:|---:|---:|
| Operaciones agregadas | 697 | 563 | 350 |
| Exposición media por fold/semilla | 3,23% | 8,53% | 20,08% |
| Compuesto bruto, rango de semillas | +31,27–50,02% | +36,70–65,88% | +38,05–64,44% |
| Compuesto neto, rango de semillas | +14,58–29,90% | +21,49–48,60% | +27,95–53,32% |
| DD concatenado, rango | 9,95–14,90% | 9,63–14,76% | 17,58–21,83% |
| Semillas que cumplen todo | 2/5 | 1/5 | 0/5 |

Las operaciones agregadas describen cinco ejecuciones, no una cartera conjunta.
La histéresis reduce rotación un 49,78% frente al original. Mejora bruto y neto
en 4/5 semillas frente al original; frente a DOWN mejora ambos en 3/5.
La diferencia bruto-neto del compuesto baja de 16,69–20,12 puntos porcentuales
a 9,66–11,12. Es impacto acumulado de costes sobre las curvas, no una suma de
comisiones. El ahorro existe, pero viene acompañado de mucha más exposición.

## Qué ocurre en cada semestre

Medias aritméticas entre las cinco semillas, sin elegir la mejor:

| Fold | Original neto | DOWN neto | Histéresis neto | Sharpe original / DOWN / histéresis | Histéresis DD medio |
|---|---:|---:|---:|---|---:|
| 2022 H1 | +1,92% | −0,48% | −8,05% | 0,56 / 0,00 / −1,12 | 14,80% |
| 2022 H2 | 0% | 0% | 0% | Cash en todos | 0% |
| 2023 H1 | +9,48% | +22,40% | +31,51% | 0,92 / 1,95 / 1,90 | 17,89% |
| 2023 H2 | +9,55% | +9,66% | +15,32% | 1,54 / 1,27 / 1,29 | 10,85% |

Consistencia por fold, expresada como semillas que pasan:

| Fold | Original | DOWN | Histéresis |
|---|---:|---:|---:|
| 2022 H1 | 5/5 | 5/5 | 5/5 |
| 2022 H2 | 5/5 cash | 5/5 cash | 5/5 cash |
| 2023 H1 | 0/5 | 0/5 | 0/5 |
| 2023 H2 | 2/5 | 1/5 | 0/5 |

Pasar consistencia frente a B&H en 2022 H1 no significa tener retorno positivo
ni cumplir el límite absoluto de riesgo. B&H perdió 56,89% en ese semestre.
En 2023 H1 B&H obtuvo +84,03% y Sharpe 2,73: la candidata captura más retorno,
pero sigue sin superar su Sharpe. En H2 también aumenta retorno medio sin
conseguir consistencia en ninguna semilla. H1 no es obligatorio por sí solo:
el criterio exige 3/4 semestres; la candidata se queda en 2/4 en todas.

## Conclusión y cierre formal

El diagnóstico de rotación identificaba una penalización real, pero quitar
salidas no conserva automáticamente la protección que proporcionaban. Esperar
a DOWN fuerte reduce costes y prolonga exposición; también aumenta drawdown y
empeora el balance Sharpe/DD. El gate SMA50/200 no basta para limitar el riesgo
de esta política, incluso manteniéndose idéntico al de it.13.

**Se cierra la familia incremental tras 19 iteraciones y cero promovidas.**
No probar otro umbral, holding, rejilla, semilla, feature o modelo para rescatar
esta receta. La excepción final autorizada por el usuario queda agotada.
No hay base para paper trading o trading real bajo `risk-return-v1`.
2024 y el test 2025–2026 permanecen cerrados.

Esto rechaza esta familia bajo el mandato vigente; no demuestra que sea
imposible superar B&H con cualquier estrategia. Una reapertura requeriría
una hipótesis económica completamente nueva, baseline sencillo, datos con
disponibilidad temporal defendible y protocolo de evaluación futura separado.
No se inicia esa investigación ni se modifica el mandato con este cierre.

## Evidencia y reproducción

- 60 controles reproducidos exactamente en targets/equity/fills/trades antes
  de ejecutar las alternativas; veredicto original idéntico al de it.13.
- 60 backtests DOWN, 60 candidata y ocho benchmarks: **188; cero modelos nuevos**.
- Posiciones de ambas alternativas contrastadas con un recorrido independiente.
- **71 tests relevantes pasados**, más lint y hooks del repositorio.
- Verificación posterior: **633 archivos**, 188 juegos de métricas recalculados
  y tres veredictos reproducidos. Sin backtests adicionales; comparte funciones
  métricas/evaluador, no constituye un segundo motor de ejecución independiente.
- Hashes de fuentes comprobados antes/después. Se conserva la limitación del
  manifiesto original parcial; la comparación exacta no prueba retrospectivamente
  la fecha de creación de todos sus archivos.
- El loader verificó hashes completos y deserializó únicamente datos <2024.

Artefactos: `data/experiments/iteration-19-20261028-hysteresis`.
Runner: `scripts/run_hysteresis_experiment.py`.
Verificador de ledgers/métricas: `scripts/verify_hysteresis_experiment.py`.
MLflow: experimento 23, run `3a491f3a5b9f4ca3923b3ae0ce83dcb3`.
Revisión archivada en `data/experiments/iteration-19-review-20261028`.
Los folds son desarrollo adaptativo muy reutilizado, no evidencia independiente.
