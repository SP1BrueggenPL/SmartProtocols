@echo off
title IT Protokoly (Django) - Brueggen Polska
echo ============================================
echo  IT Protokoly - Brueggen Polska (Django)
echo ============================================
echo.
echo Instalowanie zaleznosci...
pip install -r django_app\requirements.txt -q
echo.
cd /d "%~dp0\django_app"
echo Konfiguracja bazy danych...
python manage.py migrate
python init_data.py
echo.
echo Uruchamianie serwera Django...
echo Aplikacja dostepna pod adresem: http://localhost:8000
echo Domyslny login: admin / admin123
echo.
echo Nacisnij Ctrl+C aby zatrzymac serwer.
echo.
python manage.py runserver 0.0.0.0:8000
pause
