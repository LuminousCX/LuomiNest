@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo  LuomiNest Backend Build Script v2.0
echo  PyInstaller Executable Generator
echo ========================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH
    echo Please install Python 3.10+ from https://www.python.org/downloads/
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
    python -m pip install --upgrade pip --quiet
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

echo Upgrading pip...
pip install --upgrade pip --quiet

echo Installing PyInstaller...
pip install pyinstaller --quiet

echo Installing project dependencies (development mode)...
pip install -e ".[dev]" --quiet
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Some dependencies may have failed to install
    echo Continuing with build...
)

echo.
echo [4/5] Checking for spec file...
if not exist "luominest-backend.spec" (
    echo [ERROR] luominest-backend.spec file not found!
    echo Please ensure the PyInstaller spec file exists in the backend directory.
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
    echo Please check the error messages above.
    exit /b 1
)

if exist "dist\luominest-backend.exe" (
    for %%A in ("dist\luominest-backend.exe") do set SIZE=%%~zA
    set /a SIZEMB=!SIZE! / 1048576
    echo.
    echo ========================================
    echo  Build completed successfully!
    ========================================
    echo.
    echo Output: dist\luominest-backend.exe
    echo Size: !SIZEMB! MB
    echo.
    echo Next steps:
    echo   1. Run frontend build script to create installer
    echo      cd ..\frontend ^&^& .\build-installer.ps1
    echo   2. Or run global build script
    echo      ..\build-all.bat
) else (
    echo.
    echo [ERROR] Build output not found: dist\luominest-backend.exe
    echo The build may have failed silently. Check the PyInstaller output above.
    exit /b 1
)

endlocal
