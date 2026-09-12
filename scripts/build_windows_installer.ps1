# ==============================================================================
# HotChords v0.4.0 Windows Installer Build Script
# Targets: Windows 10 & 11 (x64)
# ==============================================================================

[CmdletBinding()]
param (
    [string]$PythonExe = "python"
)

$ErrorActionPreference = "Stop"

Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  Building HotChords v0.4.0 Standalone Windows Installer       " -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$DistDir = Join-Path $ProjectRoot "dist"
$InstallerOutput = Join-Path $DistDir "HotChords-v0.4.0-Windows-x64-Setup.exe"

Set-Location $ProjectRoot

# 1. Verify Python
Write-Host "`n[1/5] Checking Python environment..." -ForegroundColor Yellow
$PyVersion = & $PythonExe --version 2>&1
Write-Host "  Using: $PyVersion"

# 2. Install Build & Runtime Dependencies
Write-Host "`n[2/5] Installing dependencies & PyInstaller..." -ForegroundColor Yellow
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r requirements.txt
& $PythonExe -m pip install pyinstaller

# 3. Clean previous build artifacts
Write-Host "`n[3/5] Cleaning previous build staging..." -ForegroundColor Yellow
if (Test-Path (Join-Path $DistDir "HotChords")) {
    Remove-Item -Recurse -Force (Join-Path $DistDir "HotChords")
}
if (Test-Path (Join-Path $ProjectRoot "build")) {
    Remove-Item -Recurse -Force (Join-Path $ProjectRoot "build")
}

# 4. Run PyInstaller
Write-Host "`n[4/5] Bundling application with PyInstaller..." -ForegroundColor Yellow
& $PythonExe -m PyInstaller `
    --noconfirm `
    --onedir `
    --windowed `
    --name "HotChords" `
    --add-data "frontend;frontend" `
    --hidden-import "uvicorn.logging" `
    --hidden-import "uvicorn.loops" `
    --hidden-import "uvicorn.loops.auto" `
    --hidden-import "uvicorn.protocols" `
    --hidden-import "uvicorn.protocols.http" `
    --hidden-import "uvicorn.protocols.http.auto" `
    --hidden-import "uvicorn.lifespan" `
    --hidden-import "uvicorn.lifespan.on" `
    --hidden-import "soundfile" `
    --hidden-import "imageio_ffmpeg" `
    --hidden-import "scipy.special.cython_special" `
    --collect-all "librosa" `
    --collect-all "imageio_ffmpeg" `
    "hotchords.py"

if (-not (Test-Path (Join-Path $DistDir "HotChords\HotChords.exe"))) {
    Write-Error "PyInstaller build failed: HotChords.exe not found in dist/HotChords"
}

# 5. Compile Inno Setup Installer
Write-Host "`n[5/5] Compiling Inno Setup Windows Installer..." -ForegroundColor Yellow
$IsccPaths = @(
    "iscc",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "${env:LOCALAPPDATA}\Programs\Inno Setup 6\ISCC.exe"
)

$IsccExe = $null
foreach ($path in $IsccPaths) {
    if (Get-Command $path -ErrorAction SilentlyContinue) {
        $IsccExe = $path
        break
    }
    if (Test-Path $path) {
        $IsccExe = $path
        break
    }
}

if (-not $IsccExe) {
    Write-Warning "Inno Setup Compiler (ISCC.exe) not found in PATH or standard locations."
    Write-Host "Please install Inno Setup 6 (e.g. via 'choco install innosetup' or from https://jrsoftware.org/isdl.php)"
    Write-Host "Standalone executable bundle is ready at: $(Join-Path $DistDir 'HotChords')"
    exit 0
}

Write-Host "  Using ISCC: $IsccExe"
& $IsccExe (Join-Path $ScriptDir "hotchords.iss")

if (Test-Path $InstallerOutput) {
    $Hash = (Get-FileHash -Algorithm SHA256 $InstallerOutput).Hash.ToLower()
    $SizeMB = [math]::Round((Get-Item $InstallerOutput).Length / 1MB, 2)
    Write-Host "`n═══════════════════════════════════════════════════════════════" -ForegroundColor Green
    Write-Host "  HotChords Windows Installer Successfully Built!" -ForegroundColor Green
    Write-Host "  File:   $InstallerOutput" -ForegroundColor Green
    Write-Host "  Size:   $SizeMB MB" -ForegroundColor Green
    Write-Host "  SHA256: $Hash" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Green
} else {
    Write-Error "Inno Setup compilation failed to produce installer."
}
