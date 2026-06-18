@echo off
REM =============================================================
REM build_exe.bat
REM
REM Packages main.py into a standalone Windows .exe using PyInstaller,
REM so the tool can run on a machine with NO Python installed.
REM
REM IMPORTANT: Run this ON WINDOWS. PyInstaller is not a cross-compiler —
REM it can only build a Windows .exe when run from Windows itself.
REM This script cannot be run inside a Linux/Mac build environment to
REM produce a Windows .exe.
REM
REM USAGE:
REM   1. Open Command Prompt in this project folder.
REM   2. Run:  build_exe.bat
REM   3. Find the result in:  dist\DesktopAutomation.exe
REM =============================================================

setlocal

echo.
echo Installing PyInstaller (if not already installed)...
pip install pyinstaller --quiet

echo.
echo Building standalone executable...
echo This may take a minute or two.
echo.

pyinstaller --onefile ^
  --name DesktopAutomation ^
  --add-data "config;config" ^
  --console ^
  main.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Build complete.
    echo Your standalone executable is at: dist\DesktopAutomation.exe
    echo.
    echo You can now run it directly, e.g.:
    echo   dist\DesktopAutomation.exe --dry-run
    echo.
    echo NOTE: Copy the config\rules.yaml file alongside the exe if you
    echo move it to a different folder, or pass --config with a full path.
) else (
    echo.
    echo BUILD FAILED. Check the error output above.
)

echo.
pause
