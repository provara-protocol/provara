@echo off
REM backup_vault.bat — Double-click to back up your Memory Vault
REM
REM This is a simple wrapper around backup_vault.ps1.
REM You can also run it from Command Prompt:
REM   backup_vault.bat
REM   backup_vault.bat C:\Vaults\Mine D:\Backups

set "SCRIPT_DIR=%~dp0"

if "%~1"=="" (
    powershell.exe -ExecutionPolicy Bypass -File "%SCRIPT_DIR%backup_vault.ps1"
) else if "%~2"=="" (
    powershell.exe -ExecutionPolicy Bypass -File "%SCRIPT_DIR%backup_vault.ps1" -VaultPath "%~1"
) else (
    powershell.exe -ExecutionPolicy Bypass -File "%SCRIPT_DIR%backup_vault.ps1" -VaultPath "%~1" -BackupDir "%~2"
)

pause
