@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo ========================================
echo   LuomiNest Build Script
echo ========================================
echo.

set FRONTEND_DIR=%~dp0
set PROJECT_ROOT=%FRONTEND_DIR%..
set BACKEND_DIR=%PROJECT_ROOT%\backend
set BACKEND_EXE=%BACKEND_DIR%\dist\luominest-backend.exe
set RESOURCES_BACKEND=%FRONTEND_DIR%resources\backend

set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/

echo [1/4] Checking backend executable...
if not exist "%BACKEND_EXE%" (
    echo [1/4] Backend not found, building backend...
    cd /d "%BACKEND_DIR%"
    call build.bat
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Backend build failed
        exit /b 1
    )
) else (
    echo [1/4] Backend executable found
)

echo.
echo [2/4] Preparing backend resources...
if not exist "%RESOURCES_BACKEND%" mkdir "%RESOURCES_BACKEND%"
copy /Y "%BACKEND_EXE%" "%RESOURCES_BACKEND%\" >nul
echo [2/4] Backend resources ready

echo.
echo [3/4] Building frontend...
cd /d "%FRONTEND_DIR%"
call pnpm run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend build failed
    pause
    exit /b 1
)
echo [3/4] Frontend build complete

echo.
echo [4/4] Creating installer packages...
call pnpm exec electron-builder --win
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Package creation failed
    pause
    exit /b 1
)

echo.
echo ========================================
echo   BUILD SUCCESS!
echo ========================================
echo.
echo Output files:
echo   - NSIS Installer: release\dist\LuomiNest-Setup-0.2.0.exe
echo   - Portable:       release\dist\LuomiNest-Portable-0.2.0.exe
echo.

pause
