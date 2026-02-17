@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "CORE_BIN=%SCRIPT_DIR%SNP_Core\bin"
set "PYTHONPATH=%CORE_BIN%"

python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3 not found.
        exit /b 1
    )
    set "PY=python3"
) else (
    set "PY=python"
)

%PY% "%CORE_BIN%\provara.py" %*
