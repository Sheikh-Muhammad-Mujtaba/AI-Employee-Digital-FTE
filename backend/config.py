"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (one level up from backend/)
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# --- Paths ---
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
VAULT_PATH: Path = PROJECT_ROOT / "AI_Employee_Vault"

# --- Auth ---
SECRET_KEY: str = os.getenv("DASHBOARD_SECRET_KEY", "change-me-in-production-please")
ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("DASHBOARD_TOKEN_EXPIRE_MIN", "1440"))  # 24 h

# --- Database ---
DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT / 'backend' / 'dashboard.db'}"

# --- CORS ---
FRONTEND_ORIGIN: str = os.getenv("DASHBOARD_FRONTEND_ORIGIN", "http://localhost:3000")
