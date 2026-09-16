@echo off
setlocal
cd /d "%~dp0"

python --version >nul 2>&1
if not errorlevel 1 (
  python server.py
  goto :eof
)

py -3 --version >nul 2>&1
if not errorlevel 1 (
  py -3 server.py
  goto :eof
)

if exist "C:\Program Files\LibreOffice\program\python.exe" (
  "C:\Program Files\LibreOffice\program\python.exe" server.py
  goto :eof
)

echo No se encontro Python 3. Instale Python desde https://www.python.org/
pause
