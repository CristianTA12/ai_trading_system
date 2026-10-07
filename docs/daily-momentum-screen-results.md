# Momentum diario semanal — prueba cerrada sin promoción

Fecha: 2026-10-08. [Protocolo](daily-momentum-screen-protocol.md) registrado
en `698b838`; implementación en `1cb6e20`, antes de evaluar. Hipótesis:
persistencia semanal de retornos, decisiones diarias, sin clasificador.

**La regla falla los cuatro gates económicos.** No se entrena un modelo
ni se prueban otras ventanas para rescatar este resultado.

| Estrategia | Compuesto neto base | Stress | DD concatenado | Consistencia |
|---|---:|---:|---:|---:|
| Momentum 7 días | −6,90% | −8,17% | 53,72% | 1/4 |
| SMA50/200 solo | +26,34% | +26,24% | 24,21% | 2/4 |
| B&H | −8,87% | −8,95% | 67,51% | Referencia |
| Efectivo | 0% | 0% | 0% | 2/4 por excepción cash |

Retornos compuestos enlazan cuatro folds, cada uno liquidado y reiniciado:
no representan una posición B&H continua sin liquidaciones intermedias.
El evaluador compara B&H consigo mismo sin superioridad estricta; por eso
su contador interno es cero y no se interpreta como rechazo del benchmark.
Efectivo incumple rentabilidad estrictamente positiva; no es un candidato.

| Fold | Momentum neto | Sharpe momentum | Sharpe B&H | DD momentum | Trades |
|---|---:|---:|---:|---:|---:|
| 2022 H1 | −16,47% | −0,9061 | −2,0351 | 31,58% | 16 |
| 2022 H2 | −35,22% | −2,5921 | −0,3842 | 40,94% | 17 |
| 2023 H1 | +40,33% | 2,0762 | 2,7343 | 21,63% | 18 |
| 2023 H2 | +22,60% | 1,4383 | 1,8884 | 18,50% | 18 |

69 operaciones en total. En H1 2023 la exposición es 55,78%; capturar más
rally no basta para superar Sharpe B&H ni cumplir DD≤15%. En 2022 H2
pierde incluso más que B&H (−17,13%). Reducir la frecuencia de decisiones
no elimina el riesgo de señales de tendencia desfavorables.

## Qué permite concluir

El clasificador no era el único obstáculo: esta alternativa sin ML también
falla, por motivos visibles de riesgo y selección temporal. No demuestra
que un modelo nunca pueda mejorarla ni que todas las estrategias diarias
fallen. Tampoco justifica mezclar ahora momentum y SMA o elegir otra ventana.
SMA solo obtiene retorno positivo, pero supera el DD permitido y no alcanza
consistencia; una estrategia simple también debe rendir cuentas al mandato.

Se mantiene cerrado el test 2025–2026. No se leyó/evaluó 2024 en esta prueba.
No hay cambio de `risk-return-v1`, selección de semillas ni promoción:
la regla es determinista y la estabilidad entre semillas no se ha validado.
El identificador 42 usado por el evaluador de una trayectoria es únicamente
compatibilidad de API, se elimina del informe y no implica entrenamiento.

## Comprobación y archivos

- 48 backtests: cuatro estrategias, cuatro folds, tres escenarios.
- 242 tests pasan; dos de integración omitidos. Cuatro pruebas nuevas de
  frontera temporal, huecos diarios, señal no positiva y causalidad futura.
- Todas las señales contrastadas mediante cálculo escalar independiente
  por fechas antes de ejecutar; sin rolling ni as-of en la comprobación.
- Métricas de los 48 backtests y cuatro veredictos económicos recalculados
  desde equity/fills/trades guardados. Esta segunda comprobación reutiliza
  las funciones de métricas/evaluación; no es otro motor de ejecución.
- Datos originales verificados por hashes, código y protocolo registrados.

Artifacts: `data/experiments/daily-momentum-screen-20261008/`.
[MLflow, experimento 16](http://localhost:5000/#/experiments/16/runs/75532a8f150543e88dda289047954fe9).
Revisión: `python -m scripts.verify_daily_momentum_screen`.

## Dirección tras el cierre

Cerrar este baseline semanal. La siguiente revisión debe justificar una
fuente de información distinta antes de otro entrenamiento. Una opción
concreta para auditar es flujo agresor de operaciones ejecutadas (aggTrades),
sin prometer señal y sin descargar masivamente todavía: cobertura histórica,
semántica maker/taker, timestamps, coste de almacenamiento y alineación causal.
Solo una auditoría viable justificaría un protocolo predictivo; no se
presupone que los datos nuevos mejoren esta evidencia ni se abre otra prueba aquí.
