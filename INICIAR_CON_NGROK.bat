@echo off
title ContaEscola v6 + ngrok
color 0A
echo Arrancando ContaEscola...
start "ContaEscola" cmd /k "cd /d %~dp0 && streamlit run app.py --server.port 8501 --browser.gatherUsageStats false"
timeout /t 5 /nobreak >nul
echo Arrancando ngrok...
start "ngrok" cmd /k "ngrok http 8501"
echo.
echo Mira a ventana de ngrok para a URL remota
pause
