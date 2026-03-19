"""Task management router – list, approve, reject vault task files."""

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from models import User
from vault_parser import list_folder_tasks, move_task_file
from schemas import TaskFile, TaskActionRequest, TaskActionResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("/pending", response_model=list[TaskFile])
async def get_pending_tasks(_user: User = Depends(get_current_user)):
    return list_folder_tasks("Pending_Approval")


@router.get("/needs-action", response_model=list[TaskFile])
async def get_needs_action(_user: User = Depends(get_current_user)):
    return list_folder_tasks("Needs_Action")


@router.get("/done", response_model=list[TaskFile])
async def get_done_tasks(_user: User = Depends(get_current_user)):
    return list_folder_tasks("Done")


@router.get("/approved", response_model=list[TaskFile])
async def get_approved_tasks(_user: User = Depends(get_current_user)):
    return list_folder_tasks("Approved")


@router.get("/logs", response_model=list[TaskFile])
async def get_logs_tasks(_user: User = Depends(get_current_user)):
    return list_folder_tasks("Logs")


@router.get("/plans", response_model=list[TaskFile])
async def get_plans_tasks(_user: User = Depends(get_current_user)):
    return list_folder_tasks("Plans")


@router.post("/{filename}/action", response_model=TaskActionResponse)
async def task_action(
    filename: str,
    body: TaskActionRequest,
    _user: User = Depends(get_current_user),
):
    source = body.source_folder
    
    if body.action == "edit":
        from config import VAULT_PATH
        filepath = VAULT_PATH / source / filename
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="File not found")
        filepath.write_text(body.content or "", encoding="utf-8")
        return TaskActionResponse(filename=filename, action="edit", destination=source, success=True)

    if body.action == "draft":
        from config import VAULT_PATH
        filepath = VAULT_PATH / source / filename
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="File not found")
        # Recreate the file to trigger Watchdog's on_created event inside Orchestrator
        content = filepath.read_text(encoding="utf-8")
        filepath.unlink()
        filepath.write_text(content, encoding="utf-8")
        return TaskActionResponse(filename=filename, action="draft", destination=source, success=True)

    if body.action == "revise":
        dest = "Needs_Action"
    elif body.action in ("reject", "ignore"):
        dest = "Done" if source == "Needs_Action" else "Rejected"
    else:
        dest = "Approved"

    try:
        new_path = move_task_file(filename, source, dest)
        if body.action == "revise" and body.feedback:
            with open(new_path, "a", encoding="utf-8") as f:
                f.write(f"\n\n## User Feedback\n{body.feedback}\n")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File {filename} not found in {source}")
        
    return TaskActionResponse(
        filename=filename,
        action=body.action,
        destination=dest,
        success=True,
    )
