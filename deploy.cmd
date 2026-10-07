@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy-wsl.ps1" %*
set "DEPLOY_RESULT=%ERRORLEVEL%"
if not "%DEPLOY_RESULT%"=="0" echo Despliegue incompleto. Revisa el error anterior.
echo.
pause
exit /b %DEPLOY_RESULT%
