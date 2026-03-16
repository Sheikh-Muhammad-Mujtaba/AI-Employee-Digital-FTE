@echo off
SET "VAULT=%~dp0AI_Employee_Vault"
SET "WATCHERS=%~dp0watchers"

echo Starting AI Employee (Gold Tier)...
echo Vault: %VAULT%

:: Orchestrator (handles Needs_Action + Approved folders)
start "Orchestrator" cmd /k "python "%WATCHERS%\orchestrator.py" --vault "%VAULT%""

:: Gmail watcher
start "Gmail Watcher" cmd /k "python "%WATCHERS%\gmail_watcher.py" --vault "%VAULT%""

:: LinkedIn watcher
start "LinkedIn Watcher" cmd /k "py -3.13 "%WATCHERS%\linkedin_watcher.py" --vault "%VAULT%""

:: Twitter/X watcher
start "Twitter Watcher" cmd /k "python "%WATCHERS%\twitter_watcher.py" --vault "%VAULT%""

:: Facebook + Instagram watcher
start "Facebook Watcher" cmd /k "python "%WATCHERS%\facebook_watcher.py" --vault "%VAULT%""

:: ERPNext accounting watcher
start "ERPNext Watcher" cmd /k "python "%WATCHERS%\erpnext_watcher.py" --vault "%VAULT%""

:: Scheduler (daily/weekly briefings)
start "Scheduler" cmd /k "python "%WATCHERS%\scheduler.py" --vault "%VAULT%""

echo All watchers started. Close individual windows to stop them.
