@echo off
title Encerrando Analista Financeiro
echo Procurando processos Streamlit na porta 8501...
echo.

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8501 ^| findstr LISTENING') do (
    echo Matando PID %%a
    taskkill /F /PID %%a 2>nul
)

echo.
echo Encerrado.
timeout /t 2 >nul
