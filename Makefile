.PHONY: help check install dev dev-frontend dev-backend build build-frontend build-backend build-win build-linux build-mac build-portable build-installer clean clean-frontend clean-backend clean-all

PYTHON  ?= python
PNPM    ?= pnpm
PIP     ?= pip

PROJECT_ROOT    := $(shell pwd)
FRONTEND_DIR    := $(PROJECT_ROOT)/frontend
BACKEND_DIR     := $(PROJECT_ROOT)/backend
DIST_DIR        := $(PROJECT_ROOT)/dist

VERSION         := 0.2.0

ifeq ($(OS),Windows_NT)
  ACTIVATE := .venv\Scripts\activate &&
  RM_RF    := rmdir /s /q
  MKDIR_P  := mkdir
  COPY     := copy /Y
  NULL     := > nul
else
  ACTIVATE := . .venv/bin/activate &&
  RM_RF    := rm -rf
  MKDIR_P  := mkdir -p
  COPY     := cp
  NULL     :=
endif

help:
	@echo "LuomiNest - Distributed AI Companion Platform"
	@echo ""
	@echo "Development Commands:"
	@echo "  make check           - Check prerequisites (Node.js, pnpm, Python)"
	@echo "  make install         - Install all dependencies (frontend + backend)"
	@echo "  make dev             - Start frontend dev server"
	@echo "  make dev-frontend    - Start frontend dev server"
	@echo "  make dev-backend     - Start backend dev server"
	@echo ""
	@echo "Build Commands:"
	@echo "  make build           - Build frontend + backend"
	@echo "  make build-frontend  - Build frontend only"
	@echo "  make build-backend   - Build backend only (PyInstaller)"
	@echo "  make build-win       - Build Windows installer (NSIS)"
	@echo "  make build-portable  - Build Windows portable executable"
	@echo "  make build-installer - Build Windows Inno Setup installer"
	@echo "  make build-linux     - Build Linux packages"
	@echo "  make build-mac       - Build macOS DMG"
	@echo ""
	@echo "Clean Commands:"
	@echo "  make clean           - Clean all build artifacts"
	@echo "  make clean-frontend  - Clean frontend build artifacts"
	@echo "  make clean-backend   - Clean backend build artifacts"
	@echo ""

check:
	@echo "Checking prerequisites..."
	@$(PYTHON) --version 2>/dev/null || (echo "[MISSING] Python 3.12+ not found" && exit 1)
	@$(PYTHON) --version
	@node --version 2>/dev/null || (echo "[MISSING] Node.js not found" && exit 1)
	@node --version
	@$(PNPM) --version 2>/dev/null || (echo "[MISSING] pnpm not found" && exit 1)
	@$(PNPM) --version
	@echo "All prerequisites satisfied!"

install: install-backend install-frontend

install-backend:
	@echo "[Backend] Installing dependencies..."
	cd $(BACKEND_DIR) && $(PYTHON) -m venv .venv
	cd $(BACKEND_DIR) && $(ACTIVATE) $(PIP) install --upgrade pip && $(PIP) install pyinstaller && $(PIP) install -e ".[dev]"
	@echo "[Backend] Dependencies installed."

install-frontend:
	@echo "[Frontend] Installing dependencies..."
	cd $(FRONTEND_DIR) && $(PNPM) install
	@echo "[Frontend] Dependencies installed."

dev: dev-frontend

dev-frontend:
	cd $(FRONTEND_DIR) && $(PNPM) run dev

dev-backend:
	cd $(BACKEND_DIR) && $(ACTIVATE) $(PYTHON) main.py

build: build-backend build-frontend

build-backend:
	@echo "[Backend] Building with PyInstaller..."
	cd $(BACKEND_DIR) && $(ACTIVATE) pyinstaller luominest-backend.spec --clean --noconfirm
	@echo "[Backend] Build complete: $(BACKEND_DIR)/dist/luominest-backend.exe"

build-frontend:
	@echo "[Frontend] Building with electron-vite..."
	cd $(FRONTEND_DIR) && $(PNPM) run build
	@echo "[Frontend] Build complete."

build-win: prepare-backend
	@echo "[Frontend] Building Windows installer (NSIS)..."
	cd $(FRONTEND_DIR) && $(PNPM) run build:win
	@echo "Output: $(FRONTEND_DIR)/release/dist/"

build-portable: prepare-backend
	@echo "[Frontend] Building Windows portable..."
	cd $(FRONTEND_DIR) && $(PNPM) run build:win-portable
	@echo "Output: $(FRONTEND_DIR)/release/dist/"

build-installer: prepare-backend
	@echo "[Frontend] Building Windows Inno Setup installer..."
	cd $(FRONTEND_DIR) && $(PNPM) run build && $(PNPM) exec electron-builder --win --dir
	cd $(FRONTEND_DIR) && iscc installer.iss
	@echo "Output: $(FRONTEND_DIR)/release/installer/"

build-linux: prepare-backend
	@echo "[Frontend] Building Linux packages..."
	cd $(FRONTEND_DIR) && $(PNPM) run build:linux
	@echo "Output: $(FRONTEND_DIR)/release/dist/"

build-mac: prepare-backend
	@echo "[Frontend] Building macOS DMG..."
	cd $(FRONTEND_DIR) && $(PNPM) run build:mac
	@echo "Output: $(FRONTEND_DIR)/release/dist/"

prepare-backend: build-backend
	@echo "[Prepare] Copying backend to frontend resources..."
	$(MKDIR_P) $(FRONTEND_DIR)/resources/backend
	$(COPY) $(BACKEND_DIR)/dist/luominest-backend.exe $(FRONTEND_DIR)/resources/backend/ $(NULL)
	@echo "[Prepare] Backend ready."

clean: clean-frontend clean-backend
	$(RM_RF) $(DIST_DIR)
	@echo "All clean."

clean-frontend:
	$(RM_RF) $(FRONTEND_DIR)/out
	$(RM_RF) $(FRONTEND_DIR)/release
	@echo "[Frontend] Clean."

clean-backend:
	$(RM_RF) $(BACKEND_DIR)/dist
	$(RM_RF) $(BACKEND_DIR)/build
	@echo "[Backend] Clean."
