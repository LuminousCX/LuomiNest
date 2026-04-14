$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"
$BackendDir = Join-Path $ProjectRoot "backend"
$DistDir = Join-Path $ProjectRoot "dist"

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
$BackendExe = Join-Path $BackendDir "dist\luominest-backend.exe"
Copy-Item $BackendExe (Join-Path $DistDir "backend\") -Force

Write-Host ""
Write-Host "[Step 4/5] Building frontend with embedded backend..." -ForegroundColor Yellow
Set-Location $FrontendDir

$ResourcesBackend = Join-Path $FrontendDir "resources\backend"
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
Write-Host "[Step 5/5] Creating installer..." -ForegroundColor Yellow
& pnpm run build:installer
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Installer creation failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " All-in-One build completed!" -ForegroundColor Green
Write-Host " Installer: $FrontendDir\release\" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

Set-Location $ProjectRoot
