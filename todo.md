# Project Todo List

## Phase 1: Setup & Initialization
- [ ] Initialize `backend` directory with FastAPI structure.
- [ ] Configure Python virtual environment and `requirements.txt` for backend (FastAPI, SQLAlchemy, python-jose, uvicorn, pydantic).
- [ ] Initialize `frontend` directory with Next.js (App Router, Tailwind, TypeScript).
- [ ] Setup frontend styling (Dark mode, CSS variables for glassmorphism).

## Phase 2: Backend Development
- [ ] Setup SQLite database and SQLAlchemy 2.0 models for users.
- [ ] Implement JWT Authentication endpoints (login, register/init).
- [ ] Implement Vault Parser utility (regex/markdown parsing for `Dashboard.md` and `Business_Goals.md`).
- [ ] Implement Task Management API (listing files in `Pending_Approval` and moving them).
- [ ] Implement Project Planning API (writing to `Plans/` and updating `Business_Goals.md`).

## Phase 3: Frontend Development
- [ ] Build Login UI component.
- [ ] Build Main Layout (Sidebar/Navbar) with Web3 aesthetic.
- [ ] Build Dashboard Overview page (fetching and displaying stats).
- [ ] Build Task Review page (approve/reject functionality).
- [ ] Build Project Planning page.

## Phase 4: Integration & Testing
- [ ] Connect Frontend to Backend via Axios/Fetch with JWT interceptors.
- [ ] End-to-end testing of the Task Approval flow (UI -> API -> File moved to `Approved`).
- [ ] Clean up and verify pixel-perfect design.
