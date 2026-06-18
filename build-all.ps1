$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Platform = "win"
if ($IsMacOS) { $Platform = "mac" }
elseif ($IsLinux) { $Platform = "linux" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " LuomiNest Unified Build Script" -ForegroundColor Cyan
Write-Host " Host Platform: $Platform" -ForegroundColor Cyan
Write-Host " Targets:" -ForegroundColor Cyan
if ($Platform -eq "win") {
    Write-Host "   Win64 (Inno Setup Installer + Portable)" -ForegroundColor Cyan
} else {
    Write-Host "   Current platform packages" -ForegroundColor Cyan
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$DistDir = Join-Path $ProjectRoot "dist"
$ResourcesBackend = Join-Path $FrontendDir "resources\backend"
$ReleaseDir = Join-Path $FrontendDir "release\dist"
$InstallerDir = Join-Path $FrontendDir "release\installer"

if ($Platform -eq "win") {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend.exe"
} else {
    $BackendExe = Join-Path $BackendDir "dist/luominest-backend"
}

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

$startTime = Get-Date

if ($Platform -eq "win") {
    Write-Host "Pre-check: Stopping leftover LuomiNest processes..." -ForegroundColor Gray
    Stop-Process -Name "LuomiNest" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "electron" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Write-Host "Pre-check: Cleaning old release directory..." -ForegroundColor Gray
    Remove-Item -Recurse -Force (Join-Path $FrontendDir "release") -ErrorAction SilentlyContinue
}

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
# Step 4: Create portable package (electron-builder)
# ============================================================
Write-Host ""
Write-Host "[Step 4/6] Creating portable package..." -ForegroundColor Yellow
switch ($Platform) {
    "mac" {
        & pnpm exec electron-builder --mac
    }
    "linux" {
        & pnpm exec electron-builder --linux AppImage deb rpm
    }
    default {
        & pnpm exec electron-builder --win
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Portable package creation failed" -ForegroundColor Red
    exit 1
}
Write-Host "Portable package created" -ForegroundColor Green

# ============================================================
# Step 5: Cross-platform Linux build via WSL (Windows only)
# ============================================================
Write-Host ""
Write-Host "[Step 5/6] Cross-platform Linux build..." -ForegroundColor Yellow
if ($Platform -eq "win") {
    $wslAvailable = $false
    try {
        $wslListRaw = wsl --list --quiet 2>$null
        if ($LASTEXITCODE -eq 0 -and $wslListRaw) {
            $wslAvailable = $true
        }
    } catch {}

    if ($wslAvailable) {
        Write-Host "WSL detected, building Linux packages via WSL..." -ForegroundColor Yellow

        $wslDistro = $null
        $wslListRaw = wsl --list --quiet 2>$null
        foreach ($line in $wslListRaw) {
            $cleanBytes = [System.Text.Encoding]::Unicode.GetBytes($line) | Where-Object { $_ -ne 0 }
            $trimmed = [System.Text.Encoding]::ASCII.GetString($cleanBytes).Trim()
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
                Write-Host "[WARNING] WSL Linux build failed" -ForegroundColor Yellow
            }

            Remove-Item $scriptPath -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Host "WSL not available, skipping Linux cross-build" -ForegroundColor Gray
    }
} elseif ($Platform -eq "linux") {
    Write-Host "Building Windows portable via cross-compilation..." -ForegroundColor Yellow
    & pnpm exec electron-builder --win
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Windows portable built via cross-compilation" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Windows cross-build failed" -ForegroundColor Yellow
    }
}

# ============================================================
# Step 6: Inno Setup installer (Windows only)
# ============================================================
Write-Host ""
Write-Host "[Step 6/6] Creating Inno Setup installer..." -ForegroundColor Yellow
if ($Platform -eq "win") {
    $innoSetupPath = Get-Command "iscc" -ErrorAction SilentlyContinue
    if (-not $innoSetupPath) {
        $defaultPaths = @(
            "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
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
        Set-Location $FrontendDir
        & $innoSetupPath "installer.iss"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Inno Setup installer created successfully!" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] Inno Setup build failed" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "[ERROR] Inno Setup not found! Please install Inno Setup 6 from https://jrsoftware.org/isdl.php" -ForegroundColor Red
        exit 1
    }
} elseif ($Platform -eq "mac") {
    Write-Host "Skipping Inno Setup (not available on macOS)" -ForegroundColor Gray
} else {
    Write-Host "Skipping Inno Setup (not available on Linux)" -ForegroundColor Gray
}

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build completed!" -ForegroundColor Green
Write-Host " Platform: $Platform" -ForegroundColor Green
Write-Host " Duration: $($duration.ToString('mm\:ss'))" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Generated packages:" -ForegroundColor Magenta
Write-Host "" -ForegroundColor White
Write-Host "  [Installer] Inno Setup (.exe):" -ForegroundColor Cyan
Get-ChildItem "$InstallerDir\*" -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension -match '\.(exe)$'
} | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 2)
    Write-Host "    $($_.Name) ($size MB)" -ForegroundColor Green
}

Write-Host ""
Write-Host "  [Portable] Electron Builder:" -ForegroundColor Cyan
Get-ChildItem "$ReleaseDir\*" -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension -match '\.(exe|AppImage|deb|rpm|dmg|zip)$'
} | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 2)
    Write-Host "    $($_.Name) ($size MB)" -ForegroundColor Green
}

Set-Location $ProjectRoot