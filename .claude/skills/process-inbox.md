# Skill: Process Inbox

## Purpose
Scan the `/Needs_Action` folder in the AI Employee vault, read each pending task file, determine the correct action, and either complete it autonomously or create an approval request.

## When to Use
Invoke this skill when:
- New files appear in `/Needs_Action`
- You want to manually trigger a triage pass
- After the filesystem watcher drops new action files

## Instructions

Follow these steps exactly:

### Step 1 — Read the handbook
Read `Company_Handbook.md` to load all rules of engagement before taking any action.

### Step 2 — Scan /Needs_Action
List all `.md` files in `/Needs_Action` that have `status: pending` in their frontmatter.

### Step 3 — For each pending file, determine action

**If the task requires external action (email, payment, message send):**
- Create an approval file in `/Pending_Approval/` named: `APPROVAL_<original_filename>`
- Set `status: pending_approval` in the action file frontmatter
- Do NOT take the external action yet

**If the task is internal (file organization, reading, planning):**
- Complete the task directly
- Create a Plan file in `/Plans/` if multi-step work is needed
- Move the action file to `/Done/` when complete

### Step 4 — Update Dashboard
After processing all files, update `Dashboard.md`:
- Update the "Inbox Summary" counts
- Add an entry to "Recent Activity" with timestamp and description
- Update `last_updated` in the frontmatter

### Step 5 — Log
Append a JSON entry to `Logs/YYYY-MM-DD.jsonl` for each file processed:
```json
{
  "timestamp": "<ISO 8601>",
  "skill": "process-inbox",
  "file": "<filename>",
  "action": "<action taken>",
  "result": "success|pending_approval|error"
}
```

### Step 6 — Output
When all files are processed, output:
```
<promise>TASK_COMPLETE</promise>
```

## Rules
- Never send emails, messages, or make payments without an approval file first
- Never delete files — move them to /Done or /Rejected instead
- If unsure of the correct action, always create an approval request
- Respect priority order: urgent > payment/invoice > client > internal
