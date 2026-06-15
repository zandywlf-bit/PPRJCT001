# AGENT.md — AI/LLM Agent Development Guidelines

This document serves as a reference for AI coding agents (like Cline, GitHub Copilot, etc.) working on the **Supply Chain Control Tower** Streamlit application. It captures architectural decisions, coding conventions, and known constraints.

---

## 1. Project Overview

```
3-Page Streamlit Dashboard for Supply Chain Management
├── Page 1: Distributor PO Intake  → po_ledger (st.session_state)
├── Page 2: Factory Production      → production_ledger (st.session_state)
└── Page 3: Analytics & Export      → Merge + Plotly charts + Excel download
```

**Key Design Decision:** All data lives ephemerally in `st.session_state`. No external database.

---

## 2. Architecture & Code Organization

### 2.1. Application Entry Point
- `app.py` → `main()` function
- Single-file application (for simplicity and Streamlit Cloud compatibility)

### 2.2. Session State Keys

| Key | Type | Purpose |
|-----|------|---------|
| `st.session_state.po_ledger` | pd.DataFrame | PO records (columns per `PO_LEDGER_SCHEMA`) |
| `st.session_state.production_ledger` | pd.DataFrame | Production records (columns per `PRODUCTION_LEDGER_SCHEMA`) |

### 2.3. Constant Definitions (lines 21–23)

```python
SEASONS   = ['Summer', 'Fall', 'Winter', 'Spring']
FACTORIES = ['IND1', 'IND2', 'IND3', 'IND4', 'IND5', 'CHN1', 'CHN2', 'CHN3', 'CHN4']
YEARS     = list(range(2024, 2036))
```

**DO NOT change these constants** without updating all dependent code (3 pages + analytics).

### 2.4. Schema Enforcement

Always use the canonical schemas when creating or casting DataFrames:

```python
PO_LEDGER_SCHEMA = {
    'Date': 'datetime64[ns]',
    'Year': 'int64',
    'Season': 'object',
    'Factory': 'object',
    'Product Name': 'object',
    'Quantity': 'int64',
}

PRODUCTION_LEDGER_SCHEMA = {
    'Date': 'datetime64[ns]',
    'Year': 'int64',
    'Season': 'object',
    'Factory': 'object',
    'Product Name': 'object',
    'Quantity Produced': 'int64',
}
```

---

## 3. Core Algorithms

### 3.1. UPSERT (lines 82–125)

The `_upsert_record` function handles the insert-or-update logic:

1. Build a mask matching on `[Year, Season, Factory, Product Name]`
2. If match found: **add** new quantity to existing row (accumulate)
3. If no match: **append** new row

```python
def _upsert_record(df, new_record, match_cols, quantity_col):
    if df.empty:
        return concat with new record
    
    mask = True for all rows
    for col in match_cols:
        mask &= (df[col] == new_record[col])
    
    if mask.any():
        idx = df[mask].index[0]
        df.loc[idx, quantity_col] += new_record[quantity_col]
    else:
        df = concat(df, new_record)
    
    return df
```

### 3.2. Completion Rate (lines 510–520)

```python
def completion_rate(row):
    if row['Quantity'] == 0 and row['Quantity Produced'] > 0:
        return 100.0
    if row['Quantity'] == 0:
        return 0.0
    return round((row['Quantity Produced'] / row['Quantity']) * 100, 2)
```

---

## 4. Code Conventions

### 4.1. Function Naming
- `render_*` — functions that render Streamlit UI components
- `_upsert_*` — private helper functions (prefixed with underscore)
- `load_data`, `commit_transaction` — data engine operations
- `initialize_data_warehouse` — one-time session state initialization

### 4.2. UI Patterns
- Use `st.form()` with `clear_on_submit=True` for data entry
- Use `st.expander(..., expanded=True)` for prominent input sections
- Use `st.columns(n)` for layout
- Use `st.toast()` for user feedback (non-blocking)
- Use `st.metric()` for KPI display
- Use `st.dataframe()` with explicit `column_config` for clean tables
- Use `st.plotly_chart(fig, use_container_width=True)` for charts

### 4.3. Error Handling
- Validate `Product Name` is not empty before commit
- Return early if both ledgers are empty on analytics page
- Return early if filtered slices are empty (show warning, not error)
- Use silent `try/except pass` for file-system mock (best-effort only)

---

## 5. Known Constraints & Caveats

1. **Ephemeral Data** — All data resets when the Streamlit app restarts. This is intentional for Cloud deployment.
2. **No Authentication** — Single-user mode. All sessions share no state (each session is isolated).
3. **File System Mock** — The `_simulate_persist` function writes `.xlsx` files locally, but on Streamlit Cloud these files are temporary and will be cleaned up.
4. **Single-File Limitation** — The entire app is in `app.py`. For larger features, consider splitting into modules.

---

## 6. Testing Strategy

| Test Type | Approach |
|-----------|----------|
| Unit (UPSERT) | Test `_upsert_record` with empty DF, matching row, non-matching row |
| Unit (completion_rate) | Test edge cases: zero demand, zero production, both zero |
| Integration | Submit PO → verify ledger updated → verify analytics reflects change |
| UI | Manual testing via `streamlit run app.py` |

---

## 7. Deployment Checklist

- [ ] `requirements.txt` contains: streamlit, pandas, plotly, openpyxl
- [ ] App uses `st.set_page_config()` as first Streamlit command
- [ ] No hardcoded file paths that break on Cloud
- [ ] No external service dependencies
- [ ] All data stored in `st.session_state` (not local files for persistence)

---

## 8. Common Agent Tasks

### Adding a new factory
1. Add factory code to `FACTORIES` list (line 22–23)
2. Verify no hardcoded factory lists elsewhere

### Adding a new season
1. Add season to `SEASONS` list (line 21)
2. Update sort key in `render_analytics` (line 434)

### Adding a new column to a ledger
1. Add column to the corresponding schema dict
2. Update `column_config` in the `st.dataframe()` call
3. Update the form inputs
4. Update analytics merge logic if needed

### Creating a new analytics chart
1. Add new chart section in `render_analytics()` after line 573
2. Use `comparison` DataFrame which already has Quantity, Quantity Produced, Completion Rate (%)
3. Display with `st.plotly_chart(fig, use_container_width=True)`