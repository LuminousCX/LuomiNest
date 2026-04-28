.PHONY: help check install dev dev-frontend dev-backend build build-frontend build-backend \
       build-win build-linux build-mac \
       prepare-backend verify-backend \
       clean clean-frontend clean-backend clean-all config doctor \
       lint lint-frontend lint-backend test test-frontend test-backend

PYTHON  ?= python
PNPM    ?= pnpm
PIP     ?= pip

PROJECT_ROOT    := $(shell pwd)
FRONTEND_DIR    := $(PROJECT_ROOT)/frontend
BACKEND_DIR     := $(PROJECT_ROOT)/backend
DIST_DIR        := $(PROJECT_ROOT)/dist

VERSION         := 0.3.0

ifeq ($(OS),Windows_NT)
  ACTIVATE      := .venv\Scripts\activate &&
  RM_RF         := rmdir /s /q
  MKDIR_P       := mkdir
  COPY          := copy /Y
  NULL          := > nul
  DEV_NULL      := > nul 2>&1
  BACKEND_EXE   := luominest-backend.exe
  BUILD_SCRIPT  := build.bat
  PLATFORM      := win
else
  ACTIVATE      := . .venv/bin/activate &&
  RM_RF         := rm -rf
  MKDIR_P       := mkdir -p
  COPY          := cp
  NULL          :=
  DEV_NULL      :=
  BACKEND_EXE   := luominest-backend
  BUILD_SCRIPT  := build.sh
  UNAME_S       := $(shell uname -s)
  ifeq ($(UNAME_S),Darwin)
    PLATFORM    := mac
  else
    PLATFORM    := linux
  endif
endif

help:
	@echo "LuomiNest - Distributed AI Companion Platform (v$(VERSION))"
	@echo ""
	@echo "Development Commands:"
	@echo "  make check                - Check prerequisites (Node.js, pnpm, Python)"
	@echo "  make doctor               - Diagnose setup issues and show fix hints"
	@echo "  make install              - Install all dependencies (frontend + backend)"
	@echo "  make install-backend      - Install backend dependencies"
	@echo "  make install-frontend     - Install frontend dependencies"
	@echo "  make dev                  - Start frontend dev server"
	@echo "  make dev-frontend         - Start frontend dev server"
	@echo "  make dev-backend          - Start backend dev server"
	@echo ""
	@echo "Build Commands:"
	@echo "  make build                - Build frontend + backend"
	@echo "  make build-frontend       - Build frontend only"
	@echo "  make build-backend        - Build backend only (PyInstaller)"
	@echo ""
	@echo "Platform-Specific Build:"
	@echo "  make build-win            - Build Windows installer (NSIS + portable)"
	@echo "  make build-linux          - Build Linux packages (AppImage + deb + rpm)"
	@echo "  make build-mac            - Build macOS DMG + zip"
	@echo ""
	@echo "Quality Commands:"
	@echo "  make lint                 - Run all linters"
	@echo "  make lint-frontend        - Run frontend linter"
	@echo "  make lint-backend         - Run backend linter"
	@echo "  make test                 - Run all tests"
	@echo "  make test-frontend        - Run frontend tests"
	@echo "  make test-backend         - Run backend tests"
	@echo ""
	@echo "Clean Commands:"
	@echo "  make clean                - Clean all build artifacts"
	@echo "  make clean-frontend       - Clean frontend build artifacts"
	@echo "  make clean-backend        - Clean backend build artifacts"
	@echo ""
	@echo "Current Platform: $(PLATFORM)"
	@echo "Backend Executable: $(BACKEND_EXE)"

check:
	@echo "Checking prerequisites..."
	@$(PYTHON) --version $(DEV_NULL) || (echo "[MISSING] Python 3.12+ not found" && exit 1)
	@$(PYTHON) --version
	@node --version $(DEV_NULL) || (echo "[MISSING] Node.js not found" && exit 1)
	@node --version
	@$(PNPM) --version $(DEV_NULL) || (echo "[MISSING] pnpm not found" && exit 1)
	@$(PNPM) --version
	@echo "All prerequisites satisfied!"

doctor:
	@echo "LuomiNest Environment Diagnostics"
	@echo "=================================="
	@echo ""
	@echo "[Platform]"
	@echo "  OS: $(PLATFORM)"
	@echo "  Backend exe: $(BACKEND_EXE)"
	@echo ""
	@echo "[Python]"
	@-$(PYTHON) --version 2>&1 || echo "  NOT FOUND - Install Python 3.12+"
	@echo ""
	@echo "[Node.js]"
	@-node --version 2>&1 || echo "  NOT FOUND - Install Node.js 22+"
	@echo ""
	@echo "[pnpm]"
	@-$(PNPM) --version 2>&1 || echo "  NOT FOUND - Run: npm install -g pnpm"
	@echo ""
	@echo "[Backend venv]"
	@if [ -d "$(BACKEND_DIR)/.venv" ]; then echo "  OK - $(BACKEND_DIR)/.venv exists"; else echo "  MISSING - Run: make install-backend"; fi
	@echo ""
	@echo "[Frontend node_modules]"
	@if [ -d "$(FRONTEND_DIR)/node_modules" ]; then echo "  OK - $(FRONTEND_DIR)/node_modules exists"; else echo "  MISSING - Run: make install-frontend"; fi
	@echo ""
	@echo "[Backend executable]"
	@if [ -f "$(BACKEND_DIR)/dist/$(BACKEND_EXE)" ]; then echo "  OK - $(BACKEND_DIR)/dist/$(BACKEND_EXE)"; else echo "  MISSING - Run: make build-backend"; fi
	@echo ""
	@echo "[NSIS extra script]"
	@if [ -f "$(FRONTEND_DIR)/build/nsis-extra.nsh" ]; then echo "  OK - nsis-extra.nsh exists"; else echo "  MISSING - Will be created during build"; fi
	@echo ""
	@echo "[macOS entitlements]"
	@if [ -f "$(FRONTEND_DIR)/build/entitlements.mac.plist" ]; then echo "  OK - entitlements.mac.plist exists"; else echo "  MISSING - Required for macOS build"; fi
	@echo ""
	@echo "[Linux desktop entry]"
	@if [ -f "$(FRONTEND_DIR)/build/luominest.desktop" ]; then echo "  OK - luominest.desktop exists"; else echo "  MISSING - Required for Linux build"; fi

config:
	@echo "[Config] Copying example configuration files..."
	@if [ ! -f "$(PROJECT_ROOT)/.env" ] && [ -f "$(PROJECT_ROOT)/.env.example" ]; then \
		cp $(PROJECT_ROOT)/.env.example $(PROJECT_ROOT)/.env; \
		echo "  Created .env from .env.example"; \
	else \
		echo "  .env already exists or no .env.example found"; \
	fi
	@if [ ! -f "$(BACKEND_DIR)/config/.env" ] && [ -f "$(BACKEND_DIR)/config/.env.example" ]; then \
		cp $(BACKEND_DIR)/config/.env.example $(BACKEND_DIR)/config/.env; \
		echo "  Created backend config/.env from .env.example"; \
	else \
		echo "  backend config/.env already exists or no .env.example found"; \
	fi
	@if [ ! -f "$(FRONTEND_DIR)/.env" ] && [ -f "$(FRONTEND_DIR)/.env.example" ]; then \
		cp $(FRONTEND_DIR)/.env.example $(FRONTEND_DIR)/.env; \
		echo "  Created frontend .env from .env.example"; \
	else \
		echo "  frontend .env already exists or no .env.example found"; \
	fi
	@echo "[Config] Done."

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
ifeq ($(OS),Windows_NT)
	cd $(BACKEND_DIR) && call $(BUILD_SCRIPT)
else
	cd $(BACKEND_DIR) && chmod +x $(BUILD_SCRIPT) && bash $(BUILD_SCRIPT)
endif
	@echo "[Backend] Build complete: $(BACKEND_DIR)/dist/$(BACKEND_EXE)"

build-frontend:
	@echo "[Frontend] Building with electron-vite..."
	cd $(FRONTEND_DIR) && $(PNPM) run build
	@echo "[Frontend] Build complete."

prepare-backend: build-backend verify-backend
	@echo "[Prepare] Copying backend to frontend resources..."
ifeq ($(OS),Windows_NT)
	-$(MKDIR_P) $(FRONTEND_DIR)\resources\backend 2>$(NULL) || true
else
	$(MKDIR_P) $(FRONTEND_DIR)/resources/backend
endif
	$(COPY) $(BACKEND_DIR)/dist/$(BACKEND_EXE) $(FRONTEND_DIR)/resources/backend/ $(NULL)
	@echo "[Prepare] Backend ready for platform: $(PLATFORM)"

verify-backend:
	@if [ ! -f "$(BACKEND_DIR)/dist/$(BACKEND_EXE)" ]; then \
		echo "[ERROR] Backend executable not found: $(BACKEND_DIR)/dist/$(BACKEND_EXE)"; \
		echo "  The build may have failed. Please check the build output above."; \
		exit 1; \
	fi
	@echo "[Verify] Backend executable verified: $(BACKEND_DIR)/dist/$(BACKEND_EXE)"

build-win: prepare-backend
	@echo "[Frontend] Building Windows installer (NSIS + portable)..."
	cd $(FRONTEND_DIR) && $(PNPM) run build:win
	@echo "Output: $(FRONTEND_DIR)/release/dist/"

build-linux: prepare-backend
	@echo "[Frontend] Building Linux packages (AppImage + deb + rpm)..."
	cd $(FRONTEND_DIR) && $(PNPM) run build:linux
	@echo "Output: $(FRONTEND_DIR)/release/dist/"

build-mac: prepare-backend
	@echo "[Frontend] Building macOS DMG + zip..."
	cd $(FRONTEND_DIR) && $(PNPM) run build:mac
	@echo "Output: $(FRONTEND_DIR)/release/dist/"

lint: lint-frontend lint-backend

lint-frontend:
	cd $(FRONTEND_DIR) && $(PNPM) run typecheck

lint-backend:
	cd $(BACKEND_DIR) && $(ACTIVATE) ruff check . && $(ACTIVATE) mypy .

test: test-frontend test-backend

test-frontend:
	cd $(FRONTEND_DIR) && $(PNPM) run typecheck

test-backend:
	cd $(BACKEND_DIR) && $(ACTIVATE) pytest

clean: clean-frontend clean-backend
	-$(RM_RF) $(DIST_DIR) 2>$(NULL) || true
	@echo "All clean."

clean-frontend:
	-$(RM_RF) $(FRONTEND_DIR)/out 2>$(NULL) || true
	-$(RM_RF) $(FRONTEND_DIR)/release 2>$(NULL) || true
	@echo "[Frontend] Clean."

clean-backend:
	-$(RM_RF) $(BACKEND_DIR)/dist 2>$(NULL) || true
	-$(RM_RF) $(BACKEND_DIR)/build 2>$(NULL) || true
	@echo "[Backend] Clean."
