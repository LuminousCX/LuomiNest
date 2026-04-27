$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Platform = "win"
if ($IsMacOS) { $Platform = "mac" }
elseif ($IsLinux) { $Platform = "linux" }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " LuomiNest Unified Build Script" -ForegroundColor Cyan
Write-Host " Platform: $Platform" -ForegroundColor Cyan
Write-Host " Targets: Win (NSIS+Portable) / Linux (AppImage+deb+rpm)" -ForegroundColor Cyan
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

$startTime = Get-Date

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
Copy-Item $BackendExe $ResourcesBackend -Force
Write-Host "Backend resources copied" -ForegroundColor Green

Write-Host ""
Write-Host "[Step 3/5] Building frontend with electron-vite..." -ForegroundColor Yellow
Set-Location $FrontendDir
& pnpm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Frontend build failed" -ForegroundColor Red
    exit 1
}
Write-Host "Frontend build complete" -ForegroundColor Green

Write-Host ""
Write-Host "[Step 4/5] Creating installer packages (electron-builder)..." -ForegroundColor Yellow
switch ($Platform) {
    "mac" {
        Write-Host "Building macOS DMG + zip..." -ForegroundColor Yellow
        & pnpm exec electron-builder --mac
    }
    "linux" {
        Write-Host "Building Linux AppImage + deb + rpm..." -ForegroundColor Yellow
        & pnpm exec electron-builder --linux AppImage deb rpm
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
Write-Host "Electron-builder packages created" -ForegroundColor Green

Write-Host ""
Write-Host "[Step 5/5] Checking for Inno Setup (Windows only)..." -ForegroundColor Yellow
if ($Platform -eq "win") {
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

    if ($innoSetupPath) {
        Write-Host "Inno Setup found, creating Ollama-style installer..." -ForegroundColor Yellow
        & $innoSetupPath "installer.iss"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Inno Setup installer created" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] Inno Setup build failed, NSIS packages are ready" -ForegroundColor Yellow
        }
    } else {
        Write-Host "Inno Setup not found, skipping" -ForegroundColor Gray
    }
}

$endTime = Get-Date
$duration = $endTime - $startTime

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Build completed!" -ForegroundColor Green
Write-Host " Platform: $Platform" -ForegroundColor Green
Write-Host " Duration: $($duration.ToString('mm\:ss'))" -ForegroundColor Green
Write-Host " Output: $FrontendDir\release\" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "Generated packages:" -ForegroundColor Magenta
Get-ChildItem "$FrontendDir\release\dist\*" -ErrorAction SilentlyContinue | ForEach-Object {
    $size = [math]::Round($_.Length / 1MB, 2)
    Write-Host "  $($_.Name) ($size MB)" -ForegroundColor Green
}

Set-Location $ProjectRoot
