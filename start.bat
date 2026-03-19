@echo off
SETLOCAL
SET "ROOT=%~dp0"
SET "VAULT=%ROOT%AI_Employee_Vault"
SET "WATCHERS=%ROOT%watchers"
SET "BACKEND=%ROOT%backend"
SET "FRONTEND=%ROOT%frontend"
SET "WHATSAPP=%ROOT%whatsapp-baileys"

echo.
echo  ================================================================
echo    AI Employee Digital FTE — Gold Tier
echo    Starting all services...
echo  ================================================================
echo.
echo  Vault:     %VAULT%
echo  Agent:     %AGENT% (set AGENT in .env to switch: claude / gemini / qwen)
echo.

:: ── Dashboard Backend (FastAPI on port 8000) ─────────────────────────────────
echo [1/9] Starting Dashboard Backend (FastAPI :8000)...
start "Dashboard API" cmd /k "cd /d "%BACKEND%" && call .venv\Scripts\activate && uvicorn main:app --reload --port 8000"
timeout /t 3 /nobreak >nul

:: ── Dashboard Frontend (Next.js on port 3000) ────────────────────────────────
echo [2/9] Starting Dashboard Frontend (Next.js :3000)...
start "Dashboard UI" cmd /k "cd /d "%FRONTEND%" && npm run dev"

:: ── WhatsApp Baileys (HTTP API on port 3001) ─────────────────────────────────
echo [3/9] Starting WhatsApp Baileys Watcher (:3001)...
start "WhatsApp Baileys" cmd /k "cd /d "%WHATSAPP%" && node index.js --vault "%VAULT%""

:: ── Orchestrator ─────────────────────────────────────────────────────────────
echo [4/9] Starting Orchestrator...
start "Orchestrator" cmd /k "call "%ROOT%.venv\Scripts\activate" && python "%WATCHERS%\orchestrator.py" --vault "%VAULT%""

:: ── Gmail Watcher ────────────────────────────────────────────────────────────
echo [5/9] Starting Gmail Watcher...
start "Gmail Watcher" cmd /k "call "%ROOT%.venv\Scripts\activate" && python "%WATCHERS%\gmail_watcher.py" --vault "%VAULT%""

:: ── LinkedIn Watcher ─────────────────────────────────────────────────────────
echo [6/9] Starting LinkedIn Watcher...
start "LinkedIn Watcher" cmd /k "call "%ROOT%.venv\Scripts\activate" && python "%WATCHERS%\linkedin_watcher.py" --vault "%VAULT%""

:: ── Twitter/X Watcher ────────────────────────────────────────────────────────
echo [7/9] Starting Twitter Watcher...
start "Twitter Watcher" cmd /k "call "%ROOT%.venv\Scripts\activate" && python "%WATCHERS%\twitter_watcher.py" --vault "%VAULT%""

:: ── Facebook + Instagram Watcher ─────────────────────────────────────────────
echo [8/9] Starting Facebook Watcher...
start "Facebook Watcher" cmd /k "call "%ROOT%.venv\Scripts\activate" && python "%WATCHERS%\facebook_watcher.py" --vault "%VAULT%""

:: ── ERPNext Watcher ──────────────────────────────────────────────────────────
echo [9/9] Starting ERPNext Watcher...
start "ERPNext Watcher" cmd /k "call "%ROOT%.venv\Scripts\activate" && python "%WATCHERS%\erpnext_watcher.py" --vault "%VAULT%""

echo.
echo  ================================================================
echo    All 9 services started!
echo.
echo    Dashboard:  http://localhost:3000
echo    API Docs:   http://localhost:8000/docs
echo    WhatsApp:   http://localhost:3001/status
echo.
echo    Close individual CMD windows to stop services.
echo  ================================================================
echo.
ENDLOCAL
