# Collector prospectivo acotado

Fecha: 2026-10-13. Implementación del [plan](prospective-data-plan.md).
Solo datos públicos BTCUSDT spot `kline_1m`; sin claves, órdenes ni modelos.
El [piloto real del 13 de octubre](prospective-pilot-results.md) terminó y está verificado.

## Ejecutar y detener

Desde la raíz, usando Python con `websockets>=15`:

```powershell
python -m src.data.collectors.prospective --output data/prospective/nueva-sesion --seconds 600 --max-bytes 50000000
```

El directorio debe ser nuevo. Máximo 600 segundos de ventana de captura,
50.000.000 bytes totales y tres intentos de conexión. Reserva espacio para
eventos y cierre; un mensaje que no cabe se omite explícitamente en el log
y detiene la sesión. El cierre del socket puede requerir unos segundos
adicionales; la elaboración del informe sucede después de parar recepción.
Los archivos raw rotan cada 4 MB aproximadamente (sin dividir un registro).
Ctrl+C solicita cancelación limpia con informe y manifiesto; un apagado
brusco del proceso/equipo puede dejar una sesión incompleta, que no debe
presentarse como verificada. No se instala servicio ni arranque automático.

La implementación usa el [stream oficial de mercado](https://raw.githubusercontent.com/binance/binance-spot-api-docs/master/web-socket-streams.md).
El cliente responde ping/pong; se registran desconexiones. Tras un fallo
se reintenta con espera acotada dentro del presupuesto temporal. Sin mensajes
o al agotar intentos, el comando devuelve código 2 y deja evidencia del fallo.
No se usa REST para ocultar huecos ni se sustituye el stream por datos sintéticos.

## Archivos y disponibilidad

- `session.json`: sesión, configuración, versiones, commit, hash del collector,
  estado de reloj y, en Windows, resultado raw de `w32tm /query /status` en base64.
- `messages-*.jsonl`: payload original de cada mensaje, secuencia local,
  UTC en nanosegundos, reloj monotónico, unidad del proveedor y codificación.
- `events-*.jsonl`: conexiones, errores por tipo, desconexiones y parada.
- `report.json`: cobertura, duplicados, revisiones, errores y diferencias temporales.
- `manifest.json`: SHA256 de los archivos cerrados. No añadir archivos dentro
  de la sesión después; informes externos se guardan en otra carpeta.

El timestamp local se toma al retornar `recv()`, antes de parsear el payload.
Es recepción en la aplicación, no timestamp de llegada del paquete al kernel;
incluye posibles colas del cliente. El parseo exige UTC epoch en milisegundos,
velas de un minuto, campos numéricos finitos y volúmenes taker válidos.
Mensajes inválidos y binarios siguen conservándose, aunque no alimenten el replay.

`closed_asof(records, decision_ns)` conserva la última versión cerrada recibida
**estrictamente antes** de la decisión, por minuto. Un cierre tardío o una
revisión no modifica lo conocido en decisiones anteriores. Esta versión
expone cierres por minuto: no implementa todavía el agregador prospectivo 15m/1h.

La cobertura compara los minutos completos dentro de la ventana del reloj
local con cierres disponibles al final. No confundirla con tiempo de conexión
ni con cobertura de todos los mensajes del exchange, que el stream no permite
demostrar. La primera/última vela parcial se excluye del denominador, aunque
pueda existir un cierre recibido para ella. Un reloj desplazado también
puede sesgar esta métrica; conservar siempre el diagnóstico del reloj.

## Qué comprueba el informe

Duplicados de payload exacto, cambios entre versiones cerradas de la misma
vela, mensajes inválidos, cierres ausentes y saltos del reloj de pared respecto
al monotónico superiores a un segundo entre recepciones. No detectar saltos
no demuestra sincronización ni ausencia de deriva lenta.

Las diferencias evento→recepción y cierre→recepción se conservan como
diagnóstico, con sincronización marcada desconocida. No son latencia pura
de red. La evidencia raw del servicio de hora debe revisarse aparte; esta
versión no modifica el reloj ni interpreta automáticamente su salida localizada.

```powershell
python -m src.data.collectors.verify_prospective data/prospective/nueva-sesion
```

El verificador comprueba archivos, hashes, límites, secuencias, conexiones
cerradas y replay causal en fronteras de recepción, mediante un recorrido
inverso independiente del replay principal. El parseo y el cálculo de métricas
son compartidos. Las pruebas sintéticas cubren también revisiones y retrasos
que pueden no producirse en un piloto breve.

La prueba completa previa pasó 258 tests y omitió dos de integración; los
ocho tests del collector volvieron a pasar tras los ajustes finales. El piloto
solo valida este mecanismo, no estabilidad 24/7, latencia absoluta, rentabilidad
ni supuestos históricos de las iteraciones anteriores.
