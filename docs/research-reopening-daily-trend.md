# Ficha de viabilidad — Tendencia diaria de varias semanas

Fecha: 2026-10-28. **No apta para abrir un experimento con la justificación actual.**
Revisión documental autorizada por el usuario tras el cierre de it.19.
Cero backtests, entrenamientos, descargas de datos o accesos a datos reservados.
No es un preregistro ni una iteración 20.

## Propuesta y mecanismo

Propuesta inicial: BTCUSDT spot long/flat, decisiones diarias, capturar tendencias
de varias semanas mediante una regla sencilla antes de introducir ML.
Mecanismo supuesto: persistencia de movimientos de precio suficiente para
compensar costes y periodos adversos. No se ha demostrado esa ventaja para una
receta nueva. Menor frecuencia no implica por sí misma mejor riesgo o retorno.

La recomendación inicial omitió un antecedente material: esta familia económica
ya se examinó sin ML. Varias semanas no son idénticas a siete días, pero cambiar
el horizonte no introduce por sí solo un mecanismo ni información diferentes.
No se presenta esta propuesta como una hipótesis completamente nueva.

## Antecedentes que impiden reabrirla por inercia

El [preregistro del 8 de octubre](daily-momentum-screen-protocol.md) fijó
momentum de siete días con decisiones diarias, sin clasificador ni gate añadido.
La señal era C[d]/C[d−7]−1 > 0, con ocho cierres consecutivos y disponibilidad
estrictamente anterior a la ejecución. Se comparó con B&H, cash y SMA50/200 solo.

Los [resultados verificados](daily-momentum-screen-results.md) fueron:

| Baseline | Neto compuesto | Stress | DD concatenado | Consistencia |
|---|---:|---:|---:|---:|
| Momentum 7 días | −6,90% | −8,17% | 53,72% | 1/4 |
| SMA50/200 solo | +26,34% | +26,24% | 24,21% | 2/4 |
| B&H | −8,87% | −8,95% | 67,51% | Referencia |

Son cuatro folds liquidados y reiniciados, no una posición continua 2022–2023.
Momentum realizó 69 operaciones y falló los cuatro gates económicos. SMA solo
tampoco cumplió riesgo ni consistencia. No hay cinco semillas: son reglas
deterministas. No volver a ejecutar esas pruebas para confirmar lo ya archivado.

La literatura de momentum ya figuraba como motivación en aquel preregistro.
Esta ficha no aporta nueva evidencia externa que justifique escoger una ventana
de varias semanas. No atribuye resultados adicionales a esa literatura.

Además, [it.18](iteration-18-results.md) redujo decisiones pero perdió retorno;
[it.19](iteration-19-results.md) prolongó posiciones y recuperó retorno a costa
de riesgo. Son intervenciones diferentes, no réplicas del baseline diario.
En conjunto no justifican asumir que menor rotación resolverá el mandato.

## Baseline, ejecución y causalidad

El baseline sin ML solicitado ya existe: conservar la regla semanal archivada
como referencia rechazada. No definir ahora una nueva ventana, media móvil,
stop o sizing para rescatarla. No añadir ML sin una aportación concreta distinta
de intentar corregir los resultados conocidos.

El alcance propuesto mantenía BTC spot, sin leverage ni shorts, costes taker
0,0004 por lado, slippage base 0,0001 y stress 0,0002. Las decisiones diarias
no justifican medir DD solo a cierres diarios: conservar la valoración 15m
del motor para comparar riesgo en condiciones equivalentes.
Los cierres históricos y su contrato causal ya están documentados en el
preregistro semanal; disponer de esos datos no acredita una ventaja económica.

## Benchmark y criterio que seguirían vigentes

El objetivo no es exclusivamente superar el retorno bruto de B&H. Los gates
económicos de `risk-return-v1` exigen:

- Neto compuesto positivo y compuesto stress positivo.
- DD máximo <=15% en cada fold y en la curva concatenada.
- Sharpe superior a B&H y DD no superior a B&H en >=3/4 semestres, con la
  excepción cash original. Mismas barras y costes; Sharpe diario incluyendo cash.

No cambiar el benchmark ni rebajar gates para aprobar baja exposición. En una
regla determinista la estabilidad 4/5 semillas no aplica y no se considera
satisfecha; nunca duplicar la misma trayectoria ni emitir promoción global.
Un eventual paso de gates económicos solo justificaría diseñar validación
posterior, no trading. El archivo `risk-return-v1.yaml` permanece intacto.

## Separación de datos y decisión

2022–2023 ya es desarrollo adaptativo intensivamente consultado; no puede ser
confirmación independiente de otra variante. 2024 ya fue explorado y tampoco
constituye un holdout nuevo. En esta revisión ambos permanecen sin consultar,
al igual que el test reservado 2025–2026.

Antes de evaluar cualquier hipótesis admisible habría que congelar receta,
periodo de evaluación futura, duración, métricas y reglas de parada en un
protocolo aparte. No inventar aquí una duración suficiente sin definir la
hipótesis ni usar el test para elegirla. Las capturas de calidad previas no
constituyen automáticamente un holdout de rendimiento.

**Decisión: descartar la reapertura diaria propuesta por falta de novedad
justificada.** No se fija otra ventana ni se ejecuta un nuevo screen.
Esto no prueba que toda tendencia diaria sea inviable: impide repetir una
familia descartada bajo el nombre de nueva técnica.

Una ficha futura tendría que aportar mecanismo e información realmente distintos,
evidencia externa independiente de los folds, baseline y ejecución defendibles.
Si requiere otro activo, instrumento, shorts, sizing o benchmark, deberá
explicitar el cambio de alcance antes de cualquier experimento. Esta ficha
no autoriza esos cambios ni inicia otra búsqueda. La familia actual sigue cerrada.
