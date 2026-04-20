#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo " LuomiNest Backend Build Script"
echo "========================================"
echo ""

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python not found in PATH"
    exit 1
fi

PYTHON_CMD="python3"
if ! command -v python3 &>/dev/null; then
    PYTHON_CMD="python"
fi

echo "[1/4] Checking Python version..."
$PYTHON_CMD --version

echo ""
echo "[2/4] Creating virtual environment..."
if [ ! -d ".venv" ]; then
    $PYTHON_CMD -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment"
        exit 1
    fi
fi

echo ""
echo "[3/4] Installing dependencies..."
source .venv/bin/activate
pip install --upgrade pip
pip install pyinstaller
pip install -e ".[dev]"

echo ""
echo "[4/4] Building executable with PyInstaller..."
pyinstaller luominest-backend.spec --clean --noconfirm

if [ $? -ne 0 ]; then
    echo "[ERROR] PyInstaller build failed"
    exit 1
fi

BACKEND_EXE="dist/luominest-backend"
if [ "$(uname -s)" = "Darwin" ] || [ "$(uname -s)" = "Linux" ]; then
    chmod +x "$BACKEND_EXE" 2>/dev/null || true
fi

echo ""
echo "========================================"
echo " Build completed successfully!"
echo " Output: dist/luominest-backend"
echo "========================================"
