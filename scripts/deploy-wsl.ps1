# Windows entry point. All project setup and checks run inside Ubuntu WSL.
[CmdletBinding()]
param(
    [string]$Distro = 'Ubuntu',
    [switch]$Setup,
    [switch]$ServicesOnly,
    [switch]$Help
)
$ErrorActionPreference = 'Stop'
try {
    if ($Help) {
        Write-Host 'Uso: .\deploy.cmd [-Setup | -ServicesOnly] [-Distro Ubuntu]'
        Write-Host 'Sin opciones: arranca Docker, prepara Python si falta y verifica los servicios.'
        Write-Host '-Setup: instala/actualiza las dependencias Python.'
        Write-Host '-ServicesOnly: arranca solamente los seis servicios Docker.'
        exit 0
    }
    if ($Setup -and $ServicesOnly) { throw '-Setup y -ServicesOnly son excluyentes.' }
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        throw 'Instala WSL2 y Ubuntu primero: wsl --install -d Ubuntu. Reinicia Windows si lo solicita.'
    }
    $Distros = @(& wsl.exe --list --quiet) | ForEach-Object { ($_ -replace "`0", '').Trim() }
    if ($LASTEXITCODE -ne 0 -or $Distro -notin $Distros) {
        throw "No se encuentra la distribucion '$Distro'. Instala Ubuntu con wsl --install -d Ubuntu."
    }
    $DockerApp = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $DockerApp)) {
        throw 'Instala Docker Desktop y activa Settings > Resources > WSL Integration para Ubuntu.'
    }
    if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
        Write-Host '[deploy] Iniciando Docker Desktop...'
        Start-Process -FilePath $DockerApp -WindowStyle Hidden
    }
    $RepoPath = Split-Path -Parent $PSScriptRoot
    $LinuxRoot = & wsl.exe -d $Distro --exec wslpath -a ($RepoPath.Replace('\', '/'))
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo convertir la ruta del proyecto a WSL.' }
    $LinuxRoot = ($LinuxRoot -join "`n").Trim()
    $LinuxArgs = @()
    if ($Setup) { $LinuxArgs += '--setup' }
    if ($ServicesOnly) { $LinuxArgs += '--services-only' }
    Write-Host "[deploy] Desplegando en $Distro desde $RepoPath"
    & wsl.exe -d $Distro --exec bash "$LinuxRoot/scripts/deploy-wsl.sh" @LinuxArgs
    if ($LASTEXITCODE -ne 0) { throw "El despliegue WSL termino con codigo $LASTEXITCODE." }
    Write-Host '[deploy] Todo listo. Puedes cerrar esta ventana.'
    exit 0
} catch {
    Write-Host "[deploy] ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
