@echo off
chcp 65001 >nul
echo ========================================
echo   LuomiNest Inno Setup Build Script
echo ========================================
echo.

echo [1/3] Setting up mirror acceleration...
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/

echo [2/3] Building application...
call pnpm run build
if %errorlevel% neq 0 (
    echo Build failed!
    pause
    exit /b 1
)

echo [3/3] Packing files...
call pnpm exec electron-builder --win --dir
if %errorlevel% neq 0 (
    echo Pack failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Creating Inno Setup installer...
iscc installer.iss
if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo   Inno Setup not found!
    echo ========================================
    echo.
    echo Please install Inno Setup 6 from:
    echo https://jrsoftware.org/isdl.php
    echo.
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build Success!
echo ========================================
echo.
echo Installer: release\installer\LuomiNest-Setup-0.2.0.exe
echo Portable:  release\dist\LuomiNest 0.2.0.exe
echo.

pause
