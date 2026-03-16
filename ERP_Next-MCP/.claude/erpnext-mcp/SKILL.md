---
name: erpnext-mcp
description: >
  Use this skill when working with an ERPNext instance via the ERPNext MCP server.
  Triggers when the user asks to: fetch ERPNext documents, list doctypes, query Sales Invoices,
  Purchase Invoices, GL Entries, Customers, Items, Client Scripts, or any other ERPNext doctype;
  audit financial data (P&L, revenue, expenses, COGS); create or update ERPNext documents
  (e.g., "create a sales invoice", "update a customer"); or search/filter ERPNext records.
  Also triggers for questions like "show me all client scripts", "get GL entries for income accounts",
  "list purchase invoices", or "audit profit and loss".
---

# ERPNext MCP Skill

## Key Limitations to Know Upfront

1. **`list_generic_documents` only returns `name` fields** — the `fields` parameter is ignored by the API. To get financial values or other fields, use `get_generic_document` on individual records after listing.
2. **List results capped at 100** — paginate or narrow filters if more records exist.
3. **No aggregation** — SUM/COUNT/GROUP BY not available. For totals, fetch individual documents and sum manually, or direct the user to ERPNext's built-in reports.
4. **Date filters** — use `["between", ["YYYY-MM-DD", "YYYY-MM-DD"]]` or `[">=", "YYYY-MM-DD"]` syntax.
5. **Fiscal year filter** — use `"fiscal_year": "2025-2026"` on GL Entry for year-scoped queries.

---

## Available Tools

| Tool | Use For |
|------|---------|
| `test_connection` | Verify MCP ↔ ERPNext connectivity |
| `get_system_info` | ERPNext version and system info |
| `list_doctypes` | See configured doctypes and permissions |
| `get_doctype_permissions` | Check permissions for a specific doctype |
| `get_doctype_schema` | Get field metadata for any doctype |
| `list_generic_documents` | List documents (returns names only) |
| `get_generic_document` | Get full document with all fields |
| `create_generic_document` | Create a new document |
| `update_generic_document` | Update an existing document |
| `list_customer_documents` | List customers |
| `get_customer_document` | Get customer by name |
| `search_customer_documents` | Search customers by text |
| `create_customer_document` | Create a customer |
| `update_customer_document` | Update a customer |

---

## Common Workflows

### 1. Fetch a Specific Document

```
get_generic_document(doctype="Sales Invoice", name="ACC-SINV-2025-06622")
```

Use this for: Sales Invoice, Purchase Invoice, GL Entry, Client Script, Customer, Item, etc.

### 2. List Documents (Names Only)

```
list_generic_documents(
  doctype="Client Script",
  filters={},
  fields=["name"],
  limit=100
)
```

Then call `get_generic_document` on specific names to retrieve full details.

### 3. Financial Queries (P&L / Revenue / COGS)

Since list returns names only, query GL Entries by account type:

**Income entries:**
```
list_generic_documents(
  doctype="GL Entry",
  filters={"account": ["like", "%Income%"], "is_cancelled": 0, "fiscal_year": "2025-2026"},
  fields=["name"],
  limit=100
)
```

**COGS entries:**
```
list_generic_documents(
  doctype="GL Entry",
  filters={"account": ["like", "%Cost of Goods%"], "is_cancelled": 0, "fiscal_year": "2025-2026"},
  fields=["name"],
  limit=100
)
```

Then fetch individual GL entries to get `credit`, `debit`, `account`, `voucher_no`, `posting_date`.

For a full P&L, advise the user to run ERPNext's built-in **Profit and Loss Statement** report (Accounts > Financial Statements > Profit and Loss Statement).

### 4. Create a Sales Invoice

```
create_generic_document(
  doctype="Sales Invoice",
  data={
    "customer": "Walk-In",
    "posting_date": "2025-08-29",
    "is_pos": 1,
    "items": [
      {
        "item_code": "ITEM-001",
        "qty": 2,
        "rate": 500
      }
    ]
  }
)
```

Required fields: `customer`, `posting_date`, `items` (with `item_code`, `qty`, `rate`).
Optional: `pos_profile`, `cost_center`, `currency`, `selling_price_list`.

### 5. Create a Purchase Invoice

```
create_generic_document(
  doctype="Purchase Invoice",
  data={
    "supplier": "NB Danyour Factory",
    "posting_date": "2025-08-29",
    "items": [
      {
        "item_code": "ITEM-001",
        "qty": 10,
        "rate": 100
      }
    ]
  }
)
```

### 6. List and Fetch Client Scripts

```
# Step 1: list
list_generic_documents(doctype="Client Script", filters={}, fields=["name"], limit=100)

# Step 2: get details of a specific one
get_generic_document(doctype="Client Script", name="Sales Invoice")
```

### 7. Filter Submitted Invoices

Use `docstatus: 1` for submitted, `0` for draft, `2` for cancelled:

```
list_generic_documents(
  doctype="Sales Invoice",
  filters={"docstatus": 1, "posting_date": ["between", ["2025-08-01", "2025-08-31"]]},
  fields=["name"],
  limit=100
)
```

---

## ERPNext Instance Notes (National Bakers)

- **Company**: National Bakers
- **Currency**: PKR
- **Fiscal Year**: 2025-2026
- **Income Account**: `POS Main Branch Income - NB`
- **COGS Account**: `Cost of Goods Sold - NB`
- **Cost Center**: `Main - NB`
- **Warehouse**: `Main Warehouse - NB`
- **Gross margin**: ~20% (buying price ≈ 80% of selling price)
- **All POS sales**: Walk-In customer, Cash payment
- **No taxes applied** on any invoices

See `references/api_reference.md` for field reference for key doctypes.
