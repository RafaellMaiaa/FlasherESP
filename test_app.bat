@echo off
cls
echo ================================================
echo   INICIANDO TESTE DA APP ESP FLASHER
echo ================================================
echo.
echo Instalando dependências (primeira vez)...
pip install -q flask flask-socketio eventlet pyserial esptool
echo.
echo ================================================
echo   SERVIDOR INICIANDO EM http://127.0.0.1:5000
echo ================================================
echo.
python run.py
pause
