# Decisión de arquitectura después de it.17

Fecha: 2026-10-13. Revisión de resultados existentes: cero modelos nuevos,
cero backtests nuevos y ningún acceso al test reservado.

## Decisión de trabajo

Cerrar la exploración incremental de la receta BTC spot long-only,
clasificador 4h, features v1, gate SMA50/200 y sus variantes recientes.
Mantener el mandato y risk-return-v1. No seleccionar una semilla, modificar
el benchmark ni iniciar una it.18 por inercia.

El siguiente trabajo técnico recomendado es preparar captura prospectiva
de datos con tiempos de recepción, limitada y auditable. Tiene un objetivo
de calidad de datos, no de rentabilidad ni de promoción. Su contrato se
define en [prospective-data-plan.md](prospective-data-plan.md).
Esta revisión no instala ni deja ejecutándose un servicio.

## Evidencia que sostiene la decisión

| Intervención | Resultado | Lectura limitada a lo probado |
|---|---|---|
| [It.13: horizonte 4h + gate](iteration-13-results.md) | 2/5 | Rentabilidad, riesgo y stress pasan 5/5; falta consistencia |
| [It.14: clases ±75 pb](iteration-14-results.md) | 1/5 vs 2/5 | El ajuste de target no resolvió el problema |
| [It.15: SP500](iteration-15-results.md) | 1/5 vs 2/5 | Mejora retorno y DD en 5/5, pero no la estabilidad exigida; condicionado a disponibilidad |
| [It.16: salida DOWN](iteration-16-results.md) | 2/5 vs 1/5 | Mayor persistencia no basta y reaparece un fallo de riesgo |
| [Momentum semanal sin ML](daily-momentum-screen-results.md) | Falla gates económicos | −6,90% neto, DD53,72%; no es una prueba de cinco semillas |
| [It.17: flujo agresor](iteration-17-results.md) | 1/5 vs 2/5 | Menor retorno compuesto en 4/5; beneficio neto por trade 13,16 vs15,62 pb |

No sumar estas comparaciones como experimentos independientes. Comparten
mercado, folds y buena parte de la receta. Las cinco semillas miden
sensibilidad al entrenamiento, no cinco historias de mercado diferentes.
Los preregistros locales evitan elegir variantes dentro de cada ejecución,
pero no convierten folds reutilizados en confirmación independiente.

## Qué significa superar B&H en este proyecto

El criterio no exige más retorno absoluto en todos los periodos. Exige
retorno neto compuesto positivo, DD≤15% por fold y concatenado, stress
positivo y Sharpe>B&H con DD≤B&H en al menos tres de cuatro semestres,
con la excepción cash vigente; todo ello en ≥4/5 semillas.

H1 2023 falla repetidamente, pero **aprobar H1 no es obligatorio**. También
se puede cumplir pasando los otros tres folds. Las recetas recientes no
logran ese tercer fold de forma suficientemente estable. Por eso no se
debe convertir H1 en un objetivo de optimización retrospectiva separado.

Los resultados tampoco prueban imposibilidad matemática de alpha long-only.
Rechazan recetas concretas, no todos los modelos, activos o horizontes.
El balance sí reduce la justificación para seguir haciendo cambios pequeños.

## Qué no está justificado ahora

- Cambiar a Transformer/LightGBM por capacidad sin demostrar qué limitación
  de representación o generalización se pretende resolver.
- Combinar SP500 y flujo después de sus rechazos sin una hipótesis de
  interacción previa e independiente del resultado que se desea obtener.
- Comprar datos, ampliar hardware o descargar todos los aggTrades para
  repetir desequilibrios ya disponibles en klines.
- Barrer ventanas diarias, umbrales, retardos, SMA o holding hasta pasar.
- Reetiquetar las recetas como filtros de exposición aprobados bajo otro
  benchmark. Ese sería un mandato nuevo, no un rescate del resultado actual.
- Usar el test 2025–2026 para decidir qué familia investigar.

## Condiciones para reabrir investigación predictiva

Antes de una nueva iteración debe existir una ficha breve que responda:

1. ¿Qué mecanismo económico diferente se espera explotar y qué observación
   independiente de estos resultados lo motiva?
2. ¿Qué información nueva distingue la hipótesis de las familias rechazadas?
3. ¿Cuál es el baseline simple y qué aportación incremental debe justificar ML?
4. ¿Qué instrumento, ejecución, costes y disponibilidad temporal se pueden
   sostener con datos verificables?
5. ¿Qué se fija antes de evaluar, qué resultado obliga a parar y qué datos
   seguirán sin consultar?

No exigir que toda hipótesis nueva venga respaldada por beneficio histórico;
sí exigir una razón concreta para esperar algo distinto. Hasta entonces,
la alternativa válida es no entrenar otro modelo.

## Continuidad técnica y límites

La captura de cierres de klines permite observar recepción, duplicados,
revisiones y desconexiones sobre datos futuros. No prueba retrospectivamente
las latencias de SP500 o funding, no acredita los supuestos de 2020–2023,
no vuelve rentable it.17 y no sustituye una hipótesis económica nueva.

Los datos prospectivos de calidad no serán un holdout de rendimiento si se
inspeccionan para diseñar la siguiente estrategia. Separar explícitamente
ese uso del futuro test de una receta congelada. No ampliar silenciosamente
el test histórico ni mezclar capturas nuevas con su snapshot.

Situación operativa comprobada: `src/data/collectors/` contiene únicamente
su módulo inicial; no hay un collector prospectivo terminado en el repo.
Se preservan los modelos, datasets y artifacts existentes. No paper ni live.
La última suite completa registrada tiene 250 tests pasando y dos omitidos;
esta revisión solo modifica documentación y no vuelve a ejecutar experimentos.
