$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Platform = "win"
if ($IsMacOS) { $Platform = "mac" }
elseif ($IsLinux) { $Platform = "linux" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  LuomiNest Build Script" -ForegroundColor Cyan
Write-Host "  Platform: $Platform" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$FrontendDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $FrontendDir
$BackendDir = Join-Path $ProjectRoot "backend"
$ResourcesBackend = Join-Path $FrontendDir "resources\backend"

if ($Platform -eq "win") {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend.exe"
} else {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend"
}

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

Write-Host "[1/4] Checking backend executable..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[1/4] Backend not found, building backend..." -ForegroundColor Yellow
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
} else {
    Write-Host "[1/4] Backend executable found" -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/4] Verifying and preparing backend resources..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[ERROR] Backend executable not found after build: $BackendExe" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $ResourcesBackend)) {
    New-Item -ItemType Directory -Force -Path $ResourcesBackend | Out-Null
}
Copy-Item $BackendExe $ResourcesBackend -Force
Write-Host "[2/4] Backend resources ready" -ForegroundColor Green

Write-Host ""
Write-Host "[3/4] Building frontend..." -ForegroundColor Yellow
Set-Location $FrontendDir
& pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed" -ForegroundColor Red
    exit 1
}
Write-Host "[3/4] Frontend build complete" -ForegroundColor Green

Write-Host ""
Write-Host "[4/4] Creating installer packages..." -ForegroundColor Yellow
switch ($Platform) {
    "mac" {
        & pnpm exec electron-builder --mac
    }
    "linux" {
        & pnpm exec electron-builder --linux
    }
    default {
        & pnpm exec electron-builder --win
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Package creation failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor White
switch ($Platform) {
    "mac" {
        Write-Host "  - DMG: release\dist\LuomiNest-*-mac-*.dmg" -ForegroundColor Cyan
        Write-Host "  - ZIP: release\dist\LuomiNest-*-mac-*.zip" -ForegroundColor Cyan
    }
    "linux" {
        Write-Host "  - AppImage: release\dist\LuomiNest-*-linux-*.AppImage" -ForegroundColor Cyan
        Write-Host "  - DEB:      release\dist\LuomiNest-*-linux-*.deb" -ForegroundColor Cyan
        Write-Host "  - TAR.GZ:   release\dist\LuomiNest-*-linux-*.tar.gz" -ForegroundColor Cyan
    }
    default {
        Write-Host "  - NSIS Installer: release\dist\LuomiNest-Setup-0.2.0.exe" -ForegroundColor Cyan
        Write-Host "  - Portable:       release\dist\LuomiNest-Portable-0.2.0.exe" -ForegroundColor Cyan
    }
}
Write-Host ""
