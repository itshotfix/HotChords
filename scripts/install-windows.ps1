<#
.SYNOPSIS
    Optional one-command installer for HotChords on Windows (x64).
.DESCRIPTION
    Downloads the official HotChords Windows x64 installer from GitHub Releases,
    verifies its SHA-256 checksum before execution, and launches the installer.
    Primary installation remains downloading and double-clicking the .exe installer.
#>

[CmdletBinding()]
param(
    [string]$Version = "0.5.0",
    [string]$ExpectedSha256 = ""
)

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "HotChords v$Version - Optional Windows Installer"

if (-not [Environment]::Is64BitOperatingSystem) {
    Write-Error "HotChords requires 64-bit Windows (x64)."
    exit 1
}

$arch = $env:PROCESSOR_ARCHITECTURE
if ($arch -ne "AMD64" -and $env:PROCESSOR_ARCHITEW6432 -ne "AMD64") {
    Write-Error "Unsupported CPU architecture ($arch). Windows x64 (AMD64) is required."
    exit 1
}

$repo = "itshotfix/HotChords"
$assetName = "HotChords-v$Version-Windows-x64-Setup.exe"
$installerUrl = "https://github.com/$repo/releases/download/v$Version/$assetName"
$shaUrl = "https://github.com/$repo/releases/download/v$Version/installer_sha256.txt"

$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("hotchords-install-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

try {
    $installerPath = Join-Path $tempDir $assetName
    $shaPath = Join-Path $tempDir "installer_sha256.txt"

    Write-Host "Downloading $assetName from official GitHub Releases..."
    try {
        Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath -UseBasicParsing
    } catch {
        Write-Error "Failed to download $installerUrl. Ensure release v$Version is published at https://github.com/$repo/releases"
        exit 1
    }

    if ([string]::IsNullOrWhiteSpace($ExpectedSha256)) {
        try {
            Invoke-WebRequest -Uri $shaUrl -OutFile $shaPath -UseBasicParsing
            $shaLine = (Get-Content -Path $shaPath -TotalCount 1).Trim()
            if ($shaLine -match "^([a-fA-F0-9]{64})\b") {
                $ExpectedSha256 = $matches[1].ToLower()
            }
        } catch {
            # Handled below if ExpectedSha256 remains empty
        }
    }

    if ([string]::IsNullOrWhiteSpace($ExpectedSha256)) {
        Write-Error "No SHA-256 checksum available to verify $assetName. Aborting before execution."
        exit 1
    }

    $actualSha256 = (Get-FileHash -Algorithm SHA256 -Path $installerPath).Hash.ToLower()
    if ($actualSha256 -ne $ExpectedSha256.ToLower()) {
        Write-Error "SHA-256 checksum mismatch! Expected $ExpectedSha256, got $actualSha256. Aborting."
        exit 1
    }

    Write-Host "SHA-256 checksum verified: $actualSha256"
    Write-Host "Launching HotChords installer (user data and settings are preserved across upgrades)..."
    $proc = Start-Process -FilePath $installerPath -Wait -PassThru
    if ($proc.ExitCode -ne 0) {
        Write-Error "Installer exited with code $($proc.ExitCode)."
        exit $proc.ExitCode
    }

    Write-Host "HotChords v$Version setup finished."
} finally {
    if (Test-Path $tempDir) {
        Remove-Item -Path $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    }
}
