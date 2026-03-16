@echo off
SET VAULT=%~dp0AI_Employee_Vault
SET WATCHERS=%~dp0watchers

echo Starting AI Employee (Silver Tier)...
echo Vault: %VAULT%
echo.

:: Orchestrator (handles Needs_Action + Approved folders)
start "Orchestrator" cmd /k "python %WATCHERS%\orchestrator.py --vault %VAULT%"

:: Gmail watcher
start "Gmail Watcher" cmd /k "python %WATCHERS%\gmail_watcher.py --vault %VAULT%"

:: LinkedIn watcher (uses py -3.13 for Playwright compatibility)
start "LinkedIn Watcher" cmd /k "py -3.13 %WATCHERS%\linkedin_watcher.py --vault %VAULT%"

:: Scheduler (daily/weekly briefings)
start "Scheduler" cmd /k "python %WATCHERS%\scheduler.py --vault %VAULT%"

echo All watchers started. Close individual windows to stop them.
