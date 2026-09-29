# Acuerdo prospectivo de riesgo y rentabilidad v1

Fecha: 2026-09-29. Acordado antes de la iteración 10, tras la revisión del usuario.
La definición de referencia está en [risk-return-v1.yaml](risk-return-v1.yaml).
Este cambio documenta el acuerdo; todavía no implementa un evaluador automático
ni ejecuta entrenamientos o abre el test.

## Objetivo y alcance

Buscar rentabilidad neta positiva en el conjunto de cuatro semestres con pérdidas
limitadas y mejor relación rentabilidad/riesgo que Buy & Hold. Un semestre entero
en efectivo puede aportar valor durante una caída. El límite acordado de drawdown
es 15%; es una tolerancia de diseño, no una garantía fuera de muestra.

Se mantienen las seis dimensiones propuestas, sin aprobar retroactivamente ninguna
variante. Los resultados anteriores conservan el criterio histórico de al menos
tres semestres con retorno neto estrictamente positivo.

| Dimensión | Regla para una semilla |
|---|---|
| Rentabilidad | Retorno neto compuesto de los cuatro folds > 0 |
| Riesgo absoluto | Drawdown <= 15% en cada fold y en la curva concatenada |
| Consistencia | En >=3/4 folds, Sharpe > B&H y drawdown <= B&H |
| Efectivo | Excepción de consistencia si permanece íntegramente en cash y B&H pierde |
| Fricciones | Retorno compuesto > 0 con slippage de 2 pb por ejecución |
| Estabilidad | Al menos 4/5 semillas cumplen conjuntamente todas las reglas anteriores |

Semillas fijadas: **42, 123, 456, 789, 2026**. No se elige la mejor ni se
mezclan folds de distintas semillas para superar el criterio. Se publican las cinco,
incluida cualquier fallida. Un resultado ausente o no finito no puede contar como
aprobado; un error técnico se corrige y se repite con la misma receta y semilla.

## Definiciones operativas

- Folds: 2022 H1, 2022 H2, 2023 H1 y 2023 H2, en orden cronológico.
  Entrenamiento expansivo, purga temporal y control emparejado sobre las mismas
  filas y fechas. Features, target, modelo y política se fijarán en el protocolo
  específico de la próxima receta, antes de entrenarla.
- Costes base: taker 0,04% y slippage 0,01% **por ejecución**, tanto para
  candidato como para B&H. Stress: fee idéntica y slippage 0,02%. No se usa maker
  como supuesto favorable. El stress exige únicamente rentabilidad compuesta
  positiva; riesgo y consistencia se exigen en el escenario base.
- El stress reutiliza predicciones y reglas, recalculando ejecución, costes y
  capital disponible. No se aproxima restando un coste fijo al retorno final.
- Retorno compuesto: `prod(1 + r_fold) - 1`. Concatenar las curvas normalizadas
  multiplicando cada una por el capital final de la anterior; no reiniciar el
  máximo histórico en los límites de semestre. No arrastrar posiciones entre
  folds y contabilizar sus liquidaciones finales. Eliminar solo el punto inicial
  duplicado de cada nuevo fold, conservando todos los cambios de equity.
- Drawdown: magnitud positiva de `1 - equity / equity.cummax()`, incluyendo el
  capital inicial. Se mide al cierre de las velas, como en el motor existente;
  no es una estimación del peor drawdown intravela.
- Sharpe: media de retornos diarios UTC dividida por desviación estándar muestral
  (`ddof=1`), multiplicada por `sqrt(365)`, tipo libre de riesgo cero. Incluir
  días sin operar. Usar la misma convención temporal del motor para B&H.
- La excepción cash requiere **cero posiciones y cero ejecuciones durante todo
  el semestre**, equity constante y B&H neto estrictamente negativo. Exposición
  baja o acabar con retorno cero no equivalen a cash. Si B&H no pierde, cash no
  cumple consistencia. Su Sharpe es indefinido, nunca se sustituye por cero.
  Cualquier otro Sharpe indefinido hace fallar la comparación de ese fold.
- Comparar con valores completos, no con porcentajes redondeados para informes.
  Se permite igualdad en drawdown; se exige superioridad estricta en Sharpe y
  retorno compuesto estrictamente positivo.

## Interpretación de la revisión

Los dos semestres bajistas **no pasan automáticamente**: solo lo hacen por la
excepción si la estrategia realmente permanece en efectivo en cada uno. No se
pueden imponer retrospectivamente fechas en cash usando el signo conocido de B&H.

Una exposición menor puede reducir riesgo, pero no garantiza mayor Sharpe: también
reduce el retorno medio, y los días en efectivo forman parte del cálculo. Limitar
drawdown tampoco obliga matemáticamente a una exposición concreta; importan tamaño,
momento y trayectoria de las posiciones.

Superar 4/5 semillas aporta evidencia de estabilidad ante esas semillas, no prueba
una señal real ni resuelve por sí solo la sensibilidad a eliminar filas. La ablación
observó cambios de cobertura, muestreo y pesos; no aisló una causa única. No se
presentará este criterio como una prueba de estabilidad ante perturbaciones de datos.

Tampoco todos los retornos brutos observados son positivos: en 2022 H2 el control
emparejado perdió 17,54% bruto y lags 14,81%, según los artifacts de la
[ablación](lags-ablation-results.md). Las fricciones no son la única limitación.

## Decisión y trazabilidad

Los cuatro folds internos ya han informado varias decisiones. Este acuerdo es
**exploratorio y prospectivo**, no una validación independiente ni una forma de
eliminar el sesgo acumulado por selección. 2024 también fue explorado.

Si una nueva receta supera el criterio, se congela junto con un protocolo final
antes de consultar test 2025-2026. Ese protocolo debe fijar cómo usar las semillas
o un ensemble y qué decisión permite el test; no se seleccionará por su resultado.
Superar este acuerdo no autoriza operar con dinero real ni abre el test ahora.

El próximo runner deberá guardar la copia y hash del YAML, versión de código,
datos, receta, resultados por fold/semilla/escenario, curvas concatenadas, comparación
con B&H, gate histórico y motivos de cada decisión en artifacts y MLflow.
El acuerdo debe registrarse en Git antes de ejecutar la iteración 10.

Cualquier cambio de umbral o dimensión requiere otra versión, con motivo explícito,
antes de nuevos resultados. No convierte retrospectivamente un rechazo en aprobación;
reutilizar los mismos folds sigue siendo exploratorio.
