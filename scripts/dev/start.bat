@echo off
echo Starting LuomiNest Development Server...
echo.

REM Start backend
echo Starting backend server...
start cmd /k "cd /d %~dp0..\.. && cd backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

REM Wait for backend to start
timeout /t 5 /nobreak >nul

REM Start frontend
echo Starting frontend electron app...
start cmd /k "cd /d %~dp0..\.. && cd frontend && pnpm run dev"

echo.
echo LuomiNest started successfully!
echo Backend: http://127.0.0.1:8000
echo Frontend: http://localhost:5173
echo.
echo Press any key to exit this window...
pause >nul
