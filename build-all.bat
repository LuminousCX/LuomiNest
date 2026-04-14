@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo  LuomiNest All-in-One Build Script
echo ========================================
echo.

set PROJECT_ROOT=%~dp0
set FRONTEND_DIR=%PROJECT_ROOT%frontend
set BACKEND_DIR=%PROJECT_ROOT%backend
set DIST_DIR=%PROJECT_ROOT%dist

echo [Step 1/5] Building backend...
cd /d "%BACKEND_DIR%"
call build.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Backend build failed
    exit /b 1
)

echo.
echo [Step 2/5] Creating distribution directory...
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if exist "%DIST_DIR%\backend" rmdir /s /q "%DIST_DIR%\backend"
mkdir "%DIST_DIR%\backend"

echo.
echo [Step 3/5] Copying backend to distribution...
copy "%BACKEND_DIR%\dist\luominest-backend.exe" "%DIST_DIR%\backend\" /Y
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to copy backend executable
    exit /b 1
)

echo.
echo [Step 4/5] Building frontend with embedded backend...
cd /d "%FRONTEND_DIR%"

if not exist "resources\backend" mkdir "resources\backend"
copy "%DIST_DIR%\backend\luominest-backend.exe" "resources\backend\" /Y

call pnpm run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend build failed
    exit /b 1
)

echo.
echo [Step 5/5] Creating installer...
call pnpm run build:installer
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Installer creation failed
    exit /b 1
)

echo.
echo ========================================
echo  All-in-One build completed!
echo  Installer: %FRONTEND_DIR%\release\
echo ========================================

cd /d "%PROJECT_ROOT%"
endlocal
