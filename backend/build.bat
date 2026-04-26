@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo  LuomiNest Backend Build Script
echo ========================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH
    exit /b 1
)

echo [1/4] Checking Python version...
python --version

echo.
echo [2/4] Creating virtual environment...
if not exist ".venv" (
    python -m pip install --upgrade pip
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
)

echo.
echo [3/4] Installing dependencies...
call .venv\Scripts\activate.bat
pip install --upgrade pip
pip install pyinstaller
pip install -e ".[dev]"

echo.
echo [4/4] Building executable with PyInstaller...
pyinstaller luominest-backend.spec --clean --noconfirm

if %ERRORLEVEL% neq 0 (
    echo [ERROR] PyInstaller build failed
    exit /b 1
)

echo.
echo ========================================
echo  Build completed successfully!
echo  Output: dist\luominest-backend.exe
echo ========================================

endlocal
