@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo  LuomiNest Backend Build Script v3.0
echo  PyInstaller Executable Generator
echo ========================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH
    exit /b 1
)

echo [1/5] Checking Python version...
python --version
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to check Python version
    exit /b 1
)

echo.
echo [2/5] Creating virtual environment...
if not exist ".venv" (
    echo Creating new virtual environment...
    python -m venv .venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
    echo Virtual environment created successfully
) else (
    echo Virtual environment already exists
)

echo.
echo [3/5] Activating virtual environment and installing dependencies...
call .venv\Scripts\activate.bat

REM Configure pip mirror for faster downloads in China
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple >nul 2>&1
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn >nul 2>&1

echo Upgrading pip...
python -m pip install --upgrade pip --quiet

echo Installing PyInstaller...
pip install pyinstaller --quiet

echo Installing project dependencies (dev mode)...
REM Retry up to 3 times for network resilience
set RETRY_COUNT=0
:INSTALL_RETRY
pip install -e ".[dev]" --quiet
if %ERRORLEVEL% neq 0 (
    set /a RETRY_COUNT+=1
    if !RETRY_COUNT! lss 3 (
        echo [WARNING] Install attempt !RETRY_COUNT! failed, retrying...
        timeout /t 5 /nobreak >nul
        goto INSTALL_RETRY
    )
    echo [WARNING] Dev dependencies failed after retries, installing base only...
    pip install -e . --quiet
)

echo.
echo [4/5] Checking for spec file...
if not exist "luominest-backend.spec" (
    echo [ERROR] luominest-backend.spec file not found!
    exit /b 1
)
echo Spec file found: luominest-backend.spec

echo.
echo [5/5] Building executable with PyInstaller...
echo This may take a few minutes...

pyinstaller luominest-backend.spec --clean --noconfirm

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] PyInstaller build failed
    exit /b 1
)

if not exist "dist\luominest-backend\luominest-backend.exe" (
    echo.
    echo [ERROR] Build output not found: dist\luominest-backend\luominest-backend.exe
    exit /b 1
)

for %%A in ("dist\luominest-backend\luominest-backend.exe") do set SIZE=%%~zA
set /a SIZEMB=!SIZE! / 1048576

echo.
echo ========================================
echo  Build completed successfully!
echo ========================================
echo.
echo Output: dist\luominest-backend\luominest-backend.exe
echo Size: !SIZEMB! MB
echo.
echo Next steps:
echo   1. Run full build script
echo      cd .. ^&^& .\build-all.ps1
echo   2. Or build frontend only
echo      cd ..\frontend ^&^& pnpm run build:win

endlocal
