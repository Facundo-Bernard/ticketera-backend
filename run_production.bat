@echo off
title Ticketera Backend (Produccion)
cd /d %~dp0
echo ==========================================
echo   Iniciando Ticketera Backend en Produccion
echo   Host: 127.0.0.1 | Puerto: 8000
echo   Proxy Headers activados para IIS / ARR
echo ==========================================
venv\Scripts\uvicorn.exe src.main:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips=*
pause
