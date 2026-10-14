# Comprobación del reloj — 2026-10-14

## Resultado observado

El collector sigue detenido. `W32Time` está en ejecución y configurado como
automático, pero `w32tm /query /status` informa indicador de salto 3
(sin sincronizar), estrato 0, origen `Local CMOS Clock` y ninguna última
sincronización correcta registrada. El peer configurado es `time.windows.com,0x9`.

Se intentó `w32tm /resync /rediscover` sin cambiar servidor, registro ni
políticas. Windows devolvió **Acceso denegado (0x80070005)**, también en la
ejecución ampliada disponible al agente. No fue un rechazo de la revisión
automática de permisos: el proceso no dispone de los privilegios administrativos
de Windows necesarios. No se elevó mediante UAC ni se cambió el reloj.

La comprobación independiente, de solo lectura:

```powershell
w32tm /stripchart /computer:time.windows.com /samples:3 /period:2 /dataonly
```

obtuvo tres respuestas: `-0.4209222s`, `-0.4195593s`, `-0.4186029s`.
El servidor respondió desde `51.145.123.29`. Es un desfase estimado de unos
420 ms respecto a esa fuente en ese momento, no una cota certificada del error
UTC ni una medición aplicable al piloto del día anterior. Tampoco demuestra
que el servicio W32Time pueda sincronizar: stripchart y el servicio pueden
usar puertos de origen diferentes.

## Corrección pendiente en Windows

Abrir PowerShell **como administrador**, con las capturas detenidas, y ejecutar:

```powershell
w32tm /resync /rediscover
w32tm /query /status
w32tm /query /source
w32tm /query /peers
w32tm /stripchart /computer:time.windows.com /samples:5 /period:2 /dataonly
```

Conservar las salidas. Una solicitud de resincronización aceptada no basta:
comprobar una última sincronización correcta reciente, fuente externa válida,
estado sin alarma de falta de sincronización y muestras de desfase. Si falla,
diagnosticar ese error antes de cambiar servidores o políticas. No desactivar
firewall ni modificar configuraciones corporativas como solución genérica.

Referencia: [herramientas y configuración del servicio de hora de Microsoft](https://learn.microsoft.com/en-us/windows-server/networking/windows-time-service/windows-time-service-tools-and-settings).

## Continuación del proyecto

No iniciar aún la campaña prolongada. Tras resolver el reloj, conservar su
estado antes y después de una nueva captura acotada, junto a las mediciones
de desfase; reportar los límites de precisión observados. No corregir los
timestamps raw del piloto anterior ni reinterpretar sus diferencias de tiempo
como latencia de red. La agregación causal 15m/1h puede desarrollarse con
pruebas sintéticas mientras se resuelve esta dependencia del equipo.
