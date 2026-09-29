# Iteración 11 — Funding liquidado: resultado y revisión

Fecha: 2026-09-29. **Receta rechazada: 0/5 semillas cumplen risk-return-v1.**
El control v1 emparejado también obtiene 0/5. No se promueve ninguna variante,
no se reevalúa 2024 y el test 2025–2026 permanece reservado.

El [protocolo](iteration-11-protocol.md) quedó registrado en `aa8f480` y la
implementación en `9ccd153`, ambos antes de entrenar. Se ejecutó una única receta:
20 features v1 + las tres features de funding, clasificador XGBoost sin cambios,
holding mínimo 1h, cuatro folds y las cinco semillas fijadas. No hubo ajustes
posteriores ni selección de la mejor semilla.

## Resultados por semilla

Retornos compuestos de los cuatro semestres; drawdown sobre equity concatenada.
Todos los porcentajes de la tabla están redondeados solo para presentación.

| Semilla | Funding neto | Funding stress | DD funding | Consistencia | Control neto |
|---|---:|---:|---:|:---:|---:|
| 42 | −23,49% | −33,40% | 33,87% | 1/4 | −24,32% |
| 123 | −21,35% | −31,76% | 33,92% | 1/4 | −23,24% |
| 456 | −41,78% | −49,26% | 47,85% | 1/4 | +2,78% |
| 789 | −26,06% | −35,68% | 37,70% | 1/4 | −43,14% |
| 2026 | −34,02% | −42,62% | 38,67% | 1/4 | −23,21% |

Funding falla las cuatro condiciones por semilla: retorno compuesto positivo,
drawdown máximo del 15%, consistencia en tres semestres y rentabilidad con stress.
El retorno positivo del control con semilla 456 no basta para aprobar el criterio
conjunto ni autoriza seleccionar esa semilla.

| Semilla | Funding 2022 H1 | Funding 2022 H2 | Funding 2023 H1 | Funding 2023 H2 |
|---|---:|---:|---:|---:|
| 42 | −5,16% | −26,79% | +8,45% | +1,61% |
| 123 | −13,09% | −18,28% | +7,16% | +3,33% |
| 456 | −16,08% | −32,05% | +6,44% | −4,09% |
| 789 | −6,00% | −26,98% | +7,93% | −0,19% |
| 2026 | −8,13% | −31,48% | +5,17% | −0,35% |

## Qué cambia frente al control

- Funding mejora el retorno neto del control en **7/20** comparaciones
  fold/semilla y el compuesto en **3/5** semillas. La mejora relativa no satisface
  el criterio absoluto y es irregular.
- Operaciones agregadas en las cinco semillas: **3.486 frente a 4.047**, reducción
  del **13,86%**. Son ejecuciones de cinco experimentos, no una cartera conjunta.
- Exposición media simple entre folds/semillas: **4,31% frente a 4,96%**.
  Operar menos no ha evitado las pérdidas de 2022.
- Funding pierde en ambos semestres de 2022 con todas las semillas; gana en
  2023 H1 con todas y en 2023 H2 solo con dos. El gate histórico queda en 2/4
  positivos para 42 y 123, y 1/4 para 456, 789 y 2026.
- Las fricciones siguen siendo relevantes, pero no son la única limitación:
  `comparison.csv` también contiene semestres negativos en el escenario bruto.

No se ha demostrado que funding carezca de toda información predictiva. Se rechaza
este bloque de features con esta receta, horizonte, política y simulación. Las
semillas no son cinco muestras independientes de mercado. Los folds ya han guiado
múltiples decisiones, por lo que estos resultados siguen siendo exploratorios.

## Cobertura, causalidad y supuesto temporal

Se verificaron los 48 ZIP contra checksum y manifiesto, se reconstruyó funding y
se comprobó su igualdad con el Parquet auditado. No se descargaron datos nuevos.

Se calculan nivel, delta y media sobre liquidaciones distintas antes del as-of
join. Se conserva la precisión original; `event_time + 15min < decision_at` es
estricto y la edad total máxima es 8h15m. Los huecos reinician la historia de
delta/media. La nueva matriz tiene **139.229 filas y 23 features**.

| Fold | Train v1 original | Train de ambos brazos | Cobertura train | Predicciones de ambos |
|---|---:|---:|---:|---:|
| 2022 H1 | 69.221 | 69.205 | 99,9769% | 17.375 |
| 2022 H2 | 86.597 | 86.581 | 99,9815% | 17.663 |
| 2023 H1 | 104.261 | 104.245 | 99,9847% | 17.319 |
| 2023 H2 | 121.581 | 121.565 | 99,9868% | 17.663 |

Se pierden 16 filas iniciales por train, ninguna predicción original de los folds.
Se conservan todas las velas de ejecución y la política de efectivo sin señal.
V1 se reentrena con esta máscara; no se compara causalmente con un control antiguo
que usaba otras filas. El loader interno ahora filtra Parquet antes de devolver
observaciones; solo los checksums recorren los archivos completos.

**El desfase de 15 minutos es un supuesto aceptado para este experimento, no una
prueba de disponibilidad original.** Tampoco elimina posibles revisiones del
histórico. La captura futura con `received_at` permitirá estudiar latencia futura,
sin certificar retrospectivamente la de 2020–2023.

## Verificación y artifacts

- Suite: **148 tests pasan, 2 de integración omitidos** por requerir DB.
- Diez nuevos casos prueban elegibilidad estricta y milisegundos, caducidad,
  invariancia ante eventos futuros, media por eventos, reinicio tras huecos,
  rechazo de entradas inválidas, warmup y emparejamiento con purga/velas completas.
- Se refuerza la prueba del loader para comprobar el filtro de particiones.
- Ruff y hooks de commit pasan.
- **40 modelos**, predicciones reproducidas exactamente al recargarlos,
  **120 backtests de estrategias** y 8 backtests de referencia.
- El verificador de artifacts comprueba emparejamiento de predicciones/targets,
  fechas de equity, elegibilidad temporal, hash de features y métricas guardadas;
  reconstruye los inputs del evaluador desde equity/fills/trades y obtiene
  **los mismos dos veredictos JSON**.

Directorio: `data/experiments/iteration-11-20260929-funding/`.
MLflow: experimento **7**, `spot-iteration-11-funding`, ejecución
[`0538370fc6c04678bfff567490d0dd75`](http://localhost:5000/#/experiments/7/runs/0538370fc6c04678bfff567490d0dd75).
Incluye `protocol.json`, copias de protocolo/criterio, `funding_metadata.json`,
`funding_features.parquet`, `funding_alignment.parquet`, `coverage.csv`,
`comparison.csv`, modelos/predicciones/operaciones/curvas por semilla/fold,
`funding_verdict.json`, `v1_matched_verdict.json` y `report.json`.

## Reproducir

En WSL/Ubuntu con el entorno virtual del proyecto activado:

```bash
make experiment-funding DATA_ARGS="--dataset data/processed/btc-usdt-spot-15m-v1-2020-01-2026-08-20260925T164411092396Z --funding data/audits/derivatives-20260929/funding"

python scripts/verify_funding_experiment.py data/experiments/iteration-11-20260929-funding
```

La primera orden crea otro directorio; nunca sobrescribe resultados. El runner
exige código registrado, documentos iguales al preregistro, snapshots fijados
y cobertura suficiente. Opciones: `--output`, `--tracking-uri`, `--no-mlflow`.
La segunda orden solo verifica artifacts, sin entrenar ni abrir datos reservados.

## Revisión del contexto y siguiente decisión

El documento de contexto orienta correctamente hacia validar información nueva
antes de añadir complejidad. Al contrastarlo con código y artifacts conviene
precisar tres puntos:

1. El snapshot completo contiene **232.767 filas de features**; 139.245 son las
   filas de train con label/split elegible. No son el total de enero 2020–agosto 2026.
2. Tres eventos de funding separados por 8h abarcan 16h entre el primero y el
   tercero. Aquí el warmup adicional frente a v1 es 4h, no 24h.
3. Diez recetas rechazadas no demuestran que v1 carezca de toda información,
   ni balanced accuracy superior a 1/3 prueba ventaja rentable. Holding 1h es
   una mejora observada en desarrollo, no una validación independiente.

Quedan completados los cuatro pasos propuestos para la iteración 11. El siguiente
trabajo debería empezar por una nueva hipótesis económica y su horizonte de
decisión, antes de elegir otra fuente o modelo. Este rechazo no justifica ajustar
umbrales o seleccionar semillas a posteriori, abrir el test, ni incorporar OI
sin resolver su cobertura. La captura futura de funding sigue pendiente para
el equipo definitivo; no forma parte de esta ejecución histórica.
