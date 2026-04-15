$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$DistDir = Join-Path $ProjectRoot "dist"
$BackendExe = Join-Path $BackendDir "dist\luominest-backend.exe"
$ResourcesBackend = Join-Path $FrontendDir "resources\backend"

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " LuomiNest All-in-One Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[Step 1/5] Building backend..." -ForegroundColor Yellow
Set-Location $BackendDir
& ".\build.bat"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Backend build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 2/5] Creating distribution directory..." -ForegroundColor Yellow
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir }
New-Item -ItemType Directory -Force -Path $DistDir | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $DistDir "backend") | Out-Null

Write-Host ""
Write-Host "[Step 3/5] Copying backend to distribution..." -ForegroundColor Yellow
Copy-Item $BackendExe (Join-Path $DistDir "backend\") -Force

Write-Host ""
Write-Host "[Step 4/5] Preparing frontend resources and building..." -ForegroundColor Yellow
Set-Location $FrontendDir

if (-not (Test-Path $ResourcesBackend)) {
    New-Item -ItemType Directory -Force -Path $ResourcesBackend | Out-Null
}
Copy-Item $BackendExe $ResourcesBackend -Force

& pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[Step 5/5] Creating installer packages..." -ForegroundColor Yellow
& pnpm exec electron-builder --win
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Installer creation failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " All-in-One build completed!" -ForegroundColor Green
Write-Host " NSIS Installer: $FrontendDir\release\dist\" -ForegroundColor Green
Write-Host " Portable:       $FrontendDir\release\dist\" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Set-Location $ProjectRoot
