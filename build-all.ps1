$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Platform = "win"
if ($IsMacOS) { $Platform = "mac" }
elseif ($IsLinux) { $Platform = "linux" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " LuomiNest All-in-One Build Script" -ForegroundColor Cyan
Write-Host " Platform: $Platform" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$DistDir = Join-Path $ProjectRoot "dist"
$ResourcesBackend = Join-Path $FrontendDir "resources\backend"

if ($Platform -eq "win") {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend.exe"
} else {
    $BackendExe = Join-Path $BackendDir "dist\luominest-backend"
}

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

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

Write-Host ""
Write-Host "[Step 2/6] Verifying backend executable..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[ERROR] Backend executable not found: $BackendExe" -ForegroundColor Red
    Write-Host "The backend build may have failed. Check the build output above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 3/6] Creating distribution directory..." -ForegroundColor Yellow
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "backend") | Out-Null

Write-Host ""
Write-Host "[Step 4/6] Copying backend to distribution and frontend resources..." -ForegroundColor Yellow
Copy-Item $BackendExe (Join-Path $DistDir "backend\") -Force

if (-not (Test-Path $ResourcesBackend)) {
    New-Item -ItemType Directory -Force -Path $ResourcesBackend | Out-Null
}
Copy-Item $BackendExe $ResourcesBackend -Force

Write-Host ""
Write-Host "[Step 5/6] Building frontend with electron-vite..." -ForegroundColor Yellow
Set-Location $FrontendDir
& pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 6/6] Creating installer packages..." -ForegroundColor Yellow
switch ($Platform) {
    "mac" {
        Write-Host "Building macOS DMG + zip..." -ForegroundColor Yellow
        & pnpm exec electron-builder --mac
    }
    "linux" {
        Write-Host "Building Linux AppImage + deb + tar.gz..." -ForegroundColor Yellow
        & pnpm exec electron-builder --linux
    }
    default {
        Write-Host "Building Windows NSIS + portable..." -ForegroundColor Yellow
        & pnpm exec electron-builder --win
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Installer creation failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " All-in-One build completed!" -ForegroundColor Green
Write-Host " Platform: $Platform" -ForegroundColor Green
Write-Host " Output: $FrontendDir\release\dist\" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Set-Location $ProjectRoot
