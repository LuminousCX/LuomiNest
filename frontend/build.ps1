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
    $BackendExe = Join-Path $BackendDir "dist/luominest-backend"
}

$env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"

if ($Platform -eq "win") {
    Write-Host "Pre-check: Stopping leftover processes..." -ForegroundColor Gray
    Stop-Process -Name "LuomiNest" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "electron" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Write-Host "Pre-check: Cleaning old release directory..." -ForegroundColor Gray
    Remove-Item -Recurse -Force (Join-Path $FrontendDir "release") -ErrorAction SilentlyContinue
}

Write-Host "[1/5] Checking backend executable..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[1/5] Backend not found, building backend..." -ForegroundColor Yellow
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
    Write-Host "[1/5] Backend executable found" -ForegroundColor Green
}

Write-Host ""
Write-Host "[2/5] Verifying and preparing backend resources..." -ForegroundColor Yellow
if (-not (Test-Path $BackendExe)) {
    Write-Host "[ERROR] Backend executable not found after build: $BackendExe" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $ResourcesBackend)) {
    New-Item -ItemType Directory -Force -Path $ResourcesBackend | Out-Null
}
Copy-Item $BackendExe $ResourcesBackend -Force
Write-Host "[2/5] Backend resources ready" -ForegroundColor Green

Write-Host ""
Write-Host "[3/5] Building frontend..." -ForegroundColor Yellow
Set-Location $FrontendDir
& pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed" -ForegroundColor Red
    exit 1
}
Write-Host "[3/5] Frontend build complete" -ForegroundColor Green

Write-Host ""
Write-Host "[4/5] Creating portable package..." -ForegroundColor Yellow
switch ($Platform) {
    "mac" { & pnpm exec electron-builder --mac }
    "linux" { & pnpm exec electron-builder --linux AppImage deb rpm }
    default { & pnpm exec electron-builder --win }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Portable package creation failed" -ForegroundColor Red
    exit 1
}
Write-Host "[4/5] Portable package created" -ForegroundColor Green

Write-Host ""
Write-Host "[5/5] Creating Inno Setup installer..." -ForegroundColor Yellow
if ($Platform -eq "win") {
    $innoSetupPath = Get-Command "iscc" -ErrorAction SilentlyContinue
    if (-not $innoSetupPath) {
        @(
            "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
        ) | ForEach-Object {
            if (Test-Path $_) { $innoSetupPath = $_; break }
        }
    }

    if ($innoSetupPath) {
        & $innoSetupPath "installer.iss"
        if ($LASTEXITCODE -ne 0) {
            Write-Host "[ERROR] Inno Setup installer creation failed" -ForegroundColor Red
            exit 1
        }
        Write-Host "[5/5] Inno Setup installer created" -ForegroundColor Green
    } else {
        Write-Host "[WARNING] Inno Setup not found, skipping installer" -ForegroundColor Yellow
    }
} else {
    Write-Host "[5/5] Skipping Inno Setup (Windows only)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Output files:" -ForegroundColor White
Write-Host ""

$InstallerDir = Join-Path $FrontendDir "release\installer"
$ReleaseDir = Join-Path $FrontendDir "release\dist"

Write-Host "  Installer (Inno Setup):" -ForegroundColor Cyan
Get-ChildItem "$InstallerDir\*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 2)
    Write-Host "    $($_.Name) ($size MB)" -ForegroundColor Green
}

Write-Host ""
Write-Host "  Portable:" -ForegroundColor Cyan
Get-ChildItem "$ReleaseDir\*.exe" -ErrorAction SilentlyContinue | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 2)
    Write-Host "    $($_.Name) ($size MB)" -ForegroundColor Green
}
Write-Host ""
