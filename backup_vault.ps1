<#
.SYNOPSIS
    Automated Memory Vault Backup (Windows)

.DESCRIPTION
    Creates a timestamped, integrity-verified backup of your vault.
    Designed to run weekly via Task Scheduler or manually.

    What it does:
      1. Runs 17 integrity checks on the source vault
      2. Creates a timestamped zip: Backup_2026-02-13_143022.zip
      3. Verifies the zip by extracting and re-checking
      4. Writes a SHA-256 hash file alongside the zip
      5. Prunes old backups beyond the retention limit

.PARAMETER VaultPath
    Path to your Memory Vault (default: .\My_Backpack)

.PARAMETER BackupDir
    Where to store backups (default: .\Backups)

.PARAMETER MaxBackups
    How many backups to keep (default: 12, ~3 months weekly)

.EXAMPLE
    .\backup_vault.ps1
    .\backup_vault.ps1 -VaultPath "C:\Vaults\Mine" -BackupDir "D:\Backups"
    .\backup_vault.ps1 -VaultPath ".\My_Backpack" -BackupDir "E:\USB_Backup"

.NOTES
    To automate via Task Scheduler:
      1. Open Task Scheduler
      2. Create Basic Task → "Memory Vault Backup"
      3. Trigger: Weekly, Sunday 3:00 AM
      4. Action: Start a Program
         Program: powershell.exe
         Arguments: -ExecutionPolicy Bypass -File "C:\path\to\backup_vault.ps1"
      5. Finish
#>

param(
    [string]$VaultPath = "",
    [string]$BackupDir = "",
    [int]$MaxBackups = 12
)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $VaultPath) { $VaultPath = Join-Path $ScriptDir "My_Backpack" }
if (-not $BackupDir) { $BackupDir = Join-Path $ScriptDir "Backups" }

$CoreBin  = Join-Path $ScriptDir "SNP_Core\bin"
$CoreTest = Join-Path $ScriptDir "SNP_Core\test"

$Timestamp  = Get-Date -Format "yyyy-MM-dd_HHmmss"
$BackupName = "Backup_$Timestamp"
$BackupZip  = Join-Path $BackupDir "$BackupName.zip"
$BackupHash = Join-Path $BackupDir "$BackupName.sha256"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

function Write-OK   ($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn ($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail ($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red }
function Write-Log  ($msg) { Write-Host "  [backup] $msg" }

# Find Python
$Python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $null = & $cmd --version 2>&1
        $Python = $cmd
        break
    } catch { }
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

Write-Host ""
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host "     Memory Vault — Weekly Backup         " -ForegroundColor Cyan
Write-Host "  ========================================" -ForegroundColor Cyan
Write-Host ""
Write-Log "Source:  $VaultPath"
Write-Log "Target:  $BackupDir"
Write-Log "Time:    $Timestamp"
Write-Host ""

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------

if (-not (Test-Path $VaultPath -PathType Container)) {
    Write-Fail "Vault not found at $VaultPath"
    Write-Host "  Run init_backpack.bat first, or specify the correct path."
    exit 1
}

$EventsFile = Join-Path $VaultPath "events\events.ndjson"
if (-not (Test-Path $EventsFile)) {
    Write-Fail "Not a valid vault (missing events\events.ndjson)"
    exit 1
}

if (-not $Python) {
    Write-Fail "Python 3 required but not found."
    Write-Host "  Install from https://python.org (check 'Add to PATH')"
    exit 1
}

$ComplianceScript = Join-Path $CoreTest "backpack_compliance_v1.py"
if (-not (Test-Path $ComplianceScript)) {
    Write-Fail "SNP_Core test suite not found. Cannot verify integrity."
    exit 1
}

# ---------------------------------------------------------------------------
# Step 1: Pre-backup integrity check
# ---------------------------------------------------------------------------

Write-Log "Step 1/5: Verifying source vault integrity..."

$env:PYTHONPATH = $CoreBin
$PreCheck = & $Python $ComplianceScript $VaultPath 2>&1
$PreExit = $LASTEXITCODE

if ($PreExit -ne 0) {
    Write-Fail "Source vault FAILED integrity checks. Backup aborted."
    Write-Host ""
    Write-Host "  Fix the issue before backing up (see Recovery\WHAT_TO_DO.md)."
    $PreCheck | Where-Object { $_ -match "FAIL|ERROR" } | Select-Object -First 5 | ForEach-Object { Write-Host "  $_" }
    exit 2
}

Write-OK "Source vault: 17/17 checks passed"

# ---------------------------------------------------------------------------
# Step 2: Create backup
# ---------------------------------------------------------------------------

Write-Log "Step 2/5: Creating backup archive..."

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

# Use .NET compression (no external tools needed)
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $VaultPath,
    $BackupZip,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $true  # Include base directory name
)

$BackupSize = (Get-Item $BackupZip).Length
$BackupSizeMB = [math]::Round($BackupSize / 1MB, 2)
Write-OK "Archive created: $BackupZip ($BackupSizeMB MB)"

# ---------------------------------------------------------------------------
# Step 3: Hash the backup
# ---------------------------------------------------------------------------

Write-Log "Step 3/5: Computing SHA-256 hash..."

$SHA = (Get-FileHash -Path $BackupZip -Algorithm SHA256).Hash.ToLower()
Set-Content -Path $BackupHash -Value "$SHA  $(Split-Path $BackupZip -Leaf)"

Write-OK "Hash: $SHA"

# ---------------------------------------------------------------------------
# Step 4: Verify backup
# ---------------------------------------------------------------------------

Write-Log "Step 4/5: Verifying backup integrity..."

$VerifyTmp = Join-Path $env:TEMP "snp_verify_$Timestamp"
try {
    [System.IO.Compression.ZipFile]::ExtractToDirectory($BackupZip, $VerifyTmp)

    # Find the extracted vault (it's inside the base directory)
    $ExtractedVault = Get-ChildItem -Path $VerifyTmp -Directory | Select-Object -First 1
    $ExtractedPath = $ExtractedVault.FullName

    $env:PYTHONPATH = $CoreBin
    $PostCheck = & $Python $ComplianceScript $ExtractedPath 2>&1
    $PostExit = $LASTEXITCODE

    if ($PostExit -ne 0) {
        Write-Fail "Backup FAILED verification after extraction!"
        Write-Host "  The archive may be corrupted. Do NOT rely on it."
        Remove-Item $BackupZip -Force -ErrorAction SilentlyContinue
        Remove-Item $BackupHash -Force -ErrorAction SilentlyContinue
        exit 3
    }

    Write-OK "Backup verified: 17/17 checks passed after extraction"
}
finally {
    if (Test-Path $VerifyTmp) {
        Remove-Item $VerifyTmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ---------------------------------------------------------------------------
# Step 5: Prune old backups
# ---------------------------------------------------------------------------

Write-Log "Step 5/5: Pruning old backups (keeping last $MaxBackups)..."

$AllBackups = Get-ChildItem -Path $BackupDir -Filter "Backup_*.zip" | Sort-Object Name
$BackupCount = $AllBackups.Count

if ($BackupCount -gt $MaxBackups) {
    $PruneCount = $BackupCount - $MaxBackups
    $ToPrune = $AllBackups | Select-Object -First $PruneCount

    foreach ($old in $ToPrune) {
        $oldHash = $old.FullName -replace '\.zip$', '.sha256'
        Remove-Item $old.FullName -Force
        if (Test-Path $oldHash) { Remove-Item $oldHash -Force }
        Write-Log "  Pruned: $($old.Name)"
    }
    Write-OK "Pruned $PruneCount old backup(s)"
}
else {
    Write-OK "No pruning needed ($BackupCount/$MaxBackups slots used)"
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

$FinalCount = (Get-ChildItem -Path $BackupDir -Filter "Backup_*.zip").Count

Write-Host ""
Write-Host "  ================================================" -ForegroundColor Green
Write-Host "    ✓ Backup complete and verified.                " -ForegroundColor Green
Write-Host "  ================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Archive:  $BackupZip"
Write-Host "  Hash:     $SHA"
Write-Host "  Size:     $BackupSizeMB MB"
Write-Host "  Backups:  $FinalCount/$MaxBackups"
Write-Host ""
