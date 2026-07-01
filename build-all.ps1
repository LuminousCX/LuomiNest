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

# ============================================================
# Pre-check: INNO Setup 6 (winget auto-install, Ollama-style installer)
# ============================================================
# winget 可能安装到 per-machine (Program Files) 或 per-user (LocalAppData) 位置
$InnoSetupCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6",
    "${env:ProgramFiles}\Inno Setup 6",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6"
)
$InnoSetupDir = $InnoSetupCandidates | Where-Object { Test-Path "$_\ISCC.exe" } | Select-Object -First 1
if (-not $InnoSetupDir) {
    Write-Host "INNO Setup 6 not found, installing via winget..." -ForegroundColor Yellow
    & winget install --id JRSoftware.InnoSetup --silent --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] INNO Setup install failed" -ForegroundColor Red
        exit 1
    }
    $InnoSetupDir = $InnoSetupCandidates | Where-Object { Test-Path "$_\ISCC.exe" } | Select-Object -First 1
    if (-not $InnoSetupDir) {
        Write-Host "[ERROR] INNO Setup installed but ISCC.exe not found in expected paths" -ForegroundColor Red
        exit 1
    }
}
$Iscc = Join-Path $InnoSetupDir "ISCC.exe"
Write-Host "INNO Setup compiler: $Iscc" -ForegroundColor Green

$startTime = Get-Date

if ($Platform -eq "win") {
    Write-Host "Pre-check: Stopping leftover LuomiNest processes..." -ForegroundColor Gray
    Stop-Process -Name "LuomiNest" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "electron" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    Write-Host "Pre-check: Cleaning old release directory..." -ForegroundColor Gray
    Remove-Item -Recurse -Force (Join-Path $FrontendDir "release") -ErrorAction SilentlyContinue
}

# 清理陈旧 PyInstaller 产物，避免 _internal 残留与当前 spec 不一致
Write-Host "Pre-check: Cleaning stale PyInstaller output..." -ForegroundColor Gray
Remove-Item -Recurse -Force (Join-Path $BackendDir "dist") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $BackendDir "build") -ErrorAction SilentlyContinue

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
# Step 1.5: Verify TTS model
# ============================================================
Write-Host ""
Write-Host "[Step 1.5/5] Verifying TTS model..." -ForegroundColor Yellow
$TtsModelDir = Join-Path $BackendDir "models\tts\vits-melo-tts-zh_en"
$TtsModelFile = Join-Path $TtsModelDir "model.onnx"
if (-not (Test-Path $TtsModelFile)) {
    Write-Host "[ERROR] TTS model not found: $TtsModelFile" -ForegroundColor Red
    Write-Host "Please download vits-melo-tts-zh_en from:" -ForegroundColor Gray
    Write-Host "  https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-melo-tts-zh_en.tar.bz2" -ForegroundColor Gray
    exit 1
}
$ModelSize = (Get-Item $TtsModelFile).Length
if ($ModelSize -lt 100MB) {
    Write-Host "[ERROR] TTS model file corrupted (size: $([math]::Round($ModelSize/1MB,2)) MB, expected ~162 MB)" -ForegroundColor Red
    exit 1
}
Write-Host "TTS model OK: $([math]::Round($ModelSize/1MB,2)) MB" -ForegroundColor Green

# 删除损坏的 int8 模型（官方无 int8 发布版，0 字节是下载残留）
$Int8File = Join-Path $TtsModelDir "model.int8.onnx"
if (Test-Path $Int8File) {
    $Int8Size = (Get-Item $Int8File).Length
    if ($Int8Size -lt 1MB) {
        Write-Host "Removing corrupted model.int8.onnx ($Int8Size bytes)" -ForegroundColor Gray
        Remove-Item $Int8File -Force
    }
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

# 清理不应被打包的运行时数据：SQLite 预建库、WAL/SHM、secret_key
# 首次启动时由后端 init_db() 建表 + secret_key_manager 自动生成，避免状态不一致与密钥泄露。
$BackendDataDir = Join-Path $ResourcesBackend "data"
if (Test-Path $BackendDataDir) {
    Write-Host "Cleaning prebuilt backend data (db/wal/shm/secret_key)..." -ForegroundColor Gray
    Remove-Item -Recurse -Force $BackendDataDir -ErrorAction SilentlyContinue
}

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
# Step 4: Package with electron-builder (win-unpacked) + INNO Setup
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
        # electron-builder 产出 win-unpacked 目录（dir target），INNO Setup 接管安装器编译
        & pnpm exec electron-builder --win dir
    }
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Package creation failed" -ForegroundColor Red
    exit 1
}
Write-Host "Platform packages created" -ForegroundColor Green

# Windows: 用 INNO Setup 编译 Ollama 风格安装器
if ($Platform -eq "win") {
    $WinUnpacked = Join-Path $ReleaseDir "win-unpacked"
    if (-not (Test-Path $WinUnpacked)) {
        Write-Host "[ERROR] win-unpacked not found: $WinUnpacked" -ForegroundColor Red
        exit 1
    }
    Write-Host "Compiling INNO Setup installer..." -ForegroundColor Yellow
    Set-Location $FrontendDir
    & $Iscc "build\luominest.iss"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] INNO Setup compile failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "INNO Setup installer compiled" -ForegroundColor Green
}

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
Write-Host "Verifying package metadata..." -ForegroundColor Yellow
$SetupExe = Get-ChildItem "$ReleaseDir\LuomiNest-Setup-*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($SetupExe) {
    $VersionInfo = $SetupExe.VersionInfo
    Write-Host "  ProductName:     $($VersionInfo.ProductName)" -ForegroundColor Gray
    Write-Host "  FileDescription: $($VersionInfo.FileDescription)" -ForegroundColor Gray
    Write-Host "  CompanyName:     $($VersionInfo.CompanyName)" -ForegroundColor Gray
    Write-Host "  FileVersion:    $($VersionInfo.FileVersion)" -ForegroundColor Gray
    if ($VersionInfo.ProductName -ne "LuomiNest") {
        Write-Host "[WARNING] ProductName mismatch: expected 'LuomiNest', got '$($VersionInfo.ProductName)'" -ForegroundColor Yellow
    }
} else {
    Write-Host "[WARNING] No setup exe found for metadata verification" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Cross-platform builds (Linux/macOS/Windows):" -ForegroundColor Cyan
Write-Host "  Push a tag (v*) to trigger GitHub Actions release.yml" -ForegroundColor Gray
Write-Host "  Or run: gh workflow run release.yml" -ForegroundColor Gray

Set-Location $ProjectRoot
