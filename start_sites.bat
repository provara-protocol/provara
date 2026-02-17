@echo off
REM Start Provara local site servers
REM provara.dev → 3000, provara.app → 8080, huntinformationsystems.com → 5000

start "" /B python -m http.server 3000 --directory "C:\provara\sites\provara.dev"
start "" /B python -m http.server 8080 --directory "C:\provara\sites\provara.app"
start "" /B python -m http.server 5000 --directory "C:\provara\sites\huntinformationsystems.com"
