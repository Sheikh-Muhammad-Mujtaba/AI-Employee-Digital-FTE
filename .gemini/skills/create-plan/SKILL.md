# Skill: Create Plan

## Purpose
Convert a raw task in `/Needs_Action/` into a structured `Plan.md` file in `/Plans/` with clear checkboxes, ownership, deadline, and sub-steps. This is the Silver Tier reasoning loop — Claude reads a task, thinks through it, and writes an actionable plan before doing anything.

## When to Use
- When a Needs_Action file contains a multi-step task (more than one action required)
- When processing email, WhatsApp, or scheduled task triggers that require planning
- Whenever a task isn't trivially completable in one step
- When the Orchestrator triggers you to process a complex action file

## Step-by-step Instructions

1. **Read the trigger file** from `/Needs_Action/` — understand the request type, priority, and context.

2. **Read `Company_Handbook.md`** — check the rules of engagement that apply to this task.

3. **Read `Business_Goals.md`** — understand active projects and targets that provide context.

4. **Determine task complexity:**
   - If the task can be done in one action (e.g., just archive a file) → do it directly, no plan needed.
   - If 2+ steps are required → create a Plan.md.

5. **Create the Plan file** at `/Plans/PLAN_{task_slug}_{YYYYMMDD}.md` with this exact schema:

```markdown
---
type: plan
source_file: {original Needs_Action filename}
created: {ISO timestamp}Z
status: in_progress
priority: {urgent|high|normal}
estimated_completion: {date or "unknown"}
---

# Plan: {Short title describing the task}

## Objective
{One sentence: what does "done" look like?}

## Context
{Why is this needed? What triggered it?}

## Steps

- [ ] Step 1 — {action} _(skill: /skill-name if applicable)_
- [ ] Step 2 — {action}
- [ ] Step 3 — {action} _(requires approval — will create /Pending_Approval file)_
- [ ] Step 4 — Update Dashboard.md
- [ ] Step 5 — Move source file to /Done

## Risks & Rules
- {Any HITL requirements, e.g. "Email to new contact requires approval"}
- {Any spend threshold rules from Company_Handbook}

## Notes
_(Add observations here as steps complete.)_
```

6. **Update the source Needs_Action file** — add a line at the top referencing the plan:
   ```
   > ℹ️ Plan created: Plans/PLAN_{task_slug}_{YYYYMMDD}.md
   ```

7. **Update Dashboard.md** — add the plan to the "Active Plans" section.

8. **Begin executing the plan** — work through checkboxes in order. For each completed step, tick the checkbox in the plan file.

9. **For any step requiring external action** (email send, LinkedIn post, payment):
   - Create a file in `/Pending_Approval/` with full details.
   - Pause that step until the human approves (moves file to `/Approved/`).
   - Continue with other non-blocked steps if possible.

10. **When all steps are complete:**
    - Set `status: completed` in the plan frontmatter.
    - Move the plan file to `/Done/`.
    - Move the original Needs_Action file to `/Done/`.
    - Update Dashboard.md.

## Rules

- **Never skip planning for complex tasks.** A plan created and discarded is far better than an action taken without thinking.
- **One plan per trigger.** Don't create duplicate plans for the same source file.
- **Respect Company_Handbook rules** — if a rule says "always approve payments over $100", put that step in /Pending_Approval regardless of apparent urgency.
- **Never modify files in /Done.** Once archived, they are the audit record.
- **Atomic step descriptions.** Each checkbox should be a single, clear action — not "handle the email" but "draft reply to Client A re: invoice #1234".
