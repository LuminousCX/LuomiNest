$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  LuomiNest Inno Setup Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$FrontendDir = $PSScriptRoot
$ProjectRoot = Split-Path -Parent $FrontendDir
$BackendDir = Join-Path $ProjectRoot "backend"
$BackendExe = Join-Path $BackendDir "dist\luominest-backend.exe"
$ResourcesBackend = Join-Path $FrontendDir "resources\backend"

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

Write-Host "[1/4] Checking backend executable..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[1/4] Backend not found, building backend..." -ForegroundColor Yellow
    Set-Location $BackendDir
    & ".\build.bat"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Backend build failed" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "[1/4] Backend executable found" -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/4] Preparing backend resources and building frontend..." -ForegroundColor Yellow
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
Write-Host "[3/4] Packing application files..." -ForegroundColor Yellow
& pnpm exec electron-builder --win --dir
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Pack failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/4] Creating Inno Setup installer..." -ForegroundColor Yellow

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

if (-not $innoSetupPath) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  Inno Setup not found!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Inno Setup 6 from:" -ForegroundColor Yellow
    Write-Host "https://jrsoftware.org/isdl.php" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

& $innoSetupPath "installer.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Inno Setup build failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor White
Write-Host "  - Inno Setup Installer: release\installer\LuomiNest-Setup-0.3.0.exe" -ForegroundColor Cyan
Write-Host ""
