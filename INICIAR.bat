@echo off
title ContaEscola v6
color 0A
echo ============================================
echo   ContaEscola v6.0 - Arquitectura modular
echo ============================================
echo.
echo Instalando dependencias...
pip install streamlit pandas plotly xlsxwriter reportlab --quiet
echo.
echo Arrancando...
streamlit run app.py --server.port 8501 --browser.gatherUsageStats false
pause
