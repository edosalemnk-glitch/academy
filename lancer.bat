@echo off
rem Lance INPP Academie sous Windows (double-clic).
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py -3) else (set PY=python)
if not exist ".venv\Scripts\python.exe" (
  echo Creation de l'environnement Python...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo.
    echo ECHEC : Python est absent ou casse sur cet ordinateur.
    echo Lisez le fichier ACTIONS.md, etape 1, pour le reinstaller.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
  echo ECHEC de l'installation de Flask. Verifiez la connexion Internet.
  pause
  exit /b 1
)
echo.
echo INPP Academie demarre. Ouvrez http://127.0.0.1:5000 dans le navigateur.
echo Pour arreter : Ctrl + C dans cette fenetre.
echo.
".venv\Scripts\python.exe" app.py
pause
