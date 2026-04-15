@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo ========================================
echo  LuomiNest All-in-One Build Script
echo ========================================
echo.

set PROJECT_ROOT=%~dp0
set FRONTEND_DIR=%PROJECT_ROOT%frontend
set BACKEND_DIR=%PROJECT_ROOT%backend
set DIST_DIR=%PROJECT_ROOT%dist
set BACKEND_EXE=%BACKEND_DIR%\dist\luominest-backend.exe
set RESOURCES_BACKEND=%FRONTEND_DIR%\resources\backend

set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/

echo [Step 1/5] Building backend...
cd /d "%BACKEND_DIR%"
call build.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Backend build failed
    exit /b 1
)

echo.
echo [Step 2/5] Verifying backend and creating distribution directory...
if not exist "%BACKEND_EXE%" (
    echo [ERROR] Backend executable not found: %BACKEND_EXE%
    echo The backend build may have failed. Check the build output above.
    exit /b 1
)
if not exist "%DIST_DIR%" mkdir "%DIST_DIR%"
if exist "%DIST_DIR%\backend" rmdir /s /q "%DIST_DIR%\backend"
mkdir "%DIST_DIR%\backend"

echo.
echo [Step 3/5] Copying backend to distribution...
copy "%BACKEND_EXE%" "%DIST_DIR%\backend\" /Y
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to copy backend executable
    exit /b 1
)

echo.
echo [Step 4/5] Preparing frontend resources and building...
cd /d "%FRONTEND_DIR%"

if not exist "%RESOURCES_BACKEND%" mkdir "%RESOURCES_BACKEND%"
copy "%BACKEND_EXE%" "%RESOURCES_BACKEND%\" /Y
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to copy backend executable to frontend resources
    exit /b 1
)

call pnpm run build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Frontend build failed
    exit /b 1
)

echo.
echo [Step 5/5] Creating installer packages...
call pnpm exec electron-builder --win
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Installer creation failed
    exit /b 1
)

echo.
echo ========================================
echo  All-in-One build completed!
echo  NSIS Installer: %FRONTEND_DIR%\release\dist\
echo  Portable:       %FRONTEND_DIR%\release\dist\
echo ========================================

cd /d "%PROJECT_ROOT%"
endlocal
