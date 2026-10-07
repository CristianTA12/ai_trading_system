#!/usr/bin/env bash
# Ejecutar en Ubuntu WSL: bash scripts/deploy-wsl.sh
# --setup reinstala dependencias; --services-only omite la preparación Python.
set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
VENV=${TRADING_VENV:-"$HOME/.venvs/ai-trading-system"}
WAIT_SECONDS=${DEPLOY_TIMEOUT:-600}
SETUP=0
SERVICES_ONLY=0

log() { printf '\n[deploy] %s\n' "$*"; }
fail() { printf '\n[deploy] ERROR: %s\n' "$*" >&2; exit 1; }
usage() {
    cat <<'HELP'
Uso desde Ubuntu WSL:
  bash scripts/deploy-wsl.sh                  Arranque y entorno Python
  bash scripts/deploy-wsl.sh --setup          Instalar/actualizar dependencias
  bash scripts/deploy-wsl.sh --services-only  Solo infraestructura Docker

Variables opcionales:
  TRADING_VENV    Entorno virtual (por defecto ~/.venvs/ai-trading-system)
  DEPLOY_TIMEOUT Espera por fase, en segundos (por defecto 600, adecuado para HDD)

Requisitos: Ubuntu WSL2, Docker Desktop con integración WSL y soporte GPU NVIDIA.
Puede iniciar Docker Desktop instalado en su ubicación estándar de Windows.
En una instalación nueva instala paquetes Ubuntu (sudo) y dependencias Python.
Conserva .env y los volúmenes. No descarga históricos/modelos ni ejecuta trading.
HELP
}
for arg in "$@"; do
    case "$arg" in
        --setup) SETUP=1 ;;
        --services-only) SERVICES_ONLY=1 ;;
        -h|--help) usage; exit 0 ;;
        *) fail "Opción desconocida: $arg. Usa --help." ;;
    esac
done
[[ "$WAIT_SECONDS" =~ ^[1-9][0-9]*$ ]] || fail 'DEPLOY_TIMEOUT debe ser un entero positivo.'
(( SETUP == 0 || SERVICES_ONLY == 0 )) || fail '--setup y --services-only son excluyentes.'
grep -qi microsoft /proc/sys/kernel/osrelease || fail 'Ejecuta este script dentro de Ubuntu WSL2.'
[[ "$EUID" -ne 0 ]] || fail 'Ejecuta como tu usuario WSL, sin sudo; se solicitará sudo solo si hace falta.'
cd -- "$ROOT"
trap 'printf "\n[deploy] Fallo en línea %s. No se han eliminado datos.\n" "$LINENO" >&2' ERR

# No instalar un segundo Docker Engine dentro de Ubuntu.
if ! command -v docker >/dev/null || ! timeout 15 docker version --format '{{.Server.Os}}' >/dev/null 2>&1; then
    log 'Iniciando Docker Desktop y esperando su motor Linux…'
    POWERSHELL=$(command -v powershell.exe || true)
    if [[ -z "$POWERSHELL" ]]; then
        POWERSHELL=/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
    fi
    [[ -x "$POWERSHELL" ]] || fail 'No encuentro PowerShell. Abre Docker Desktop y activa la integración con Ubuntu.'
    "$POWERSHELL" -NoProfile -NonInteractive -Command \
        '$ErrorActionPreference="Stop"; $app=Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"; if (!(Test-Path -LiteralPath $app)) {throw "Docker Desktop no instalado"}; if (!(Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)) {Start-Process -FilePath $app -WindowStyle Hidden}'
    deadline=$((SECONDS + WAIT_SECONDS))
    until command -v docker >/dev/null && timeout 15 docker version --format '{{.Server.Os}}' >/dev/null 2>&1; do
        (( SECONDS < deadline )) || fail 'Docker no responde. Comprueba motor Linux e integración WSL en Docker Desktop.'
        sleep 5
    done
fi
[[ $(docker version --format '{{.Server.Os}}') == linux ]] || fail 'Docker debe usar contenedores Linux.'
docker compose version >/dev/null || fail 'Hace falta Docker Compose v2 en la integración WSL.'

# Configuración nueva solo si no hay datos anteriores que requieran credenciales.
if [[ ! -f .env ]]; then
    if [[ -n $(docker ps -a --filter name=trading-timescaledb --format '{{.ID}}') ]] ||
       [[ -n $(docker volume ls --filter name=timescaledb-data --format '{{.Name}}') ]]; then
        fail 'Falta .env pero hay una base de datos previa. Restaura su .env para conservar las credenciales.'
    fi
    command -v python3 >/dev/null || fail 'Instala python3 en Ubuntu antes del primer despliegue.'
    log 'Creando .env local con contraseñas aleatorias para la instalación nueva.'
    python3 - <<'PY'
from pathlib import Path
import os
import secrets

text = Path('.env.example').read_text(encoding='utf-8')
for placeholder in ('CHANGE_ME_secure_password', 'CHANGE_ME_grafana_password',
                    'CHANGE_ME_grafana_reader_password'):
    text = text.replace(placeholder, secrets.token_hex(24))
text = text.replace('LOG_DIR=/data/logs', 'LOG_DIR=./logs')
text += '\nCOMPOSE_FILE=docker-compose.yml:docker-compose.wsl.yml\n'
fd = os.open('.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, 'w', encoding='utf-8') as stream:
    stream.write(text)
PY
fi

# Selección explícita: no afecta al Compose de Ubuntu nativo ni depende del cwd.
COMPOSE=(docker compose --project-directory "$ROOT" --env-file "$ROOT/.env"
    -f "$ROOT/docker-compose.yml" -f "$ROOT/docker-compose.wsl.yml")
"${COMPOSE[@]}" config --quiet
log 'Levantando TimescaleDB, Redis, MLflow, Grafana, Ollama y Prometheus…'
"${COMPOSE[@]}" up -d --wait --wait-timeout "$WAIT_SECONDS"

if (( SERVICES_ONLY == 0 )); then
    if [[ ! -x "$VENV/bin/python" ]] || (( SETUP )); then
        packages=()
        for package in python3-venv python3-pip make build-essential libgomp1; do
            if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
                packages+=("$package")
            fi
        done
        if (( ${#packages[@]} )); then
            log 'Instalando prerrequisitos Ubuntu…'
            sudo apt-get update
            sudo apt-get install -y "${packages[@]}"
        fi
        python3 -c 'import sys; assert sys.version_info >= (3, 11), "Se requiere Python 3.11+"'
        [[ -x "$VENV/bin/python" ]] || python3 -m venv "$VENV"
        log "Instalando dependencias en $VENV (la primera vez puede tardar)…"
        "$VENV/bin/python" -m pip install -e '.[dev]'
        "$VENV/bin/python" -m pre_commit install
    fi
    log 'Comprobando entorno Python y acceso al proyecto…'
    "$VENV/bin/python" -c 'import src, pandas, xgboost, mlflow, psycopg2, dotenv; import sys; assert sys.version_info >= (3, 11)'
    # Crea/actualiza el lector en bases nuevas y existentes, usando el .env local.
    "$VENV/bin/python" -m src.monitoring.setup_dashboard
fi

# up --wait comprueba DB/Redis; estos servicios HTTP no tienen healthcheck Compose.
command -v python3 >/dev/null || fail 'Se necesita python3 para verificar los servicios HTTP.'
log 'Esperando respuestas HTTP de los servicios…'
python3 - "$WAIT_SECONDS" <<'PY'
import sys
import time
import urllib.request

pending = {
    'Grafana': 'http://localhost:3000/api/health',
    'MLflow': 'http://localhost:5000/health',
    'Prometheus': 'http://localhost:9090/-/ready',
    'Ollama': 'http://localhost:11434/api/version',
}
deadline = time.monotonic() + int(sys.argv[1])
while pending and time.monotonic() < deadline:
    for name, url in list(pending.items()):
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if response.status == 200:
                    print(f'  {name}: OK', flush=True)
                    del pending[name]
        except (OSError, TimeoutError):
            pass
    if pending:
        time.sleep(3)
if pending:
    raise SystemExit('No responden: ' + ', '.join(pending) + '. Consulta docker compose logs.')
PY
"${COMPOSE[@]}" ps
log 'Entorno listo.'
printf 'Grafana: http://localhost:3000\nMLflow: http://localhost:5000\nPrometheus: http://localhost:9090\nOllama: http://localhost:11434\n'
if (( SERVICES_ONLY == 0 )); then
    printf '\nPara continuar en tu terminal:\n  cd %q\n  source %q\n' "$ROOT" "$VENV/bin/activate"
fi
