# It.19 — Última intervención: histéresis sobre it.13

Fecha: 2026-10-28. Preregistro anterior a implementación y evaluación.
El usuario autoriza una última intervención aislada después del rechazo de
it.18. Cero modelos nuevos, features o búsquedas de parámetros.

## Hipótesis y comparación congelada

Mantener la posición durante NEUTRAL/UP débil podría reducir rotación y costes.
No garantiza mejorar retorno ni resolver el déficit bruto de 2023 H1. El
79,70% de salidas del diagnóstico anterior corresponde a SP500, no a v1.
It.16 probó DOWN argmax sobre SP500; aquí se aísla el umbral con tres brazos
emparejados sobre las probabilidades originales v1 de it.13:

1. `four_hour_regime`: control original; después del mínimo, salir cuando
   desaparece UP argmax con p_up>=0,50.
2. `four_hour_down`: control de mecanismo; salir por DOWN argmax sin umbral.
3. `four_hour_hysteresis`: única candidata; salir por DOWN argmax Y p_down>=0,50.

Entrada idéntica: UP argmax Y p_up>=0,50. Orden de desempate DOWN, NEUTRAL, UP.
Decisiones cada 15m; holding mínimo ordinario de 240 minutos transcurridos.
Solo cuenta la señal actual: no memorizar DOWN ocurrido dentro del mínimo.
NEUTRAL, UP insuficiente y DOWN débil mantienen la candidata. No introducir
un segundo umbral de p_up para mantener ni probar variantes.
Las probabilidades ponderadas no están calibradas: 0,50 es un score, no una
probabilidad empírica demostrada.

Gate diario SMA50>SMA200 original. Gate cerrado/ausente o predicción ausente
fuerzan cash inmediato, incluso dentro del mínimo. Reapertura exige nueva
entrada válida, sin posición latente. Cada fold empieza cash; el motor liquida
al cierre final. Sin stops, cooldown, sizing nuevo ni cambios de ejecución.

## Datos, ejecución y auditoría

Fuente inmutable: `data/experiments/iteration-13-20260930-four-hour`.
20 modelos/probabilidades congelados: semillas 42,123,456,789,2026 y folds
2022 H1/H2, 2023 H1/H2. Mismas filas originales, sin filtrar por outcome futuro.
No deserializar >=2024; se permite verificar hashes completos del dataset.
Capital 10.000 por fold, spot long/flat 100%, sin apalancamiento.
Bruto sin costes; base taker 0,0004 por lado y slippage 0,0001; stress mismo fee
y slippage 0,0002. Mismo motor que it.13.

Preregistro y código comprometidos en Git antes de evaluar. Reproducir primero
los 60 backtests originales, con igualdad exacta de targets/equity/fills/trades.
Si difieren, abortar sin relajar tolerancias. Después 60 ejecuciones por cada
alternativa y ocho benchmarks B&H/cash: 188 backtests, cero entrenamientos.
Comprobar ambas alternativas con recorrido independiente de estado.
Guardar targets, ledgers, métricas, veredictos, hashes antes/después, manifiesto
y registro MLflow. El manifiesto parcial de it.13 no acredita históricamente
todos sus archivos: conservar esta limitación junto con la reproducción exacta.
Verificador posterior recalcula métricas y veredictos desde ledgers guardados;
comparte funciones métricas/evaluador, no es un segundo motor de ejecución.

## Criterio y cierre

`risk-return-v1`, SHA256
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
Exigir >=4/5 semillas: compuesto neto positivo, DD<=15% por fold y concatenado,
compuesto stress positivo y consistencia frente a B&H >=3/4 folds con excepción
cash vigente. 2023 H1 no es obligatorio por sí solo. No alterar el criterio.
Informar bruto/neto, costes, exposición, operaciones, DD y consistencia completa.

Si la candidata falla, cierre formal de esta familia incremental, incluso si
el control DOWN pasa. No sustituir retrospectivamente la candidata, optimizar
umbrales/holding ni elegir semillas. Otra investigación requerirá una hipótesis
económica completamente nueva o un mandato diferente. Si pasa, resultado
exploratorio en folds reutilizados: sin promoción automática, despliegue ni
acceso automático a validación 2024/test reservado.
