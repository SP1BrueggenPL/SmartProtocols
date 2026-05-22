@echo off
title IT Protokoly - Brueggen Polska
echo ======================================
echo  IT Protokoly - Brueggen Polska
echo ======================================
echo.
echo Instalowanie zaleznosci...
pip install -r requirements.txt -q
echo.
echo Uruchamianie serwera...
echo Aplikacja dostepna pod adresem: http://localhost:5000
echo Domyslny login: admin / admin123
echo.
echo Nacisnij Ctrl+C aby zatrzymac serwer.
echo.
cd /d "%~dp0\app"
python app.py
pause
