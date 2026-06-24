#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo " LuomiNest Backend Build Script v3.0"
echo " PyInstaller Executable Generator"
echo "========================================"
echo ""

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python not found in PATH"
    echo "Please install Python 3.12+ from https://www.python.org/downloads/"
    exit 1
fi

PYTHON_CMD="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON_CMD="python"
fi

echo "[1/5] Checking Python version..."
if ! $PYTHON_CMD --version; then
    echo "[ERROR] Failed to check Python version"
    exit 1
fi

echo ""
echo "[2/5] Creating virtual environment..."
if [ ! -d ".venv" ]; then
    echo "Creating new virtual environment..."
    $PYTHON_CMD -m pip install --upgrade pip --quiet 2>/dev/null || true
    $PYTHON_CMD -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        exit 1
    fi
    echo "Virtual environment created successfully"
else
    echo "Virtual environment already exists"
fi

echo ""
echo "[3/5] Activating virtual environment and installing dependencies..."
source .venv/bin/activate

# Configure pip mirror for faster downloads in China
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple 2>/dev/null || true
pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn 2>/dev/null || true

echo "Upgrading pip..."
pip install --upgrade pip --quiet

echo "Installing PyInstaller..."
pip install pyinstaller --quiet

echo "Installing project dependencies (dev mode)..."
# Retry up to 3 times for network resilience
RETRY_COUNT=0
while ! pip install -e ".[dev]" --quiet; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt 3 ]; then
        echo "[WARNING] Install attempt $RETRY_COUNT failed, retrying..."
        sleep 5
    else
        echo "[WARNING] Dev dependencies failed after retries, installing base only..."
        pip install -e . --quiet
        break
    fi
done

echo ""
echo "[4/5] Checking for spec file..."
if [ ! -f "luominest-backend.spec" ]; then
    echo "[ERROR] luominest-backend.spec file not found!"
    exit 1
fi
echo "Spec file found: luominest-backend.spec"

echo ""
echo "[5/5] Building executable with PyInstaller..."
echo "This may take a few minutes..."

if ! pyinstaller luominest-backend.spec --clean --noconfirm; then
    echo ""
    echo "[ERROR] PyInstaller build failed"
    exit 1
fi

BACKEND_EXE="dist/luominest-backend/luominest-backend"
if [ "$(uname -s)" = "Darwin" ] || [ "$(uname -s)" = "Linux" ]; then
    chmod +x "$BACKEND_EXE" 2>/dev/null || true
fi

if [ -f "$BACKEND_EXE" ]; then
    SIZE=$(du -h "$BACKEND_EXE" | cut -f1)

    echo ""
    echo "========================================"
    echo " Build completed successfully!"
    echo "========================================"
    echo ""
    echo "Output: $BACKEND_EXE"
    echo "Size: $SIZE"
    echo ""
    echo "Next steps:"
    echo "  1. Run the global build script to create installer"
    echo "     cd .. && ./build-all.ps1 (or pwsh build-all.ps1)"
else
    echo ""
    echo "[ERROR] Build output not found: $BACKEND_EXE"
    exit 1
fi
