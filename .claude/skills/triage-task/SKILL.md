# Skill: Triage Task

## Purpose
Deeply analyse a single task file from `/Needs_Action`, create a structured Plan, and determine whether it can be completed autonomously or needs human approval.

## When to Use
Invoke with the filename as argument:
```
/triage-task FILENAME.md
```

## Instructions

### Step 1 — Read the task file
Read the specified `.md` file from `/Needs_Action`. Extract:
- `type` (email, file_drop, payment, etc.)
- `priority`
- `status`
- The body text describing the task

### Step 2 — Read the handbook
Read `Company_Handbook.md` — specifically:
- Section 3 (Autonomy Thresholds)
- Section 4 (Task Priority Rules)
- Section 5 (Sensitive Triggers)

### Step 3 — Classify the task

Assign one of these classifications:
- `auto` — can be completed without human input
- `approval_required` — needs human sign-off before action
- `blocked` — missing information; cannot proceed

### Step 4A — If `auto`:
- Complete the task directly
- Move the task file to `/Done/`
- Log the completion

### Step 4B — If `approval_required`:
Create a file in `/Pending_Approval/` named:
`APPROVAL_<type>_<safe_description>_<YYYY-MM-DD>.md`

With this structure:
```markdown
---
type: approval_request
original_task: <source filename>
action: <what action will be taken>
priority: <urgency>
created: <ISO 8601 timestamp>
expires: <24 hours from now>
status: pending
---

## Proposed Action
<Clear description of what the AI will do if approved>

## Reason
<Why this action is needed>

## To Approve
Move this file to /Approved/

## To Reject
Move this file to /Rejected/
```

### Step 4C — If `blocked`:
Add a `## Blocker` section to the task file explaining what information is missing.
Set `status: blocked` in frontmatter.
Leave the file in `/Needs_Action/`.

### Step 5 — Create a Plan (for multi-step tasks)
If the task requires more than 2 steps, create `/Plans/PLAN_<safe_description>.md`:
```markdown
---
created: <timestamp>
task_source: <source filename>
status: in_progress
---

## Objective
<One sentence>

## Steps
- [ ] Step 1
- [ ] Step 2
- [ ] Step 3

## Approval Required
<Yes/No — and why>
```

### Step 6 — Update Dashboard
Call the update-dashboard skill logic to refresh counts.

### Step 7 — Output
```
Triage complete for: <filename>
Classification: <auto|approval_required|blocked>
Action taken: <description>
<promise>TASK_COMPLETE</promise>
```

## Rules
- Never assume approval — when in doubt, classify as `approval_required`
- Never delete files
- Always log every decision
