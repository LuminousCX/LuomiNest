$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ============================================================
# LuomiNest Unified Build Script
# Builds backend (PyInstaller) + frontend (electron-builder) for the
# CURRENT host platform only. Cross-platform builds are handled by
# GitHub Actions (.github/workflows/release.yml).
# ============================================================

$Platform = "win"
if ($IsMacOS) { $Platform = "mac" }
elseif ($IsLinux) { $Platform = "linux" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " LuomiNest Unified Build Script" -ForegroundColor Cyan
Write-Host " Host Platform: $Platform" -ForegroundColor Cyan
Write-Host " Targets: current platform only" -ForegroundColor Cyan
Write-Host " (Cross-platform builds: GitHub Actions)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$ResourcesBackend = Join-Path $FrontendDir "resources\backend"
$ReleaseDir = Join-Path $FrontendDir "release\dist"

if ($Platform -eq "win") {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend\luominest-backend.exe"
} else {
    $BackendExe = Join-Path $BackendDir "dist/luominest-backend/luominest-backend"
}

# Mirror acceleration for China users
$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
$env:PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
$env:PIP_TRUSTED_HOST = "pypi.tuna.tsinghua.edu.cn"

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
# Step 1: Build backend with PyInstaller
# ============================================================
Write-Host ""
Write-Host "[Step 1/5] Building backend with PyInstaller..." -ForegroundColor Yellow
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
Write-Host "[Step 2/5] Verifying backend executable..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[ERROR] Backend executable not found: $BackendExe" -ForegroundColor Red
    exit 1
}
Write-Host "Backend executable found: $BackendExe" -ForegroundColor Green

if (-not (Test-Path $ResourcesBackend)) {
    New-Item -ItemType Directory -Force -Path $ResourcesBackend | Out-Null
}
# Copy the entire backend dist folder (exe + dependencies) so the
# bundled executable can find its shared libraries at runtime.
$BackendDistDir = Split-Path $BackendExe -Parent
Remove-Item -Recurse -Force $ResourcesBackend -ErrorAction SilentlyContinue
Copy-Item -Recurse $BackendDistDir $ResourcesBackend
Write-Host "Backend resources copied" -ForegroundColor Green

# ============================================================
# Step 3: Build frontend with electron-vite
# ============================================================
Write-Host ""
Write-Host "[Step 3/5] Building frontend with electron-vite..." -ForegroundColor Yellow
Set-Location $FrontendDir
& pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed" -ForegroundColor Red
    exit 1
}
Write-Host "Frontend build complete" -ForegroundColor Green

# ============================================================
# Step 4: Package with electron-builder (NSIS / AppImage / DMG)
# ============================================================
Write-Host ""
Write-Host "[Step 4/5] Creating platform packages..." -ForegroundColor Yellow
switch ($Platform) {
    "mac" {
        & pnpm exec electron-builder --mac
    }
    "linux" {
        & pnpm exec electron-builder --linux AppImage deb
    }
    default {
        & pnpm exec electron-builder --win
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Package creation failed" -ForegroundColor Red
    exit 1
}
Write-Host "Platform packages created" -ForegroundColor Green

# ============================================================
# Step 5: Summary
# ============================================================
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
Write-Host ""
Get-ChildItem "$ReleaseDir\*" -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension -match '\.(exe|AppImage|deb|rpm|dmg|zip)$'
} | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 2)
    Write-Host "  $($_.Name) ($size MB)" -ForegroundColor Green
}

Write-Host ""
Write-Host "Cross-platform builds (Linux/macOS/Windows):" -ForegroundColor Cyan
Write-Host "  Push a tag (v*) to trigger GitHub Actions release.yml" -ForegroundColor Gray
Write-Host "  Or run: gh workflow run release.yml" -ForegroundColor Gray

Set-Location $ProjectRoot
