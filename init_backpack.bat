@echo off
REM init_backpack.bat — Create a new Memory Vault (Backpack v1.0)
REM
REM Double-click this file, or run from Command Prompt:
REM   init_backpack.bat              (creates .\My_Backpack)
REM   init_backpack.bat C:\Vaults\me (creates at custom path)
REM
REM Requirements: Python 3.10+ from https://python.org
REM   During install, CHECK "Add Python to PATH"

setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "CORE_BIN=%SCRIPT_DIR%SNP_Core\bin"
set "CORE_TEST=%SCRIPT_DIR%SNP_Core\test"
set "KEYS_FILE=%SCRIPT_DIR%my_private_keys.json"

if "%~1"=="" (
    set "TARGET=%SCRIPT_DIR%My_Backpack"
) else (
    set "TARGET=%~1"
)

echo.
echo ========================================
echo    Memory Vault — First Time Setup
echo ========================================
echo.

REM --- Check Python ---
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3 is required but not found.
        echo.
        echo Download it from https://python.org
        echo During installation, CHECK the box "Add Python to PATH"
        echo Then restart this script.
        echo.
        pause
        exit /b 1
    )
    set "PY=python3"
) else (
    set "PY=python"
)

for /f "tokens=*" %%v in ('%PY% -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"') do set PYVER=%%v
echo   Python: %PYVER%

REM --- Check cryptography library ---
%PY% -c "import cryptography" >nul 2>&1
if errorlevel 1 (
    echo   Installing required library...
    %PY% -m pip install cryptography --quiet >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Could not install 'cryptography' package.
        echo Run:  pip install cryptography
        pause
        exit /b 1
    )
)
echo   Crypto library: OK

REM --- Check target ---
if exist "%TARGET%\*" (
    dir /a /b "%TARGET%" 2>nul | findstr "." >nul
    if not errorlevel 1 (
        echo.
        echo ERROR: %TARGET% already exists and is not empty.
        echo Choose a different location or remove the existing folder.
        pause
        exit /b 1
    )
)

REM --- Check core ---
if not exist "%CORE_BIN%\bootstrap_v0.py" (
    echo ERROR: SNP_Core not found at %CORE_BIN%
    echo Make sure the Legacy Kit folder structure is intact.
    pause
    exit /b 1
)

echo.
echo   Creating vault at: %TARGET%
echo.

REM --- Bootstrap ---
set "PYTHONPATH=%CORE_BIN%"
%PY% "%CORE_BIN%\bootstrap_v0.py" "%TARGET%" --quorum --private-keys "%KEYS_FILE%" --self-test

if %errorlevel% equ 0 (
    echo.
    echo ================================================
    echo   Your Memory Vault has been created.
    echo   All 17 integrity checks passed.
    echo ================================================
    echo.
    echo   IMPORTANT: Your private keys are in:
    echo   %KEYS_FILE%
    echo.
    echo   1. Move this file to your password manager or a safe place.
    echo   2. Delete it from this folder after you've secured it.
    echo   3. If you lose these keys, you lose ownership of this vault.
    echo.
    echo   Your vault is at: %TARGET%
    echo.
) else (
    echo.
    echo ================================================
    echo   Something went wrong during setup.
    echo ================================================
    echo.
    echo   Check the error messages above.
    echo   If you need help, see Recovery\WHAT_TO_DO.md
)

pause
