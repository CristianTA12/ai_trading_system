# Revisión de alcance tras it.19 — propuesta de investigación de carry

Fecha: 2026-10-28. Revisión documental y de fuentes públicas; cero backtests,
entrenamientos, descargas de precios, acceso a cuentas o datos reservados.

Seguimiento: el usuario autorizó investigar derivados de cobertura. La
[auditoría posterior](carry-data-audit.md) valida una muestra de precios de 2022,
pero no acredita margen/costes históricos y ejecución. No apta todavía para
backtest; la propuesta original de esta ficha se conserva como antecedente.
**Propuesta: auditar la viabilidad de cash-and-carry BTC con futuro de vencimiento.
No hay estrategia aprobada ni cambio efectivo del mandato spot-only.**

## Decisión razonada

Se mantiene cerrado el clasificador BTC spot y sus variantes. La
[revisión diaria](research-reopening-daily-trend.md) también impide presentar
otra ventana de momentum como una hipótesis económica nueva.

Se comparan tres direcciones a nivel de mecanismo y alcance, sin medir retornos:

| Dirección | Qué cambiaría | Evidencia y dificultad | Decisión |
|---|---|---|---|
| Otro algoritmo sobre BTC spot | Representación, manteniendo información y problema | No se ha identificado una limitación concreta que justifique más capacidad | No iniciar |
| Selección entre varias criptomonedas spot | Universo e información relativa entre activos | Existe literatura transversal, pero no acredita una cartera líquida long-only que cumpla nuestro mandato; exige universo histórico sin sesgo de supervivencia | No priorizar ahora |
| Spot comprado + futuro vendido con vencimiento | Fuente de resultado: diferencial entre instrumentos y liquidación contractual | Mecanismo distinto de predecir retornos; exige estudiar costes, capital, márgenes y ejecución de ambas posiciones | Priorizar solo auditoría de viabilidad |

La evidencia transversal de [Liu, Tsyvinski y Wu](https://www.nber.org/papers/w25882)
describe factores de mercado, tamaño y momentum, incluyendo estrategias
long-short. El [trabajo de Cakici et al.](https://doi.org/10.1016/j.irfa.2024.103244)
advierte que sus alphas dependen de activos pequeños, ilíquidos y volátiles.
No trasladamos esos resultados a BTC/ETH ni a una cartera spot invertible.
Para ambos se consultaron los resúmenes indexados del editor; la apertura
directa falló. No se atribuyen detalles metodológicos no leídos.

## Hipótesis económica propuesta

La demanda de exposición apalancada puede sostener un precio de futuros
superior al spot; cubrir el BTC comprado con un futuro vendido permite estudiar
la captura de ese diferencial hasta vencimiento. El [BIS Working Paper 1087,
Crypto carry](https://www.bis.org/publications/working-paper-1087-crypto-carry.pdf)
relaciona la prima con esa demanda y las limitaciones del capital que toma el
lado contrario. También describe riesgo de márgenes y liquidación. Se leyeron
el resumen y las secciones iniciales del PDF; no se replicó su estudio.
Es motivación externa para auditar, no prueba de rentabilidad actual o libre
de riesgo ni de cumplimiento de `risk-return-v1`.

La diferencia con it.11 es sustancial: allí funding era una feature para
pronosticar dirección de spot. Aquí se investigarían dos posiciones cubiertas
y su resultado económico conjunto. No reutilizar los supuestos temporales de
funding como autorización general para otros datos de derivados.

Se prefiere auditar un futuro con vencimiento antes que un perpetuo para
delimitar el mecanismo de liquidación. Los perpetuos no vencen y sus pagos de
funding pueden cambiar de signo; no fijan una ganancia futura en la entrada.
Esto se documenta en las referencias oficiales de [contratos](https://www.binance.com/en/support/faq/detail/360033524991)
y [funding](https://www.binance.com/en/support/faq/detail/360033525031).
No se ha elegido Binance ni se presupone acceso a derivados por el usuario.

## Economía mínima que habría que demostrar

Para un futuro lineal en la misma moneda de valoración, cantidad q de BTC,
compra spot a S0, venta del futuro a F0 y liquidación a un índice IT:

```text
PnL spot al vender = q * (ST - S0)
PnL futuro corto   = q * (F0 - IT)
PnL conjunto      = q * (F0 - S0) + q * (ST - IT) - costes
Retorno capital   = PnL conjunto / capital total comprometido
```

La cancelación perfecta del precio requiere ST=IT, cobertura compatible y
ejecución/solvencia hasta liquidación. En la práctica hay diferencia entre
precio de venta spot e índice, spreads, comisiones y desfases. La fórmula no
se aplica sin adaptación a contratos inversos o collateral en BTC.

El denominador debe incluir spot pagado, garantías y reserva de liquidez.
No presentar rentabilidad sobre margen como rentabilidad del capital total.
No reutilizar la misma unidad de efectivo como reserva y como compra spot.
Una posición cubierta puede necesitar garantías adicionales durante su vida;
la neutralidad direccional no elimina riesgo de liquidez ni de contraparte.

Ejemplo didáctico, sin cotizaciones reales: spot 100, futuro 102, q=1,
coste total supuesto 0,4 y capital total comprometido 150. Si venta spot e
índice coinciden y no hay otros costes, resultado 1,6 y retorno 1,07% sobre
capital, no 2%. El ejemplo no está anualizado ni representa una oportunidad.

## Qué cambia y qué no se puede dar por resuelto

La restricción actual es una posición spot long/flat sin derivados. Estudiar
carry como estrategia ejecutable requeriría ampliar explícitamente ese alcance
a un corto de cobertura, contabilidad de márgenes y dos posiciones simultáneas.
No se propone un corto direccional ni financiar con deuda la compra spot.
Tampoco se describe el par como «sin apalancamiento» solo por ser delta-neutral:
hay que declarar exposición bruta y capital realmente asignado.

El motor actual (`src/backtesting/engine.py`) solo admite targets 0/1 y una
posición spot. No modela margen, liquidación ni compensación de dos instrumentos.
No simular carry sumando retrospectivamente funding o restando dos curvas spot.
Primero demostrar viabilidad de datos y contabilidad; después decidir si merece
un simulador separado. No reescribir ahora el motor validado.

Se conserva el objetivo de rendimiento ajustado por riesgo frente a B&H BTC.
Una prima de carry positiva no garantiza superar ese benchmark. No sustituirlo
por efectivo para aprobar la hipótesis. Un mandato de rentabilidad absoluta
sería otra decisión del usuario, no una consecuencia automática de esta ficha.
`risk-return-v1.yaml` no cambia: determinismo no equivale a aprobar 4/5 semillas,
y una evaluación futura distinta exigiría protocolo explícito, sin reclasificar
las 19 iteraciones. No hay promoción por motivos teóricos.

## Auditoría propuesta: pequeña y con salida concreta

El siguiente trabajo acotado sería una auditoría pública de contrato y datos,
sin curva de rentabilidad ni búsqueda de activos o venues por resultados.
BTC es el único subyacente propuesto. Sin cuentas, claves ni dinero real.

| Comprobación | Evidencia requerida | Condición de parada |
|---|---|---|
| Contrato | Lineal/inverso, multiplicador, moneda, vencimiento, índice y procedimiento de liquidación | No poder reconstruir la cobertura o asumir convergencia a un precio distinto |
| Datos históricos | Contratos individuales, fechas de alta/baja, spot/futuro sincronizados, mark/index y liquidaciones | Solo series continuas ajustadas o ausencia de timestamps defendibles |
| Capital y margen | Reglas iniciales/mantenimiento, cambios históricos y garantías admisibles | Usar reglas actuales como históricas sin fundamento o ignorar llamadas de margen |
| Ejecución | Precios negociables o límites de fills explícitos para ambas posiciones, costes específicos y liquidación | Confundir mid/mark con precio ejecutable o asumir ejecución atómica |
| Recursos | Acceso gratuito suficiente y almacenamiento/operación local viables | Dependencia necesaria de datos de pago o servicio no disponible |
| Evaluación | Receta futura congelable, datos de desarrollo separados y B&H mantenido | Necesidad de mirar el test para escoger parámetros o cambiar benchmark para aprobar |

Las [especificaciones CME](https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/bitcoin/specs)
ejemplifican liquidación financiera y calendario contractual. Su
[página de márgenes](https://www.cmegroup.com/markets/cryptocurrencies/bitcoin/bitcoin/margins)
indica que la descarga requiere cuenta. Son referencias de auditoría, no
selección de venue, acreditación de acceso personal ni constatación de que los
datos históricos completos sean gratuitos. Las reglas actuales no prueban las
reglas de 2022–2023. Esa cobertura sigue sin auditar.

Entregable de esa auditoría: matriz sí/no/desconocido con enlaces, esquema de
datos mínimo y veredicto apto/no apto para diseñar un baseline. Si una pieza
esencial no es defendible, cerrar esta vía sin construir el simulador; no
pasar silenciosamente a perpetuos u otro exchange para rescatarla.

## Estado al terminar esta revisión

Hay una hipótesis diferente con motivación externa; **todavía no hay viabilidad
de implementación ni ventaja demostradas**. Recomendación: discutir la ampliación
a derivados cubiertos y, si encaja con el objetivo, realizar únicamente la
auditoría anterior. No abrir it.20, optimizar estrategias ni entrenar modelos.
La confirmación de acceso operativo personal sería posterior y separada de una
auditoría de documentación pública.

2024 y el test 2025–2026 no se han consultado. Los resultados 2022–2023 conocidos
siguen siendo desarrollo reutilizado. Las fuentes externas se consultaron el
2026-10-28; sus resultados históricos no se tratan como rentabilidad esperable.
