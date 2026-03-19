"""Accounting router – triggers invoice creation and reads snapshots."""

import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from models import User
from config import VAULT_PATH

router = APIRouter(prefix="/api/accounting", tags=["accounting"])

class AccountingRequest(BaseModel):
    prompt: str

@router.post("/request")
async def create_accounting_request(body: AccountingRequest, _user: User = Depends(get_current_user)):
    needs_action = VAULT_PATH / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"ACCOUNTING_REQUEST_{ts}.md"
    content = f"---\ntype: accounting_request\ncreated: {datetime.datetime.utcnow().isoformat()}Z\nstatus: needs_action\n---\n\n{body.prompt}"
    
    (needs_action / filename).write_text(content, encoding="utf-8")
    return {"message": "Accounting request sent to Agent", "filename": filename}

@router.get("/snapshot")
async def get_accounting_snapshot(_user: User = Depends(get_current_user)):
    snapshot_path = VAULT_PATH / "Accounting" / "latest_snapshot.md"
    if not snapshot_path.exists():
        return {"content": "No snapshot available yet. The ERPNext watcher or an Accounting prompt will create one."}
    
    raw = snapshot_path.read_text(encoding="utf-8", errors="replace")
    return {"content": raw}
