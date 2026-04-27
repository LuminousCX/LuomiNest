$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Platform = "win"
if ($IsMacOS) { $Platform = "mac" }
elseif ($IsLinux) { $Platform = "linux" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " LuomiNest Unified Build Script" -ForegroundColor Cyan
Write-Host " Host Platform: $Platform" -ForegroundColor Cyan
Write-Host " Targets: Win64 (NSIS+Portable) + Linux (AppImage+deb+rpm)" -ForegroundColor Cyan
if ($Platform -eq "mac") {
    Write-Host "         + macOS (DMG+zip)" -ForegroundColor Cyan
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$DistDir = Join-Path $ProjectRoot "dist"
$ResourcesBackend = Join-Path $FrontendDir "resources\backend"
$ReleaseDir = Join-Path $FrontendDir "release\dist"

if ($Platform -eq "win") {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend.exe"
} else {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend"
}

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

$startTime = Get-Date

# ============================================================
# Step 1: Build backend
# ============================================================
Write-Host "[Step 1/6] Building backend with PyInstaller..." -ForegroundColor Yellow
Set-Location $BackendDir
if ($Platform -eq "win") {
    & ".\build.bat"
} else {
    bash ./build.sh
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Backend build failed" -ForegroundColor Red
    exit 1
}

# ============================================================
# Step 2: Verify and copy backend executable
# ============================================================
Write-Host ""
Write-Host "[Step 2/6] Verifying backend executable..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[ERROR] Backend executable not found: $BackendExe" -ForegroundColor Red
    exit 1
}
Write-Host "Backend executable found: $BackendExe" -ForegroundColor Green

if (-not (Test-Path $ResourcesBackend)) {
    New-Item -ItemType Directory -Force -Path $ResourcesBackend | Out-Null
}
Copy-Item $BackendExe $ResourcesBackend -Force
Write-Host "Backend resources copied" -ForegroundColor Green

# ============================================================
# Step 3: Build frontend
# ============================================================
Write-Host ""
Write-Host "[Step 3/6] Building frontend with electron-vite..." -ForegroundColor Yellow
Set-Location $FrontendDir
& pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed" -ForegroundColor Red
    exit 1
}
Write-Host "Frontend build complete" -ForegroundColor Green

# ============================================================
# Step 4: Package for current platform
# ============================================================
Write-Host ""
Write-Host "[Step 4/6] Creating installer packages for current platform..." -ForegroundColor Yellow
switch ($Platform) {
    "mac" {
        Write-Host "Building macOS packages..." -ForegroundColor Yellow
        & pnpm exec electron-builder --mac
    }
    "linux" {
        Write-Host "Building Linux packages..." -ForegroundColor Yellow
        & pnpm exec electron-builder --linux AppImage deb rpm
    }
    default {
        Write-Host "Building Windows packages..." -ForegroundColor Yellow
        & pnpm exec electron-builder --win
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Current platform packaging failed" -ForegroundColor Red
    exit 1
}
Write-Host "Current platform packages created" -ForegroundColor Green

# ============================================================
# Step 5: Cross-platform Linux build via WSL (Windows only)
# ============================================================
Write-Host ""
Write-Host "[Step 5/6] Cross-platform Linux build..." -ForegroundColor Yellow
if ($Platform -eq "win") {
    $wslAvailable = $false
    try {
        $wslList = wsl --list --quiet 2>$null
        if ($LASTEXITCODE -eq 0 -and $wslList) {
            $wslAvailable = $true
        }
    } catch {}

    if ($wslAvailable) {
        Write-Host "WSL detected, building Linux packages via WSL..." -ForegroundColor Yellow

        $wslDistro = $null
        foreach ($line in (wsl --list --quiet 2>$null)) {
            $trimmed = $line.Trim()
            if ($trimmed -and $trimmed -ne "docker-desktop") {
                $wslDistro = $trimmed
                break
            }
        }

        if (-not $wslDistro) {
            Write-Host "[WARNING] No suitable WSL distro found, skipping Linux build" -ForegroundColor Yellow
        } else {
            Write-Host "Using WSL distro: $wslDistro" -ForegroundColor Gray

            $wslBuildScript = @"
set -euo pipefail

WSL_BUILD_DIR="$HOME/build-luominest"
PROJECT_SRC="/mnt/c/Users/lumin/Projects/Project/LuomiNest"

echo "Copying project to WSL filesystem..."
mkdir -p "$WSL_BUILD_DIR"
rm -rf "$WSL_BUILD_DIR/frontend" "$WSL_BUILD_DIR/backend"
cp -r "$PROJECT_SRC/frontend" "$WSL_BUILD_DIR/"
cp -r "$PROJECT_SRC/backend" "$WSL_BUILD_DIR/"

echo "Installing frontend dependencies..."
cd "$WSL_BUILD_DIR/frontend"
export ELECTRON_MIRROR=https://npmmirror.com/mirrors/electron/
export ELECTRON_BUILDER_BINARIES_MIRROR=https://npmmirror.com/mirrors/electron-builder-binaries/
pnpm install --frozen-lockfile 2>/dev/null || pnpm install

echo "Building frontend..."
pnpm run build

echo "Building backend in WSL..."
cd "$WSL_BUILD_DIR/backend"
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install pyinstaller --quiet
pip install -e '.[dev]' --quiet 2>/dev/null || pip install -e . --quiet
pyinstaller luominest-backend.spec --clean --noconfirm

echo "Copying Linux backend to frontend resources..."
cp "$WSL_BUILD_DIR/backend/dist/luominest-backend" "$WSL_BUILD_DIR/frontend/resources/backend/"
rm -f "$WSL_BUILD_DIR/frontend/resources/backend/luominest-backend.exe"

echo "Packaging Linux targets (AppImage + deb + rpm)..."
cd "$WSL_BUILD_DIR/frontend"
pnpm exec electron-builder --linux AppImage deb rpm

echo "Copying Linux packages to Windows output..."
mkdir -p "$PROJECT_SRC/frontend/release/dist"
cp "$WSL_BUILD_DIR/frontend/release/dist/"*.AppImage "$PROJECT_SRC/frontend/release/dist/" 2>/dev/null || true
cp "$WSL_BUILD_DIR/frontend/release/dist/"*.deb "$PROJECT_SRC/frontend/release/dist/" 2>/dev/null || true
cp "$WSL_BUILD_DIR/frontend/release/dist/"*.rpm "$PROJECT_SRC/frontend/release/dist/" 2>/dev/null || true

echo "WSL_LINUX_BUILD_DONE"
"@

            $scriptPath = Join-Path $env:TEMP "luominest-wsl-build.sh"
            $wslBuildScript | Out-File -FilePath $scriptPath -Encoding utf8 -Force

            $wslScriptPath = ($scriptPath -replace '\\', '/' -replace '^([A-Z]):', { '/mnt/$1'.ToLower() })
            wsl -d $wslDistro -- bash $wslScriptPath

            if ($LASTEXITCODE -eq 0) {
                Write-Host "Linux packages built via WSL" -ForegroundColor Green
            } else {
                Write-Host "[WARNING] WSL Linux build failed, Windows packages are ready" -ForegroundColor Yellow
            }

            Remove-Item $scriptPath -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "WSL not available, skipping Linux cross-build" -ForegroundColor Gray
        Write-Host "To build Linux packages, install WSL with Ubuntu" -ForegroundColor Gray
    }
} elseif ($Platform -eq "linux") {
    Write-Host "Building Windows packages via cross-compilation..." -ForegroundColor Yellow
    & pnpm exec electron-builder --win
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Windows packages built via cross-compilation" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Windows cross-build failed" -ForegroundColor Yellow
    }
} else {
    Write-Host "Building Linux + Windows packages via cross-compilation..." -ForegroundColor Yellow
    & pnpm exec electron-builder --linux AppImage deb rpm --win
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Linux + Windows packages built" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Cross-platform build partially failed" -ForegroundColor Yellow
    }
}

# ============================================================
# Step 6: Inno Setup (Windows only, optional)
# ============================================================
Write-Host ""
Write-Host "[Step 6/6] Checking for Inno Setup (Windows only)..." -ForegroundColor Yellow
if ($Platform -eq "win") {
    $innoSetupPath = Get-Command "iscc" -ErrorAction SilentlyContinue
    if (-not $innoSetupPath) {
        $defaultPaths = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
        )
        foreach ($path in $defaultPaths) {
            if (Test-Path $path) {
                $innoSetupPath = $path
                break
            }
        }
    }

    if ($innoSetupPath) {
        Write-Host "Inno Setup found, creating Ollama-style installer..." -ForegroundColor Yellow
        & $innoSetupPath "installer.iss"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Inno Setup installer created" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Inno Setup build failed, NSIS packages are ready" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Inno Setup not found, skipping" -ForegroundColor Gray
    }
}

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build completed!" -ForegroundColor Green
Write-Host " Host Platform: $Platform" -ForegroundColor Green
Write-Host " Duration: $($duration.ToString('mm\:ss'))" -ForegroundColor Green
Write-Host " Output: $ReleaseDir" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Generated packages:" -ForegroundColor Magenta
Get-ChildItem "$ReleaseDir\*" -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension -match '\.(exe|AppImage|deb|rpm|dmg|zip)$'
} | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 2)
    Write-Host "  $($_.Name) ($size MB)" -ForegroundColor Green
}

Set-Location $ProjectRoot
