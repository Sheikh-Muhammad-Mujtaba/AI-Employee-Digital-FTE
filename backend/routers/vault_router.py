"""Dashboard & vault status router."""

from fastapi import APIRouter, Depends

from auth import get_current_user
from models import User
from vault_parser import parse_dashboard
from schemas import DashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/status", response_model=DashboardResponse)
async def dashboard_status(_user: User = Depends(get_current_user)):
    return parse_dashboard()
