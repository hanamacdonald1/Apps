@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
start "Hana AI background worker" /D "%~dp0" ".venv\Scripts\python.exe" worker.py
.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
pause
exit /b
:fail
echo Setup failed. Install Python 3.11+ from python.org and enable Add Python to PATH.
pause
exit /b 1
