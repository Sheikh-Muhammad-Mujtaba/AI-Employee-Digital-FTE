"""Projects & plans router."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import get_current_user
from models import User
from vault_parser import parse_business_goals, create_plan_file, list_folder_tasks
from schemas import BusinessGoals, CreatePlanRequest, TaskFile

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/goals", response_model=BusinessGoals)
async def get_business_goals(_user: User = Depends(get_current_user)):
    return parse_business_goals()


@router.get("/plans", response_model=list[TaskFile])
async def get_plans(_user: User = Depends(get_current_user)):
    return list_folder_tasks("Plans")


@router.post("/plans", status_code=201)
async def create_plan(body: CreatePlanRequest, _user: User = Depends(get_current_user)):
    path = create_plan_file(body.title, body.description, body.steps, body.due_date)
    return {"message": "Plan created", "path": str(path.name)}


class GeneratePlanRequest(BaseModel):
    prompt: str

@router.post("/generate", status_code=201)
async def generate_plan_request(body: GeneratePlanRequest, _user: User = Depends(get_current_user)):
    import datetime
    from config import VAULT_PATH
    
    needs_action = VAULT_PATH / "Needs_Action"
    needs_action.mkdir(parents=True, exist_ok=True)
    
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"PLAN_REQUEST_{ts}.md"
    content = f"---\ntype: generate_plan\ncreated: {datetime.datetime.utcnow().isoformat()}Z\nstatus: needs_action\n---\n\n{body.prompt}"
    
    (needs_action / filename).write_text(content, encoding="utf-8")
    return {"message": "Plan generation requested", "filename": filename}
