#!/usr/bin/env bash
set -euo pipefail

UNAME_S="$(uname -s)"
PLATFORM="linux"
if [ "$UNAME_S" = "Darwin" ]; then
    PLATFORM="mac"
fi

echo "========================================"
echo " LuomiNest Unified Build Script"
echo " Host Platform: $PLATFORM"
echo " Targets: Win64 (NSIS+Portable) + Linux (AppImage+deb+rpm)"
if [ "$PLATFORM" = "mac" ]; then
    echo "          + macOS (DMG+zip)"
fi
echo "========================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"
BACKEND_DIR="$SCRIPT_DIR/backend"
DIST_DIR="$SCRIPT_DIR/dist"
RESOURCES_BACKEND="$FRONTEND_DIR/resources/backend"
RELEASE_DIR="$FRONTEND_DIR/release/dist"

if [ "$PLATFORM" = "win" ]; then
    BACKEND_EXE="$BACKEND_DIR/dist/luominest-backend.exe"
else
    BACKEND_EXE="$BACKEND_DIR/dist/luominest-backend"
fi

export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
export ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/"

START_TIME=$(date +%s)

# ============================================================
# Step 1: Build backend
# ============================================================
echo "[Step 1/6] Building backend with PyInstaller..."
cd "$BACKEND_DIR"
chmod +x build.sh 2>/dev/null || true
if ! bash build.sh; then
    echo "[ERROR] Backend build failed"
    exit 1
fi

# ============================================================
# Step 2: Verify and copy backend executable
# ============================================================
echo ""
echo "[Step 2/6] Verifying backend executable..."
if [ ! -f "$BACKEND_EXE" ]; then
    echo "[ERROR] Backend executable not found: $BACKEND_EXE"
    exit 1
fi
echo "Backend executable found: $BACKEND_EXE"

mkdir -p "$RESOURCES_BACKEND"
cp "$BACKEND_EXE" "$RESOURCES_BACKEND/"
echo "Backend resources copied"

# ============================================================
# Step 3: Build frontend
# ============================================================
echo ""
echo "[Step 3/6] Building frontend with electron-vite..."
cd "$FRONTEND_DIR"
if ! pnpm run build; then
    echo "[ERROR] Frontend build failed"
    exit 1
fi
echo "Frontend build complete"

# ============================================================
# Step 4: Package for current platform
# ============================================================
echo ""
echo "[Step 4/6] Creating installer packages for current platform..."
if [ "$PLATFORM" = "mac" ]; then
    echo "Building macOS packages..."
    if ! pnpm exec electron-builder --mac; then
        echo "[ERROR] Current platform packaging failed"
        exit 1
    fi
elif [ "$PLATFORM" = "linux" ]; then
    echo "Building Linux packages..."
    if ! pnpm exec electron-builder --linux AppImage deb rpm; then
        echo "[ERROR] Current platform packaging failed"
        exit 1
    fi
else
    echo "Building Windows packages..."
    if ! pnpm exec electron-builder --win; then
        echo "[ERROR] Current platform packaging failed"
        exit 1
    fi
fi
echo "Current platform packages created"

# ============================================================
# Step 5: Cross-platform build
# ============================================================
echo ""
echo "[Step 5/6] Cross-platform build..."
if [ "$PLATFORM" = "linux" ]; then
    echo "Building Windows packages via cross-compilation..."
    if pnpm exec electron-builder --win; then
        echo "Windows packages built via cross-compilation"
    else
        echo "[WARNING] Windows cross-build failed"
    fi
elif [ "$PLATFORM" = "mac" ]; then
    echo "Building Linux + Windows packages via cross-compilation..."
    if pnpm exec electron-builder --linux AppImage deb rpm --win; then
        echo "Linux + Windows packages built"
    else
        echo "[WARNING] Cross-platform build partially failed"
    fi
else
    echo "Cross-compilation from Windows to Linux requires WSL."
    echo "Run build-all.ps1 on Windows for automatic WSL integration."
fi

# ============================================================
# Step 6: Inno Setup (Windows only, optional)
# ============================================================
echo ""
echo "[Step 6/6] Checking for Inno Setup (Windows only)..."
if [ "$PLATFORM" = "win" ] && command -v iscc &>/dev/null; then
    echo "Inno Setup found, creating Ollama-style installer..."
    if iscc "$FRONTEND_DIR/installer.iss"; then
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
echo " Host Platform: $PLATFORM"
echo " Duration: ${MINUTES}m ${SECONDS}s"
echo " Output: $RELEASE_DIR"
echo "========================================"
echo ""

echo "Generated packages:"
for file in "$RELEASE_DIR/"*; do
    if [ -f "$file" ]; then
        case "$file" in
            *.exe|*.AppImage|*.deb|*.rpm|*.dmg|*.zip)
                SIZE=$(du -h "$file" | cut -f1)
                echo "  $(basename "$file") ($SIZE)"
                ;;
        esac
    fi
done

cd "$SCRIPT_DIR"
