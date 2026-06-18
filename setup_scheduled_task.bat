@echo off
REM =============================================================
REM setup_scheduled_task.bat
REM
REM Registers a Windows Task Scheduler job that runs main.py
REM automatically once a week. Run this file ONCE as Administrator
REM (right-click -> "Run as administrator") to set it up.
REM
REM To change the schedule later, open Task Scheduler (search for
REM "Task Scheduler" in the Start menu) and find the task named
REM "DesktopAutomationWeekly".
REM =============================================================

setlocal

REM --- EDIT THESE TWO LINES IF YOUR PATHS ARE DIFFERENT ---
set PROJECT_DIR=%~dp0
set PYTHON_PATH=python

echo.
echo Registering weekly task "DesktopAutomationWeekly"...
echo Project folder: %PROJECT_DIR%
echo.

schtasks /create ^
  /tn "DesktopAutomationWeekly" ^
  /tr "\"%PYTHON_PATH%\" \"%PROJECT_DIR%main.py\"" ^
  /sc weekly ^
  /d SUN ^
  /st 09:00 ^
  /rl HIGHEST ^
  /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Task created. It will run every Sunday at 9:00 AM.
    echo You can verify it in Task Scheduler under "DesktopAutomationWeekly".
) else (
    echo.
    echo FAILED to create the task. Make sure you ran this file as Administrator.
)

echo.
pause
