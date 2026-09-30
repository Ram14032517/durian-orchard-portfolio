@echo off
cd /d "%~dp0"
if /i "%~1"=="notebook" goto notebook
if not exist "%~dp0.venv-portfolio\Scripts\python.exe" (
  echo Run SETUP_PORTFOLIO.ps1 first. Opening the saved notebook instead.
  goto notebook
)
"%~dp0.venv-portfolio\Scripts\python.exe" "%~dp0tools\open_orchard_report.py"
if errorlevel 1 pause
exit /b
:notebook
if not exist "%~dp000_OPEN_ME.ipynb" (
  echo Missing 00_OPEN_ME.ipynb. Keep this launcher in the project folder.
  pause
  exit /b 1
)
where code >nul 2>nul
if errorlevel 1 (
  if exist "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" (
    start "" "%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe" --reuse-window "%~dp000_OPEN_ME.ipynb"
    exit /b
  )
  echo Visual Studio Code was not found.
  echo Open VS Code, press Ctrl+P, and paste this path:
  echo %~dp000_OPEN_ME.ipynb
  pause
  exit /b 1
)
call code --reuse-window "%~dp000_OPEN_ME.ipynb"
