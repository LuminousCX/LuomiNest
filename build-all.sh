#!/usr/bin/env bash
set -euo pipefail

UNAME_S="$(uname -s)"
PLATFORM="linux"
if [ "$UNAME_S" = "Darwin" ]; then
    PLATFORM="mac"
fi

echo "========================================"
echo " LuomiNest Unified Build Script"
echo " Platform: $PLATFORM"
echo " Targets: Win (NSIS+Portable) / Linux (AppImage+deb+rpm)"
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

START_TIME=$(date +%s)

echo "[Step 1/5] Building backend with PyInstaller..."
cd "$BACKEND_DIR"
chmod +x build.sh 2>/dev/null || true
bash build.sh
if [ $? -ne 0 ]; then
    echo "[ERROR] Backend build failed"
    exit 1
fi

echo ""
echo "[Step 2/5] Verifying backend executable..."
if [ ! -f "$BACKEND_EXE" ]; then
    echo "[ERROR] Backend executable not found: $BACKEND_EXE"
    exit 1
fi
echo "Backend executable found: $BACKEND_EXE"

mkdir -p "$RESOURCES_BACKEND"
cp "$BACKEND_EXE" "$RESOURCES_BACKEND/"
echo "Backend resources copied"

echo ""
echo "[Step 3/5] Building frontend with electron-vite..."
cd "$FRONTEND_DIR"
pnpm run build
if [ $? -ne 0 ]; then
    echo "[ERROR] Frontend build failed"
    exit 1
fi
echo "Frontend build complete"

echo ""
echo "[Step 4/5] Creating installer packages (electron-builder)..."
if [ "$PLATFORM" = "mac" ]; then
    echo "Building macOS DMG + zip..."
    pnpm exec electron-builder --mac
elif [ "$PLATFORM" = "linux" ]; then
    echo "Building Linux AppImage + deb + rpm..."
    pnpm exec electron-builder --linux AppImage deb rpm
else
    echo "Building Windows NSIS + portable..."
    pnpm exec electron-builder --win
fi

if [ $? -ne 0 ]; then
    echo "[ERROR] Installer creation failed"
    exit 1
fi
echo "Electron-builder packages created"

echo ""
echo "[Step 5/5] Checking for Inno Setup (Windows only)..."
if [ "$PLATFORM" = "win" ] && command -v iscc &>/dev/null; then
    echo "Inno Setup found, creating Ollama-style installer..."
    iscc "$FRONTEND_DIR/installer.iss"
    if [ $? -eq 0 ]; then
        echo "Inno Setup installer created"
    else
        echo "[WARNING] Inno Setup build failed, NSIS packages are ready"
    fi
else
    echo "Skipping Inno Setup (not Windows or not installed)"
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
SECONDS=$((DURATION % 60))

echo ""
echo "========================================"
echo " Build completed!"
echo " Platform: $PLATFORM"
echo " Duration: ${MINUTES}m ${SECONDS}s"
echo " Output: $FRONTEND_DIR/release/"
echo "========================================"
echo ""

echo "Generated packages:"
for file in "$FRONTEND_DIR/release/dist/"*; do
    if [ -f "$file" ]; then
        SIZE=$(du -h "$file" | cut -f1)
        echo "  $(basename "$file") ($SIZE)"
    fi
done

cd "$SCRIPT_DIR"
