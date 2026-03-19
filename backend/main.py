"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import FRONTEND_ORIGIN
from database import Base, engine
from routers import auth_router, vault_router, tasks_router, projects_router, whatsapp_router, accounting_router

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Digital FTE Dashboard API",
    version="1.0.0",
    description="Backend API for the AI Employee Digital FTE Dashboard",
)

# CORS — allow the Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router.router)
app.include_router(vault_router.router)
app.include_router(tasks_router.router)
app.include_router(projects_router.router)
app.include_router(whatsapp_router.router)
app.include_router(accounting_router.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
