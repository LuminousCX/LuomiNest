@echo off
chcp 65001 >nul
echo ========================================
echo   LuomiNest 打包脚本
echo ========================================
echo.

echo [1/3] 设置镜像加速...
set ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
set ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/

echo [2/3] 开始构建...
call npm run build:win

if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo   打包成功！
    echo ========================================
    echo.
    echo 安装包位置: release\dist\
    echo   - NSIS安装包: LuomiNest Setup 1.0.0.exe
    echo   - 便携版: LuomiNest 1.0.0.exe
    echo.
) else (
    echo.
    echo ========================================
    echo   打包失败，请检查错误信息
    echo ========================================
    echo.
)

pause
