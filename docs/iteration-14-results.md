# Iteración 14 — Umbral ±75 pb: rechazo, sin mejora de consistencia

Fecha: 2026-10-05. **Candidato 1/5 semillas; control ±100 pb 2/5. Se exigen
4/5: no hay promoción.** 2023 H1 sigue fallando en todas las semillas.
No se ha probado ±50 pb ni modificado holding, gate, costes o criterio.

Preregistro [iteration-14-protocol.md](iteration-14-protocol.md), commit
`c1b84b3`; implementación `46c5583`, ambos anteriores al entrenamiento.
Motivación y limitaciones: [diagnóstico H1](diagnostic-2023h1-consistency.md).

## Resultado de la receta completa

20 modelos nuevos con clases ±75 pb; 20 modelos de it.13 reutilizados como
control ±100 pb. Mismas filas, semillas, 20 features v1 y horizonte 4h;
holding 240 minutos y gate diario SMA50>SMA200. Recalcular los pesos según las
nuevas clases forma parte de la intervención; la regla de ponderación no cambia.

Los retornos de esta tabla son compuestos netos de los cuatro folds 2022–2023,
reiniciando las posiciones por fold. El DD es el de la curva concatenada.

| Semilla | Candidato base | Candidato stress | DD candidato | Consistencia | Cumple todo | Control base | Control cumple |
|---|---:|---:|---:|:---:|:---:|---:|:---:|
| 42 | +16,18% | +13,00% | 14,50% | 3/4 | Sí | +20,19% | No |
| 123 | +18,28% | +15,08% | 10,20% | 2/4 | No | +19,70% | No |
| 456 | −1,33% | −3,96% | 17,32% | 2/4 | No | +29,90% | Sí |
| 789 | +20,80% | +17,53% | 10,53% | 2/4 | No | +14,58% | No |
| 2026 | +14,23% | +11,03% | 12,64% | 2/4 | No | +26,29% | Sí |

| Gate risk-return-v1 | ±75 pb | Control ±100 pb |
|---|:---:|:---:|
| Compuesto base positivo | 4/5 | 5/5 |
| DD ≤15%, cada fold y concatenado | 4/5 | 5/5 |
| Consistencia ≥3/4 folds | 1/5 | 2/5 |
| Compuesto stress positivo | 4/5 | 5/5 |
| Todos simultáneamente | **1/5** | **2/5** |

Ambos brazos pasan 2022 H1 en las cinco semillas y 2022 H2 por la excepción
cash. En 2023 H2, solo 42 pasa con ±75 pb; con ±100 pb pasan 456 y 2026.
No se selecciona 42 como estrategia ni se mezclan semillas entre semestres.

## El bloqueo de 2023 H1 persiste

B&H del mismo fold: retorno +84,03%, Sharpe 2,7343. Ninguna semilla lo supera.

| Semilla | Retorno ±75 pb | Sharpe ±75 pb | Sharpe control | DD ±75 pb | Exposición ±75 pb | Trades ±75 / ±100 |
|---|---:|---:|---:|---:|---:|---:|
| 42 | +1,18% | 0,2145 | 0,7962 | 14,50% | 7,48% | 80 / 74 |
| 123 | +10,99% | 1,0123 | 1,2641 | 10,19% | 7,16% | 76 / 77 |
| 456 | −8,69% | −0,6487 | 1,3690 | 16,41% | 7,29% | 78 / 82 |
| 789 | +18,48% | 1,5631 | 0,2249 | 10,53% | 7,33% | 78 / 75 |
| 2026 | +5,68% | 0,6330 | 0,9553 | 11,79% | 7,59% | 81 / 81 |

Solo 789 mejora retorno y Sharpe de H1 frente al control. La mayor proporción
de etiquetas UP (train H1: 21,89% frente a 16,91%) no se traduce en una mejora
general de participación ni de selección económica. Hay 393 trades H1 frente
a 389 del control, sin aumento sustancial de exposición.

## Comparación descriptiva agregada

Pooled sobre los cuatro folds y cinco semillas; las semillas comparten mercado,
por lo que estos trades no constituyen observaciones independientes de una nueva muestra.
La media por trade pondera por número de operaciones; la exposición es la media
aritmética de los 20 pares semilla/fold, no una exposición de cartera combinada.

| Métrica | ±75 pb | ±100 pb |
|---|---:|---:|
| Operaciones | 690 | 697 |
| Media bruta por trade | 20,49 pb | 25,64 pb |
| Media neta base por trade | 10,48 pb | 15,62 pb |
| Media neta stress por trade | 8,47 pb | 13,61 pb |
| Exposición media | 3,20% | 3,23% |

En retorno neto por semilla/fold, el candidato mejora 5 de 20 comparaciones,
empata 5 (2022 H2 íntegramente cash) y empeora 10. El retorno compuesto mejora
solo en una semilla. El cambio no apoya la hipótesis económica preregistrada.
Esto rechaza **esta receta ±75 pb**; no demuestra que cualquier definición
alternativa del target falle, ni identifica causalmente una única causa del
problema de la estrategia.

## Verificación y trazabilidad

- 128 backtests: 120 de los dos brazos en bruto/base/stress, más 8 benchmarks
  B&H/cash. No se han simulado otros umbrales.
- Antes de entrenar, verificación de it.13 y recarga de sus 20 modelos:
  probabilidades idénticas sobre las features actuales, mismas versiones,
  labels, filas y gate. Cobertura >=95% en todos los folds.
- Control reproducido **exactamente** en equity, fills y trades, en todos
  los escenarios. Veredicto completo idéntico al original.
- Verificación independiente de políticas, métricas, clases y veredictos:
  128 backtests aprobados; las 150 predicciones sin outcome completo
  (15 timestamps × 5 semillas × 2 brazos) permanecen disponibles para operar.
- Suite completa: **171 tests pasan, 2 se omiten** por dependencia de BD.
  Ruff y hooks pre-commit aprobados. Los cinco tests nuevos comprueban
  fronteras de clase y detección de diferencias incluso mínimas del control.
- 2024 y test 2025–2026 siguen sin evaluar. Inputs originales no modificados;
  hashes, versiones y commits quedan registrados en `protocol.json`.

Artifacts: `data/experiments/iteration-14-20261005-threshold-75`.
[MLflow local, experimento 11, run f6a6af349a4c4372ad458cf446205294](http://localhost:5000/#/experiments/11/runs/f6a6af349a4c4372ad458cf446205294).

```bash
python -m src.training.threshold_experiment --output data/experiments/<directorio-nuevo>
python -m scripts.verify_threshold_experiment data/experiments/iteration-14-20261005-threshold-75
pytest -q
```

El runner exige protocolo y código registrados y rechaza sobrescribir un run.
La reproducción debe hacerse en el mismo entorno de librerías del control.

## Decisión y siguiente bloque

**Cerrar it.14 como rechazada.** It.13 permanece como referencia de investigación,
también rechazada para promoción. No bajar ahora a 50 pb ni modificar el holding
para buscar retrospectivamente una variante aprobada.

El siguiente bloque del plan es una **auditoría de viabilidad y causalidad de
datos macro** antes de diseñar un experimento: cobertura, horario real de
disponibilidad, revisiones, cierres, festivos y desfases. No hay todavía evidencia
de que macro aporte edge. Ese trabajo requiere sus propias fuentes y protocolo;
no se ha iniciado ingestión ni entrenamiento macro en esta iteración.
El cierre documental general y la consolidación del runner siguen pendientes;
este runner reutiliza los componentes existentes pero no declara completada la fase B.
