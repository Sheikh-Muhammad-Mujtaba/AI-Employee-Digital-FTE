# ERPNext Doctype Field Reference

## Table of Contents
- [Sales Invoice](#sales-invoice)
- [Purchase Invoice](#purchase-invoice)
- [GL Entry](#gl-entry)
- [Client Script](#client-script)
- [Customer](#customer)
- [Filter Syntax](#filter-syntax-reference)
- [docstatus Values](#docstatus-values)

---

## Sales Invoice

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Auto-generated, e.g. ACC-SINV-2025-06622 |
| `customer` | link | Customer name |
| `posting_date` | date | YYYY-MM-DD |
| `grand_total` | float | Total including taxes |
| `net_total` | float | Total before taxes |
| `total_taxes_and_charges` | float | Tax amount |
| `docstatus` | int | 0=draft, 1=submitted, 2=cancelled |
| `status` | string | Paid, Unpaid, Overdue, Return |
| `is_pos` | int | 1 if POS invoice |
| `is_return` | int | 1 if credit note |
| `currency` | string | PKR, USD, etc. |
| `cost_center` | link | e.g. Main - NB |
| `items` | table | Child table — see below |
| `payments` | table | POS payment modes |

**Sales Invoice Item fields:** `item_code`, `item_name`, `qty`, `rate`, `amount`, `net_amount`, `income_account`, `expense_account`, `incoming_rate` (COGS rate), `warehouse`

---

## Purchase Invoice

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | e.g. ACC-PINV-2025-00158 |
| `supplier` | link | Supplier name |
| `posting_date` | date | |
| `grand_total` | float | |
| `net_total` | float | |
| `docstatus` | int | 0/1/2 |
| `status` | string | Paid, Unpaid, Overdue |
| `items` | table | Purchase Invoice Item child table |

**Purchase Invoice Item fields:** `item_code`, `item_name`, `qty`, `rate`, `amount`, `warehouse`, `expense_account`, `valuation_rate`

---

## GL Entry

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | e.g. ACC-GLE-2025-113787 |
| `posting_date` | date | |
| `fiscal_year` | string | e.g. 2025-2026 |
| `account` | link | Chart of accounts entry |
| `debit` | float | Debit amount (expense/asset increase) |
| `credit` | float | Credit amount (income/liability increase) |
| `voucher_type` | string | Sales Invoice, Purchase Invoice, Journal Entry, etc. |
| `voucher_no` | string | Source document name |
| `is_cancelled` | int | 0 = active |
| `cost_center` | link | |
| `company` | link | |
| `remarks` | text | Transaction description |

**P&L logic:**
- Income = sum of `credit` where account contains "Income"
- COGS = sum of `debit` where account = "Cost of Goods Sold - NB"
- Gross Profit = Income − COGS

---

## Client Script

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Usually the DocType name it applies to |
| `dt` | link | Target DocType |
| `view` | string | Form, List |
| `enabled` | int | 0=disabled, 1=enabled |
| `script` | code | JavaScript (Frappe UI) |

---

## Customer

| Field | Type | Notes |
|-------|------|-------|
| `name` | string | Customer ID |
| `customer_name` | string | Display name |
| `customer_type` | string | Company / Individual |
| `customer_group` | link | |
| `territory` | link | |
| `email_id` | string | |
| `mobile_no` | string | |

---

## Filter Syntax Reference

```python
# Equality
{"docstatus": 1}

# Like / contains
{"account": ["like", "%Income%"]}

# Date range
{"posting_date": ["between", ["2025-08-01", "2025-08-31"]]}

# Greater than or equal
{"posting_date": [">=", "2025-01-01"]}

# In list
{"status": ["in", ["Paid", "Unpaid"]]}

# Not equal
{"is_cancelled": ["!=", 1]}
```

---

## docstatus Values

| Value | Meaning |
|-------|---------|
| 0 | Draft |
| 1 | Submitted |
| 2 | Cancelled |

Always use `"docstatus": 1` when querying for active/posted financial documents.

Example real reference docs from other skills:
- product-management/references/communication.md - Comprehensive guide for status updates
- product-management/references/context_building.md - Deep-dive on gathering context
- bigquery/references/ - API references and query examples

## When Reference Docs Are Useful

Reference docs are ideal for:
- Comprehensive API documentation
- Detailed workflow guides
- Complex multi-step processes
- Information too lengthy for main SKILL.md
- Content that's only needed for specific use cases

## Structure Suggestions

### API Reference Example
- Overview
- Authentication
- Endpoints with examples
- Error codes
- Rate limits

### Workflow Guide Example
- Prerequisites
- Step-by-step instructions
- Common patterns
- Troubleshooting
- Best practices
