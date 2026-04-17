#!/usr/bin/env bash
set -euo pipefail

UNAME_S="$(uname -s)"
PLATFORM="linux"
if [ "$UNAME_S" = "Darwin" ]; then
    PLATFORM="mac"
fi

echo "========================================"
echo "  LuomiNest Build Script"
echo "  Platform: $PLATFORM"
echo "========================================"
echo ""

FRONTEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$FRONTEND_DIR")"
BACKEND_DIR="$PROJECT_ROOT/backend"
RESOURCES_BACKEND="$FRONTEND_DIR/resources/backend"

if [ "$PLATFORM" = "win" ]; then
    BACKEND_EXE="$BACKEND_DIR/dist/luominest-backend.exe"
else
    BACKEND_EXE="$BACKEND_DIR/dist/luominest-backend"
fi

export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
export ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/"

echo "[1/4] Checking backend executable..."
if [ ! -f "$BACKEND_EXE" ]; then
    echo "[1/4] Backend not found, building backend..."
    cd "$BACKEND_DIR"
    chmod +x build.sh
    bash build.sh
    if [ $? -ne 0 ]; then
        echo "[ERROR] Backend build failed"
        exit 1
    fi
else
    echo "[1/4] Backend executable found"
fi

echo ""
echo "[2/4] Verifying and preparing backend resources..."
if [ ! -f "$BACKEND_EXE" ]; then
    echo "[ERROR] Backend executable not found after build: $BACKEND_EXE"
    exit 1
fi
mkdir -p "$RESOURCES_BACKEND"
cp "$BACKEND_EXE" "$RESOURCES_BACKEND/"
echo "[2/4] Backend resources ready"

echo ""
echo "[3/4] Building frontend..."
cd "$FRONTEND_DIR"
pnpm run build
if [ $? -ne 0 ]; then
    echo "[ERROR] Frontend build failed"
    exit 1
fi
echo "[3/4] Frontend build complete"

echo ""
echo "[4/4] Creating installer packages..."
if [ "$PLATFORM" = "mac" ]; then
    pnpm exec electron-builder --mac
elif [ "$PLATFORM" = "linux" ]; then
    pnpm exec electron-builder --linux
else
    pnpm exec electron-builder --win
fi

if [ $? -ne 0 ]; then
    echo "[ERROR] Package creation failed"
    exit 1
fi

echo ""
echo "========================================"
echo "  BUILD SUCCESS!"
echo "========================================"
echo ""
echo "Output files:"
if [ "$PLATFORM" = "mac" ]; then
    echo "  - DMG: release/dist/LuomiNest-*-mac-*.dmg"
    echo "  - ZIP: release/dist/LuomiNest-*-mac-*.zip"
elif [ "$PLATFORM" = "linux" ]; then
    echo "  - AppImage: release/dist/LuomiNest-*-linux-*.AppImage"
    echo "  - DEB:      release/dist/LuomiNest-*-linux-*.deb"
    echo "  - TAR.GZ:   release/dist/LuomiNest-*-linux-*.tar.gz"
else
    echo "  - NSIS Installer: release/dist/LuomiNest-Setup-0.2.0.exe"
    echo "  - Portable:       release/dist/LuomiNest-Portable-0.2.0.exe"
fi
echo ""
