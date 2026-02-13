@echo off
REM check_backpack.bat — Verify the integrity of an existing Memory Vault
REM
REM Double-click this file, or run from Command Prompt:
REM   check_backpack.bat                   (checks .\My_Backpack)
REM   check_backpack.bat C:\Vaults\mine    (checks custom path)

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "CORE_BIN=%SCRIPT_DIR%SNP_Core\bin"
set "CORE_TEST=%SCRIPT_DIR%SNP_Core\test"

if "%~1"=="" (
    set "TARGET=%SCRIPT_DIR%My_Backpack"
) else (
    set "TARGET=%~1"
)

echo.
echo ========================================
echo    Memory Vault — Integrity Check
echo ========================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3 is required.
        pause
        exit /b 1
    )
    set "PY=python3"
) else (
    set "PY=python"
)

if not exist "%TARGET%" (
    echo ERROR: No vault found at %TARGET%
    echo Run init_backpack.bat first.
    pause
    exit /b 1
)

echo   Checking: %TARGET%
echo.

set "PYTHONPATH=%CORE_BIN%"
%PY% "%CORE_TEST%\backpack_compliance_v1.py" "%TARGET%" -v

if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo   All 17 integrity checks passed.
    echo   Your vault has not been tampered with.
    echo ================================================
) else (
    echo.
    echo ================================================
    echo   INTEGRITY CHECK FAILED.
    echo   See errors above.
    echo   If you have a backup, restore from it.
    echo   See Recovery\WHAT_TO_DO.md for help.
    echo ================================================
)

echo.
pause
