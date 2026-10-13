# Siguiente etapa técnica — captura prospectiva de calidad

Fecha: 2026-10-13. **Diseño preparado; collector todavía no implementado
ni activado.** Deriva de la [revisión post-it.17](architecture-review-post-17.md).
No es un protocolo de rentabilidad ni una iteración 18.

## Pregunta y alcance mínimo

¿Podemos reconstruir qué cierres BTCUSDT y volúmenes taker estaban realmente
disponibles para una decisión local, conservando entrega tardía y huecos?

Primera versión: solo stream público spot `btcusdt@kline_1m`, sin API key,
sin órdenes, señales de trading, cuenta, balances ni dependencias de funding
o macro. Conservar mensajes recibidos, incluidos estados aún no cerrados;
solo eventos con cierre confirmado pueden alimentar agregados de investigación.
No capturar todavía todos los aggTrades ni un libro de órdenes completo.

La [documentación oficial de Binance](https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/web-socket-streams.md)
ofrece un endpoint exclusivo de datos de mercado y describe `E` (evento),
`k.t`/`k.T` (barra), `k.x` (cierre), `v`/`q` (volumen) y `V`/`Q` (compras
taker). Las conexiones requieren gestión de ping/pong y reconexión; no se
puede suponer una conexión perpetua. Revisar el contrato al implementar.

## Evidencia a conservar

Cada recepción guarda payload original y un sobre local con:

- ID de sesión, contador local, versión del collector y configuración.
- Timestamp UTC local de recepción, antes de parsear el mensaje.
- Reloj monotónico local y unidad temporal explícita del proveedor.
- Hora del evento, apertura/cierre de barra, símbolo y estado de cierre.

Guardar por separado eventos de conexión, desconexión, excepciones y cierre
de sesión. Archivos nuevos por sesión, manifiesto SHA256 y rotación acotada.
Nunca sobrescribir raw; un mensaje corregido o duplicado conserva su lugar
en la secuencia de recepción. La vista deduplicada es un producto derivado.

`received_at−event_time` es una diferencia de relojes más transporte y
procesamiento, no una medida pura de latencia de red. Registrar estado de
sincronización/desfase del reloj cuando pueda obtenerse; si no, marcarlo
desconocido y limitar las conclusiones. No corregir timestamps raw a posteriori.

## Reconstrucción causal

Un replay de disponibilidad solo utiliza mensajes cuyo `received_at` sea
estrictamente anterior a la decisión. Un cierre tardío no se inserta
retroactivamente como si hubiera llegado a tiempo. Para 15m se requieren
los quince minutos cerrados observados; para una hora, cuatro agregados
consecutivos. Mantener el rastro de revisiones y sus tiempos de recepción.

Si se añade recuperación REST en una versión posterior, marcarla como
backfill con su recepción real y no mezclarla con observaciones en vivo.
Una interrupción de captura no equivale a un mercado sin operaciones.

## Entrega y verificación previstas

1. Implementar grabación con duración máxima, límite de bytes y cancelación
   limpia. Sin servicio persistente ni arranque automático por defecto.
2. Pruebas sintéticas de cierre, unidades, payload inválido, duplicados,
   revisión, retraso, orden de recepción, desconexión y límites de recursos.
3. Prueba acotada de diez minutos, máximo 50 MB y sin reintentos ilimitados.
   Reportar fallos de acceso de forma explícita; no sustituir datos en vivo
   por ejemplos sintéticos presentados como captura real.
4. Informe de minutos cubiertos, mensajes inválidos/duplicados, cierres
   tardíos, cambios de reloj y huecos de captura. Un piloto de diez minutos
   valida el mecanismo, no estabilidad 24/7 ni disponibilidad histórica.
5. Con el piloto revisado, definir duración, almacenamiento y supervisión
   de una captura prolongada acorde al equipo que vaya a permanecer encendido.

No fijar una fecha de finalización ni prometer meses de datos sin operar
el proceso durante ese tiempo. La ausencia de infraestructura continua
puede limitar la fase prolongada; no impide preparar y probar el collector.

## Criterio de aceptación técnica

Integridad de todos los archivos, límites respetados, cierre limpio y
reconstrucción que no utilice mensajes antes de recibirlos. Los huecos,
errores y revisiones deben verse en el informe; no se exige ocultarlos
para declarar que el programa funciona. Una captura sin errores pero con
reloj no verificado no acredita latencia absoluta.

Sin training, PnL ni comparación contra B&H en esta etapa. No se toca el
snapshot del test histórico. Los datos nuevos usados para diagnóstico de
calidad no se presentan después como confirmación independiente de una
estrategia diseñada a partir de ellos.
