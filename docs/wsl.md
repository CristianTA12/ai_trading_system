# Desarrollo en Windows con Ubuntu WSL2

Ejecutar los comandos del proyecto en la terminal **Ubuntu**, con Docker Desktop
iniciado y su integración con Ubuntu activada. Se necesita una GPU NVIDIA
accesible desde WSL para el servicio Ollama del Compose actual.

Comprobar primero el espacio libre de la unidad que aloja los discos virtuales
de Ubuntu y Docker Desktop: tener el repositorio en `D:` no mueve esos discos
fuera de `C:`. Las imágenes y las dependencias de PyTorch/CUDA ocupan varios GB.
Si hace falta, trasladar los discos a una unidad con espacio antes de instalar.

La ubicación del disco de Docker es una configuración local del equipo, no del
repositorio. Se puede mantener Ubuntu y el entorno virtual en el SSD y alojar
Docker en otra unidad. Si esa unidad es un HDD, las operaciones de disco y las
migraciones iniciales pueden tardar más que en el SSD.

## Compatibilidad con Ubuntu nativo

`docker-compose.wsl.yml` es opcional: solo se aplica al seleccionarlo mediante
`COMPOSE_FILE` o `docker compose -f`. En Ubuntu nativo, usar su propio `.env`,
sin la línea `COMPOSE_FILE` de esta guía. El Compose principal conserva los
directorios `${DATA_DIR:-/data}` y la reserva de GPU NVIDIA.

Los directorios de datos deben tener los permisos adecuados para los usuarios
de cada contenedor. La GPU requiere Docker con soporte NVIDIA configurado.
Las correcciones del backend de instalación Python, el driver PostgreSQL de
MLflow y el chequeo de salud de PostgreSQL son comunes a ambos entornos.

Validar la configuración nativa sin arrancar servicios:

```bash
docker compose -f docker-compose.yml config --quiet
```

No copiar `.env`, discos virtuales ni volúmenes entre equipos como parte de un
commit. La validación en WSL no sustituye una prueba de arranque en el servidor
Ubuntu de destino.

## Preparación (una vez)

```bash
sudo apt-get update
sudo apt-get install -y make python3-venv python3-pip build-essential libgomp1
cd /mnt/d/ai_trading_system
cp .env.example .env  # Solo si todavía no existe .env
```

Editar `.env`: asignar contraseñas a PostgreSQL y Grafana, mantener la misma
contraseña en `POSTGRES_PASSWORD` y `DATABASE_URL`, y añadir:

```dotenv
COMPOSE_FILE=docker-compose.yml:docker-compose.wsl.yml
```

Cambiar también `LOG_DIR` a `./logs`. No hacen falta claves de exchange para
levantar la infraestructura. Mantener `TRADING_MODE=paper`.

El Compose adicional sustituye los directorios persistentes de `/data` por
volúmenes administrados por Docker en Linux. `DATA_DIR` no controla estos
volúmenes; la configuración normal de Ubuntu sigue disponible sin el override.

Crear el entorno virtual en el disco Linux para acelerar la instalación:

```bash
python3 -m venv ~/.venvs/ai-trading-system
source ~/.venvs/ai-trading-system/bin/activate
make up
make setup
```

## Siguientes sesiones

```bash
cd /mnt/d/ai_trading_system
source ~/.venvs/ai-trading-system/bin/activate
make up
docker compose ps
make test
```

Servicios accesibles desde Windows:

| Servicio | Dirección |
| --- | --- |
| Grafana | http://localhost:3000 |
| MLflow | http://localhost:5000 |
| Prometheus | http://localhost:9090 |
| Ollama | http://localhost:11434 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

Las credenciales están en `.env`. `make down` detiene los servicios y conserva
los volúmenes; `docker compose down -v` elimina los datos de esos volúmenes.

`make up` arranca seis servicios de infraestructura y `make setup` instala el
paquete Python y el hook de pre-commit en el entorno activo. No descargan un
modelo de Ollama ni arrancan un bot. Para descargar el modelo ligero disponible
en el Makefile, ejecutar `make ollama-pull-light` por separado.

El proyecto contiene comandos CLI pendientes de implementación, incluido paper
trading. `trading status` todavía muestra estados de ejemplo. Los targets de
Prometheus en los puertos 8000 y 9100 necesitan procesos adicionales que este
Compose no inicia.

Para cargar el primer histórico y habilitar su dashboard, seguir la
[guía de ingesta](data-ingestion.md). Incluye el paso `make setup-dashboard`
para crear el usuario de lectura de Grafana en una base de datos existente.
