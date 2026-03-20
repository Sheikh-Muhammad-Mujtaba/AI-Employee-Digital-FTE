# Skill: Update Dashboard

## Purpose
Refresh `Dashboard.md` with current, accurate data from all vault folders. Provides a real-time snapshot of the AI Employee's status.

## When to Use
- After processing any task
- On demand to get a current status view
- As a scheduled check-in

## Instructions

### Step 1 — Count items in each folder

Count `.md` files (excluding `.gitkeep`) in:
- `/Inbox` — items waiting to be processed
- `/Needs_Action` — pending action items
- `/Pending_Approval` — items waiting for human approval
- `/Done` — completed items
- `/Approved` — recently approved actions
- `/Plans` — active plans

### Step 2 — Read recent activity

Read the most recent 5 entries from today's log file at `Logs/YYYY-MM-DD.jsonl` (use today's date). Format them as a bullet list.

### Step 3 — Read active plans

List any `.md` files in `/Plans` that do not have `status: complete` in their frontmatter.

### Step 4 — Rewrite Dashboard.md

Update the following sections in `Dashboard.md`:
- Update `last_updated` in the YAML frontmatter to current UTC time
- **System Status** — set File Watcher and Orchestrator status based on any recent log entries
- **Inbox Summary** — update all four counts
- **Recent Activity** — replace with the 5 most recent log entries
- **Active Plans** — list open plans or write "_No active plans._"
- **Quick Stats** — update Tasks completed, Tasks pending, Approvals waiting

### Step 5 — Output

Output a brief summary:
```
Dashboard updated at <timestamp>.
- Needs Action: X items
- Pending Approval: Y items
- Done: Z items
```

Then output:
```
<promise>TASK_COMPLETE</promise>
```

## Rules
- Never delete Dashboard.md
- Preserve all sections — only update their content, not structure
- If a folder doesn't exist, show count as 0
- Use UTC timestamps everywhere
