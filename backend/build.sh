#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo " LuomiNest Backend Build Script v2.0"
echo " PyInstaller Executable Generator"
echo "========================================"
echo ""

if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python not found in PATH"
    echo "Please install Python 3.10+ from https://www.python.org/downloads/"
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

echo "Upgrading pip..."
pip install --upgrade pip --quiet

echo "Installing PyInstaller..."
pip install pyinstaller --quiet

echo "Installing project dependencies (development mode)..."
if ! pip install -e ".[dev]" --quiet; then
    echo "[WARNING] Some dependencies may have failed to install"
    echo "Continuing with build..."
fi

echo ""
echo "[4/5] Checking for spec file..."
if [ ! -f "luominest-backend.spec" ]; then
    echo "[ERROR] luominest-backend.spec file not found!"
    echo "Please ensure the PyInstaller spec file exists in the backend directory."
    exit 1
fi
echo "Spec file found: luominest-backend.spec"

echo ""
echo "[5/5] Building executable with PyInstaller..."
echo "This may take a few minutes..."

if ! pyinstaller luominest-backend.spec --clean --noconfirm; then
    echo ""
    echo "[ERROR] PyInstaller build failed"
    echo "Please check the error messages above."
    exit 1
fi

BACKEND_EXE="dist/luominest-backend"
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
    echo "Output: dist/luominest-backend"
    echo "Size: $SIZE"
    echo ""
    echo "Next steps:"
    echo "  1. Run the global build script to create installer"
    echo "     cd .. && ./build-all.sh (or .ps1 on Windows)"
else
    echo ""
    echo "[ERROR] Build output not found: dist/luominest-backend"
    echo "The build may have failed silently. Check the PyInstaller output above."
    exit 1
fi
