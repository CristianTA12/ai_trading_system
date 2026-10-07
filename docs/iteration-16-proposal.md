# Propuesta it.16 — Salida por DOWN sobre modelos SP500 4h congelados

Fecha: 2026-10-07. **Propuesta concreta pendiente de preregistro operativo;
no hay resultados ni política alternativa implementada.** Motivación y límites
en la [revisión de arquitectura](architecture-review-post-15.md).

## Una intervención

| Elemento | Control | Candidato |
|---|---|---|
| Modelos y features | 20 modelos SP500 de it.15 | Los mismos, sin reentrenar |
| Entrada estando cash | Gate abierto, argmax UP, p_up≥0,5 | Idéntica |
| Holding mínimo | 240 min | Idéntico |
| Salida tras holding | Desaparece condición de entrada | DOWN es argmax, sin umbral adicional |
| NEUTRAL / UP insuficiente estando long | Sale tras mínimo | Mantiene |
| Gate cerrado/ausente, señal ausente | Cash inmediato | Idéntico, incluso dentro del mínimo |
| Fin de fold | Liquida | Idéntico |

El mínimo no es duración fija ni máxima. DOWN antes de 240 min no queda
pendiente: al alcanzar el mínimo se usa la señal actual. No cooldown;
tras salir se podrá entrar en una barra posterior con señal válida.
Gate reabierto exige nueva entrada; no restaura una posición latente.
Empates de argmax conservan el orden de clases DOWN, NEUTRAL, UP del código.
No entrar por NEUTRAL ni convertir gate abierto en una compra automática.

## Controles y datos

Referencia: `data/experiments/iteration-15-20261007-sp500`, receta `fc84441`,
preregistro it.15 `e02b46e`. Folds 2022 H1/H2, 2023 H1/H2; semillas
42,123,456,789,2026. Mismos timestamps, probabilidades, velas, targets de
clasificación, gate y supuestos SP500 de it.15. Sin leer BTC 2024 o test 2025–2026.

Antes de evaluar: verificar hashes, librerías, 20 modelos recargados y
probabilidades exactas. Reproducir control de it.15 en bruto/base/stress,
incluidos targets/equity/fills/trades. La nueva salida debe recalcular desde
cero la secuencia de posiciones y ejecución; no reutilizar trades del control.
No eliminar señales por falta de outcome futuro. No cambiar las filas comunes.

Capital inicial 10.000 por fold, long/flat 100%, spot sin apalancamiento.
Taker 0,0004 por lado; slippage base 0,0001, stress 0,0002; bruto cero fricción.
120 backtests de los dos brazos más ocho benchmarks B&H/cash base. Puede
haber comprobaciones previas del control adicionales, sin candidatos alternativos.

## Criterio y parada

Mismo `risk-return-v1`, hash
`12398837a044bd1b4519e22c67cf4d8bd68616eb12580d56d6f48dde5fec638a`.
Al menos 4/5 semillas deben cumplir simultáneamente rentabilidad base positiva,
DD≤15% en cada fold y concatenado, consistencia Sharpe/DD frente a B&H en
≥3/4 folds con la excepción cash vigente y compuesto stress positivo.
El control rechazado de it.15 no se promueve por aparecer en esta comparación.

Si falla: cerrar la prueba, sin barrer confianza, holding, umbral DOWN ni
añadir otra variante en esta iteración. Si pasa: resultado exploratorio
condicionado a los supuestos SP500, sin apertura automática del test ni despliegue.
No cambiar B&H por un benchmark de menor exposición para aprobar retrospectivamente.

Además del veredicto, informar por fold/semilla: duración, exposición,
rotación, bruto/neto, DD, días con retorno, causas de salida y Sharpe H1/H2.
Son descriptores, no criterios adicionales para seleccionar resultados.

## Requisitos antes de ejecución

1. Convertir esta propuesta en protocolo operativo congelado y registrar el commit.
2. Implementar política y runner con pruebas de NEUTRAL, UP insuficiente,
   DOWN antes/después de 4h, gate, ausencias, reentrada y liquidación final.
3. Reproducir el control antes de evaluar el candidato.
4. Guardar artifacts en carpeta nueva, MLflow y verificación independiente.

Las salidas observadas motivaron esta propuesta sobre folds ya conocidos:
es investigación adaptativa, no evidencia confirmatoria nueva.
