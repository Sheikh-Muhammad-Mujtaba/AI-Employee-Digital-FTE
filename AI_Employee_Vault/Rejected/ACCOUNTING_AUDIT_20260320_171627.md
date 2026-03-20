---
action: run_accounting_audit
source_file: Needs_Action/ERPNEXT_audit_20260320_171627.md
open_invoices: 50
total_outstanding: 388.50
created: 2026-03-20T17:16:27Z
---

# Accounting Audit Execution Request

**Task:** Run the `accounting-audit` skill to pull a full snapshot from ERPNext.

**Expected Output:** Update `AI_Employee_Vault/Accounting/latest_snapshot.md` with full ERPNext data.

## Current Summary
- **Open Invoices:** 50
- **Total Outstanding Amount:** 388.50

## Sample Invoices (First 10)
| Invoice Name | Grand Total | Outstanding | Due Date |
|--------------|-------------|-------------|----------|
| ACC-SINV-2025-07474 | 5.5 | 0.5 | 2025-08-31 |
| ACC-SINV-2025-07475 | 690.0 | 90.0 | 2025-08-31 |
| ACC-SINV-2025-08468 | 277.5 | 1.0 | 2025-09-02 |
| ACC-SINV-2025-08577 | 994.75 | 1.0 | 2025-09-02 |
| ACC-SINV-2025-10109 | 408.8 | 1.0 | 2025-09-04 |
| ACC-SINV-2025-10889 | 660.6 | 1.0 | 2025-09-05 |
| ACC-SINV-2025-11760 | 2000.6 | 1.0 | 2025-09-07 |
| ACC-SINV-2025-15510 | 600.6 | 1.0 | 2025-09-12 |
| ACC-SINV-2025-15567 | 2000.6 | 1.0 | 2025-09-12 |
| ACC-SINV-2025-16113 | 640.6 | 1.0 | 2025-09-13 |

## Next Steps
1. Execute the accounting-audit skill
2. Pull full snapshot from ERPNext
3. Update Accounting/latest_snapshot.md
4. Move this file to Done/
