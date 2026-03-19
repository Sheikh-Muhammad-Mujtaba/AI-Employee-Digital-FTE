# AI Employee Digital FTE - Dashboard Implementation Plan

## Overview
The goal is to build a full-stack dashboard for the existing AI Employee Digital FTE (Gold Tier). The current system uses an Obsidian Markdown vault (`AI_Employee_Vault`) as its database. The new dashboard will provide a web-based GUI to review tasks, monitor system status, and plan projects, replacing or augmenting the Obsidian interface.

## Tech Stack
Based on project rules:
- **Frontend**: Next.js (App Router), TypeScript, Tailwind CSS. Web3-inspired UI/UX (dark theme, glassmorphism, subtle gradients).
- **Backend**: FastAPI, Python 3.13+, Uvicorn, SQLAlchemy 2.0+, SQLite, JWT Auth (python-jose).
- **Integration**: The backend will read/write from the existing `AI_Employee_Vault` directory to maintain compatibility with the ongoing Claude Orchestrator and Python watchers.

## Architecture

### Backend (FastAPI)
1. **Auth Module**: JWT-based login (hardcoded initial admin user in SQLite).
2. **Vault Service**: Python service to parse markdown files (`Dashboard.md`, `Business_Goals.md`) and list files in operational folders (`/Pending_Approval`, `/Needs_Action`).
3. **API Endpoints**:
   - `GET /api/dashboard/status` - Returns parsed data from `Dashboard.md`.
   - `GET /api/tasks/pending` - Lists approval tasks.
   - `POST /api/tasks/{task_id}/approve` - Moves a task from `/Pending_Approval` to `/Approved`.
   - `GET /api/projects` - Parses `Business_Goals.md`.
   - `POST /api/projects/plan` - Creates a new project plan file in `/Plans`.

### Frontend (Next.js)
1. **Auth Pages**: Login screen.
2. **Dashboard Overview**: Metrics, Recent Activity, System Status (pulled from backend).
3. **Task Review**: Interface to see "Upcoming Actions" and approve/reject them.
4. **Project Planning**: Interface to view and update Q1 Objectives and active projects.

## Verification
- Run FastAPI local server and Next.js dev server.
- Log in via frontend.
- Ensure Dashboard stats match `AI_Employee_Vault/Dashboard.md`.
- Ensure creating a plan from the UI creates a valid markdown file in `AI_Employee_Vault/Plans/`.
