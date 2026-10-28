@echo off
cd /d "%~dp0"
if not exist .venv (py -3 -m venv .venv)
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt || (echo Dependency installation failed & pause & exit /b 1)
set SEED_DEMO=1
set APP_ENV=development
set COOKIE_SECURE=0
set DATABASE_URL=sqlite:///./sivrce.db
echo.
echo Open http://127.0.0.1:8000 in your browser
echo.
python -m uvicorn server:app --host 127.0.0.1 --port 8000
pause
