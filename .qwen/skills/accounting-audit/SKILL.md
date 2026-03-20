# Skill: Accounting Audit

## Purpose
Query ERPNext via the MCP server, generate an accounting snapshot, and write it to `Accounting/latest_snapshot.md`. This snapshot is read by the weekly-briefing skill for the CEO report.

## When to Use
- When an `ERPNEXT_audit_*` file appears in `/Needs_Action/`
- When the weekly briefing skill needs fresh accounting data
- When the user asks for a financial summary

## Step-by-step Instructions

1. **Read the trigger file** — note open invoice count and total outstanding.

2. **Query ERPNext via MCP tools** (requires `erpnext` MCP server running):

   ```
   list_sales_invoice_documents  filters={"status": ["Unpaid","Overdue"]}  limit=50
   list_payment_entry_documents  limit=20
   list_gl_entry_documents       limit=30
   ```

3. **Build the snapshot** and write to `Accounting/latest_snapshot.md`:

```markdown
---
generated: {ISO timestamp}Z
source: ERPNext MCP
---

# Accounting Snapshot

**Generated:** {date}

## Open Invoices

| Invoice | Customer | Amount | Due Date | Status |
|---------|----------|--------|----------|--------|
| {name} | {customer} | {grand_total} | {due_date} | {status} |

**Total Outstanding:** {sum}
**Count:** {N}

## Recent Payments (last 20)

| Payment | Party | Amount | Date | Type |
|---------|-------|--------|------|------|
| {name} | {party} | {paid_amount} | {posting_date} | {payment_type} |

## Summary

- Open invoices: {N}
- Total outstanding: {amount}
- Payments received this month: {N}
- Total received this month: {amount}

## Data Gaps
{Note any doctypes that returned errors or empty results}
```

4. **Move trigger file from `/Needs_Action/` to `/Done/`.**

5. **Update Dashboard.md** — update "Last Sync" in the Accounting table.

6. **Log** with `action_type: accounting_audit_complete`.

## Rules
- **Never fabricate numbers.** If MCP returns an error, write the error in the Data Gaps section.
- **Read-only.** This skill never creates or modifies ERPNext records.
- If ERPNext MCP is not running, write: "ERPNext MCP not available — start with `claude --mcp-config mcp.json`" in the snapshot and move trigger to Done.
