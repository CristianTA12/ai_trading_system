# Agregación prospectiva 15m/1h — 2026-10-14

Implementada en `src/data/collectors/aggregate_prospective.py`. No entrena
modelos, genera señales ni inicia conexiones. Usa los mensajes de una sola
sesión en orden de recepción y el replay `closed_asof` del collector.

## Contrato

- Una decisión solo ve versiones cerradas recibidas **estrictamente antes**
  de su timestamp local. La igualdad todavía no permite usar el mensaje.
- Ventanas alineadas a UTC: cuartos de hora y horas naturales, no ventanas
  móviles. Se requieren 15 minutos distintos consecutivos por cuarto y cuatro
  cuartos consecutivos por hora. Los huecos y extremos parciales se omiten.
- Open del primer minuto, close del último, máximo high, mínimo low; suma
  de volumen base/cotizado, compras taker base/cotizadas y número de trades.
  Cantidades decimales conservadas como cadenas, cálculo con Decimal.
- Cada resultado guarda las secuencias, aperturas y recepciones de los minutos
  originales. `available_at_ns` es la recepción más tardía de la versión
  seleccionada de sus componentes; no es una certificación de UTC absoluto.
- Revisiones y duplicados reemplazan la versión seleccionada de un minuto,
  nunca suman ese minuto otra vez. Consultar una decisión anterior conserva
  el conocimiento de entonces. Los mensajes raw permanecen intactos.

La incertidumbre del reloj se conserva. Un salto hacia atrás puede comprometer
la interpretación del tiempo de pared; este módulo no repara relojes ni une
sesiones de equipos diferentes. El diagnóstico del collector sigue siendo
necesario para interpretar la calidad temporal de una sesión.

## Uso sobre una sesión cerrada

```powershell
python -m src.data.collectors.aggregate_prospective data/prospective/pilot-20261013-kline-1m
```

Primero verifica integridad y replay de la captura; después imprime JSON
derivado, con ID de sesión y hash del manifiesto de origen. Por defecto usa
la decisión al final de la sesión; `--decision-ns` admite una decisión dentro
del intervalo registrado. No escribe dentro de la captura ni modifica raw.
En Python: `aggregate_asof(records, decision_ns)` devuelve mapas `15m` y `1h`
indexados por apertura UTC epoch en milisegundos.

## Validación y alcance

Cinco pruebas nuevas cubren OHLC y los cuatro volúmenes, trazabilidad,
fronteras de recepción, cierre tardío, revisiones, duplicados, huecos, mensajes
abiertos/inválidos, extremos parciales y alineación UTC. Las pruebas usan datos
sintéticos declarados, sin consultar el test histórico reservado.
Suite completa: **263 tests pasados y dos omitidos**. Ruff y formato correctos.

El piloto real de diez minutos tiene diez cierres: es insuficiente para
producir una barra completa de 15m o 1h. El resultado esperado sobre ese piloto
es ambos mapas vacíos; no se completan con datos históricos ni inventados.
La validación de una hora completa en vivo queda pendiente de una captura
de duración suficiente. Esto no es evidencia de rentabilidad ni estabilidad 24/7.
