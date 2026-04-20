$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  LuomiNest Inno Setup Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$projectRoot = Split-Path -Parent $PSScriptRoot
$frontendPath = Join-Path $projectRoot "frontend"

Set-Location $frontendPath

Write-Host "[1/3] Building Electron app..." -ForegroundColor Yellow
pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "[2/3] Packing application files..." -ForegroundColor Yellow
pnpm exec electron-builder --win --dir
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pack failed!" -ForegroundColor Red
    exit 1
}

Write-Host "[3/3] Creating Inno Setup installer..." -ForegroundColor Yellow

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
    Write-Host "Inno Setup not found! Please install Inno Setup 6 from:" -ForegroundColor Red
    Write-Host "https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    exit 1
}

& $innoSetupPath "installer.iss"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Inno Setup build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Build completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Installer location: $frontendPath\release\installer\" -ForegroundColor Cyan
