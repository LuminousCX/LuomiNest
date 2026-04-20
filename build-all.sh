#!/usr/bin/env bash
set -euo pipefail

UNAME_S="$(uname -s)"
PLATFORM="linux"
if [ "$UNAME_S" = "Darwin" ]; then
    PLATFORM="mac"
fi

echo "========================================"
echo " LuomiNest All-in-One Build Script"
echo " Platform: $PLATFORM"
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"
DIST_DIR="$SCRIPT_DIR/dist"
RESOURCES_BACKEND="$FRONTEND_DIR/resources/backend"

if [ "$PLATFORM" = "win" ]; then
    BACKEND_EXE="$BACKEND_DIR/dist/luominest-backend.exe"
else
    BACKEND_EXE="$BACKEND_DIR/dist/luominest-backend"
fi

export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
export ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/"

echo "[Step 1/6] Building backend with PyInstaller..."
cd "$BACKEND_DIR"
chmod +x build.sh
bash build.sh
if [ $? -ne 0 ]; then
    echo "[ERROR] Backend build failed"
    exit 1
fi

echo ""
echo "[Step 2/6] Verifying backend executable..."
if [ ! -f "$BACKEND_EXE" ]; then
    echo "[ERROR] Backend executable not found: $BACKEND_EXE"
    echo "The backend build may have failed. Check the build output above."
    exit 1
fi

echo ""
echo "[Step 3/6] Creating distribution directory..."
mkdir -p "$DIST_DIR"
rm -rf "$DIST_DIR/backend"
mkdir -p "$DIST_DIR/backend"

echo ""
echo "[Step 4/6] Copying backend to distribution and frontend resources..."
cp "$BACKEND_EXE" "$DIST_DIR/backend/"
if [ ! -f "$DIST_DIR/backend/luominest-backend" ] && [ ! -f "$DIST_DIR/backend/luominest-backend.exe" ]; then
    echo "[ERROR] Failed to copy backend executable"
    exit 1
fi

mkdir -p "$RESOURCES_BACKEND"
cp "$BACKEND_EXE" "$RESOURCES_BACKEND/"
if [ ! -f "$RESOURCES_BACKEND/luominest-backend" ] && [ ! -f "$RESOURCES_BACKEND/luominest-backend.exe" ]; then
    echo "[ERROR] Failed to copy backend executable to frontend resources"
    exit 1
fi

echo ""
echo "[Step 5/6] Building frontend with electron-vite..."
cd "$FRONTEND_DIR"
pnpm run build
if [ $? -ne 0 ]; then
    echo "[ERROR] Frontend build failed"
    exit 1
fi

echo ""
echo "[Step 6/6] Creating installer packages..."
if [ "$PLATFORM" = "mac" ]; then
    echo "Building macOS DMG + zip..."
    pnpm exec electron-builder --mac
elif [ "$PLATFORM" = "linux" ]; then
    echo "Building Linux AppImage + deb + tar.gz..."
    pnpm exec electron-builder --linux
else
    echo "Building Windows NSIS + portable..."
    pnpm exec electron-builder --win
fi

if [ $? -ne 0 ]; then
    echo "[ERROR] Installer creation failed"
    exit 1
fi

echo ""
echo "========================================"
echo " All-in-One build completed!"
echo " Platform: $PLATFORM"
echo " Output: $FRONTEND_DIR/release/dist/"
echo "========================================"

cd "$SCRIPT_DIR"
