# Captura por sesiones manuales — 2026-10-16

El usuario confirma que este PC solo estará disponible mientras lo utiliza.
Se adopta captura intermitente, sin servicio persistente, arranque automático,
cambios de energía ni exigencia de mantener el equipo encendido 24 horas.
Los pilotos técnicos están cerrados; no hace falta repetirlos por rutina.

## Inicio y parada

El collector v3 conserva el valor por defecto de diez minutos y permite
sesiones de hasta 7.500 segundos (2 h 5 min), con máximo 50 MB y tres intentos.
Cada sesión utiliza carpeta y marcador de parada nuevos. Ejemplo desde la raíz:

```powershell
$sessionName = Get-Date -Format 'yyyyMMdd-HHmmss'
$captureFolder = "data/prospective/manual-$sessionName"
$stopMarker = "logs/manual-$sessionName.stop"
Write-Output "Sesion: $captureFolder; marcador de parada: $stopMarker"
python -m src.data.collectors.prospective --output $captureFolder --seconds 3600 --stop-file $stopMarker
```

El comando anterior ocupa esa consola. Para detener antes de una hora, crear
el marcador desde otra consola, sustituyendo el identificador por el mostrado
en la primera (puede consultarse en `session.json`, campo `stop_file`):

```powershell
New-Item -ItemType File -Path 'logs/manual-IDENTIFICADOR.stop'
```

El collector detecta el marcador, deja de recibir y cierra socket, informe y
manifiesto con motivo `user_stop`. Puede tardar en detectarlo mientras espera
conexión o mensajes (timeouts de 15 segundos), más el cierre e informe.
Esperar a que termine y exista `report.json` antes de apagar o suspender.
También sigue disponible Ctrl+C para cancelación limpia desde la consola.
Cerrar forzosamente la ventana/proceso o apagar el equipo no garantiza cierre.

El marcador debe estar fuera de la carpeta de captura. Si ya existe, el
collector rechaza el arranque sin crear la sesión: no se borra ni se reutiliza
automáticamente. Se conserva como evidencia de la solicitud.

Después de una parada limpia:

```powershell
python -m src.data.collectors.verify_prospective data/prospective/manual-IDENTIFICADOR
python -m src.data.collectors.aggregate_prospective data/prospective/manual-IDENTIFICADOR
```

Una sesión de 60 minutos iniciada fuera de la hora exacta puede no contener
ninguna hora UTC completa; no es un error. Se conservan sus minutos y los
cuartos completos disponibles. No unir sesiones para ocultar huecos.

## Presupuesto y lectura de resultados

El piloto horario usó unos 1,69 MB en 97 minutos: orientativamente, alrededor
de 1 MB/h con aquella actividad. No es una garantía de tamaño futuro; permanece
el límite duro de 50 MB por sesión. No hay borrado automático. Antes de ampliar
la colección se debe revisar espacio y decidir qué sesiones conservar.

La cobertura entre sesiones será discontinua y seleccionada por los horarios
de uso del PC. No representa una muestra continua ni un holdout de rendimiento.
La incertidumbre del reloj se registra y no bloquea la captura; sigue limitando
afirmaciones de latencia absoluta. No hay entrenamiento, trading ni evaluación
del test histórico reservado en este flujo.

Pruebas: parada mediante marcador conserva un cierre verificable; marcadores
preexistentes o dentro de la captura se rechazan. También se mantienen las
pruebas de cancelación, límites, integridad, agregación y planificación horaria.
