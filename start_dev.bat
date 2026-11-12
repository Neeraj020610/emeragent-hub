@echo off
echo ===================================================
echo   Emergent Central Hub - Development Servers
echo ===================================================
echo.
echo Starting Backend on http://localhost:8000 ...
start "Emergent Central Hub - Backend (Port 8000)" cmd /k "cd /d %~dp0backend && set PYTHONPATH=. && .\.venv\Scripts\uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo Starting Frontend on http://localhost:3000 ...
start "Emergent Central Hub - Frontend (Port 3000)" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Both servers have been launched in separate terminal windows:
echo - Backend API & Docs: http://localhost:8000/docs
echo - Frontend Dashboard: http://localhost:3000
echo.
pause

