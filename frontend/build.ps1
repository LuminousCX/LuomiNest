$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  LuomiNest Inno Setup Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Setting up mirror acceleration..." -ForegroundColor Yellow
$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
Write-Host "[OK] Mirror configured" -ForegroundColor Green

Write-Host ""
Write-Host "[2/4] Building application..." -ForegroundColor Yellow
pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[3/4] Packing files..." -ForegroundColor Yellow
pnpm exec electron-builder --win --dir
if ($LASTEXITCODE -ne 0) {
    Write-Host "Pack failed!" -ForegroundColor Red
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
    Write-Host "Inno Setup build failed!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor White
Write-Host "  - Installer: release\installer\LuomiNest-Setup-0.2.0.exe" -ForegroundColor Cyan
Write-Host "  - Portable:  release\dist\LuomiNest 0.2.0.exe" -ForegroundColor Cyan
Write-Host ""

Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
