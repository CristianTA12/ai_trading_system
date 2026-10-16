# Ficha de reapertura: atención externa a Bitcoin

Fecha: 2026-10-16. **Candidata a auditoría de datos; no autoriza todavía una
iteración 18 ni constituye un preregistro de rendimiento.** Cero entrenamientos,
backtests, consultas de precios históricos o accesos al test reservado en esta revisión.

Actualización: [auditoría ejecutada](attention-source-audit.md). La muestra tiene
31/31 días, pero no acredita publicación histórica ni revisiones. Se archiva
la candidata para ejecución histórica inmediata; no se abre it.18.

## Decisión

Investigar si una medida externa de atención permite distinguir demanda
persistente de movimientos de precio sin participación nueva. El mecanismo
propuesto es que la búsqueda de información puede preceder decisiones de
participación y compras. Es una hipótesis: también puede ser una reacción a
retornos pasados, pánico vendedor o curiosidad sin intención de operar.

La información sería actividad fuera del exchange, distinta de OHLCV, funding,
SP500 y desequilibrio taker. No consiste en añadir otro lookback del precio a
la receta 4h rechazada. La captura prospectiva de klines ya terminada no contiene
esta información y no justifica otra tanda para estudiarla.

## Evidencia externa y sus límites

[Liu y Tsyvinski, Risks and Returns of Cryptocurrency (2018)](https://www.nber.org/papers/w24877)
reportan predictibilidad asociada a proxies de atención de inversores, además
de momentum. Esto motiva investigar atención, no prueba una estrategia actual
ni una señal basada en Wikipedia. En esta revisión se consultaron los resúmenes
indexados del editor y de la versión de autores; la descarga completa del PDF
de NBER devolvió 403. No se atribuyen al paper ventanas, umbrales, costes o
resultados netos que no se hayan leído.

El mismo trabajo motivó el ensayo previo de momentum; ese ensayo permanece
rechazado. Atención no hereda un resultado favorable de momentum: es otra
variable que debe justificar su aportación. Que una fuente sea nueva no basta.

La búsqueda sobre liderazgo BTC/ETH no aportó una justificación inequívoca
para elegir ETH como predictor de BTC a cuatro horas. No se selecciona esa
familia por mera correlación ni se prueban múltiples monedas hasta encontrar
una favorable. Esto es una decisión de prioridad, no prueba de inexistencia
de efectos entre activos.

## Fuente candidata: visitas a la página Bitcoin

Primera auditoría: Wikimedia, proyecto `en.wikipedia.org`, artículo `Bitcoin`,
granularidad diaria, todos los accesos y categoría de agente `user`. Esta
selección limita el alcance antes de mirar rendimientos. No se barrerán idiomas,
artículos o variantes para elegir la serie que mejor encaje con los folds.
Es una aproximación a atención informativa, no una medida de compradores únicos
ni una réplica de Google Trends. Una página en inglés no representa toda la
demanda mundial y `user` no garantiza que todo el tráfico sea humano.

La [referencia oficial de pageviews](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/reference/page-views.html)
indica disponibilidad del servicio desde julio de 2015. Esto hace plausible la
cobertura del periodo de desarrollo, pero aún no se ha descargado ni comprobado
la serie elegida. No confundir cobertura del servicio con cobertura de un artículo.

La [definición oficial](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/concepts/page-views.html)
distingue tráfico automatizado y explica que las visitas a redirecciones no se
acumulan sin más en la página de destino. Deben auditarse esos cambios de medida.

**Problema temporal ya identificado:** la [documentación de disponibilidad](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/troubleshooting.html)
explica que la carga posterior al periodo suele tardar horas y puede exceder
24 horas. Un 404 puede significar cero visitas o datos todavía no cargados.
Por tanto, fecha de observación no equivale a fecha de disponibilidad y no
se convertirán 404 en ceros. La [política de estabilidad de API](https://doc.wikimedia.org/generated-data-platform/aqs/analytics-api/documentation/stability-policy.html)
describe versiones del contrato, no garantiza inmutabilidad histórica de valores.

## Baseline y aportación que tendría que justificar ML

Propuesta para un eventual protocolo, todavía sin evaluación:

- Una sola variable de atención: razón entre el último recuento diario elegible
  y la mediana de los 28 días anteriores elegibles. Referencia calculada solo
  con pasado; faltantes o denominador cero dejan la señal no disponible.
- Baseline sin ML: long/flat según razón >1, con decisiones semanales y horizonte
  de una semana para evitar trasladar evidencia de atención a segundos o minutos.
  El calendario exacto y tratamiento de disponibilidad se congelarán si pasa la auditoría.
- Controles emparejados: B&H, cash y baseline de momentum semanal ya existente,
  sin alterar su regla para rescatarlo. Mismas filas y costes; las pérdidas de
  cobertura se reportan antes de cualquier métrica económica.
- BTCUSDT spot long-only, sin leverage, shorts, cambio de activo ni ejecución maker.
  Mantener costes taker/slippage vigentes y stress. No relajar risk-return-v1.
- ML solo tendría sentido si aporta valor incremental sobre esa regla y sobre
  información de precio ya conocida. No abrir un barrido de algoritmos, ventanas
  o normalizaciones. Su receta requeriría preregistro aparte.

28 días, razón 1 y horizonte semanal son elecciones de diseño por simplicidad,
no parámetros validados por la literatura ni por los folds del proyecto.
No se promete superar B&H. Un baseline determinista no se presenta como
aprobación de cuatro de cinco semillas: esa parte del criterio pertenece a
una eventual receta entrenada.

## Condiciones de avance y descarte

1. Auditar contrato, cobertura, huecos, unidad, cambios de definición y trazabilidad
   temporal sin leer retornos del periodo de validación. Guardar respuestas raw,
   recepción y hashes; una muestra de desarrollo basta para empezar.
2. Buscar evidencia de publicación y revisiones. Si solo hay snapshot actual y
   ninguna disponibilidad histórica acreditable, **no ejecutar backtest causal**.
   El permiso previo para un supuesto SP500 no se extiende a esta fuente.
   Un retraso de 48 h no se considerará una prueba ni se adoptará automáticamente.
3. Si no se resuelve esa condición, marcar histórica no apta y decidir entre
   observación prospectiva acotada o descartar la fuente. No sustituirla en silencio
   por Google Trends, otro idioma o un proxy seleccionado por rendimiento.
4. Solo si la auditoría pasa, preregistrar una prueba sin ML: datos/hash, calendario,
   disponibilidad, baseline, controles, costes, reglas de exclusión y gates exactos.
5. Si la regla incumple los gates económicos, cerrar esa formulación; no ajustar
   retrospectivamente el signo, umbral o horizonte. Un resultado favorable en
   folds reutilizados seguirá siendo desarrollo, nunca confirmación independiente.

El test 2025–2026 permanece reservado. No usar 2024 para elegir la hipótesis,
ni las capturas de calidad recientes como un supuesto holdout de rendimiento.

**Siguiente tarea concreta:** auditoría pequeña de Wikimedia sobre datos de
desarrollo, sin unir precios ni entrenar modelos. La evidencia temporal puede
descartar esta candidata antes de gastar una nueva iteración.
