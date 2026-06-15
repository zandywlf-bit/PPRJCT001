# Product Requirements Document (PRD) — Supply Chain Control Tower

## 1. Overview

**Product Name:** Supply Chain Control Tower  
**Version:** 1.0.0  
**Platform:** Streamlit Community Cloud (web-based)  
**Target Users:** Supply Chain Data Engineers, Factory Managers, Distributor Planners

A 3-page interactive dashboard for end-to-end supply chain visibility: capturing distributor purchase orders, recording factory production reports, and comparing planned demand against actual production output.

---

## 2. Functional Requirements

### 2.1. Page 1 — Distributor PO Intake Engine

| ID | Requirement | Priority |
|----|------------|----------|
| FR-01 | User selects **Year** from a dropdown (range: 2024–2035) | P0 |
| FR-02 | User selects **Season** from Summer, Fall, Winter, Spring | P0 |
| FR-03 | User selects **Factory** from IND1–IND5, CHN1–CHN4 | P0 |
| FR-04 | User inputs **Date** of the request via date picker | P0 |
| FR-05 | User inputs **Product Name** as free text | P0 |
| FR-06 | User inputs **Quantity** (positive integer, min 1) | P0 |
| FR-07 | On submit, record is committed to the PO ledger | P0 |
| FR-08 | If a record with the same Year + Season + Factory + Product Name exists, quantities are **summed** (UPSERT) | P0 |
| FR-09 | Data is organized virtually as: `data/<Year>/<Season>/<Factory>.xlsx` | P1 |
| FR-10 | The PO ledger is displayed as a sortable data table | P0 |

### 2.2. Page 2 — Factory Production Ledger Terminal

| ID | Requirement | Priority |
|----|------------|----------|
| FR-11 | User selects **Year**, **Season**, **Factory** (same taxonomy as Page 1) | P0 |
| FR-12 | User inputs **Date**, **Product Name**, **Quantity Produced** | P0 |
| FR-13 | On submit, record is committed to the production ledger | P0 |
| FR-14 | Same-product entries (Year + Season + Factory) are auto-aggregated | P0 |
| FR-15 | Data is virtually stored in the same folder structure as PO data | P1 |
| FR-16 | Production ledger is displayed as a sortable data table | P0 |

### 2.3. Page 3 — Cross-Functional Performance Analytics

| ID | Requirement | Priority |
|----|------------|----------|
| FR-17 | User selects **Year**, **Season**, **Factory** as demand-driven filters | P0 |
| FR-18 | System pulls matching PO and Production data from both ledgers | P0 |
| FR-19 | **KPI Cards** display: Total Requested, Total Produced, Product Count, Overall Completion Rate (%) | P0 |
| FR-20 | **Grouped Bar Chart** (Plotly) compares Demand vs Yield per product | P0 |
| FR-21 | **Comparison Grid** table shows per-product requested vs produced vs completion % | P0 |
| FR-22 | **Excel Export** button downloads a compiled `.xlsx` with metrics + summary sheet | P0 |
| FR-23 | Completion Rate = (Quantity Produced / Quantity Requested) × 100 | P0 |
| FR-24 | Edge cases handled: no PO data, no Production data, both empty | P1 |

---

## 3. Non-Functional Requirements

| ID | Requirement | Priority |
|----|------------|----------|
| NFR-01 | App must run on **Streamlit Community Cloud** without external databases | P0 |
| NFR-02 | Data is ephemeral (in-memory via `st.session_state`); no persistent storage guaranteed | P1 |
| NFR-03 | App must support concurrent user sessions (each with isolated state) | P1 |
| NFR-04 | Excel export must use `.xlsx` format with `openpyxl` engine | P0 |
| NFR-05 | UI must be responsive and use Streamlit's wide layout | P1 |

---

## 4. Data Model

### 4.1. PO Ledger Schema (`po_ledger`)

| Column | Type | Description |
|--------|------|-------------|
| Date | datetime64 | Date of the PO request |
| Year | int64 | Selected year (e.g., 2024) |
| Season | string | Summer / Fall / Winter / Spring |
| Factory | string | IND1–IND5, CHN1–CHN4 |
| Product Name | string | Name of the product |
| Quantity | int64 | Requested quantity (aggregated) |

### 4.2. Production Ledger Schema (`production_ledger`)

| Column | Type | Description |
|--------|------|-------------|
| Date | datetime64 | Date of the production report |
| Year | int64 | Selected year |
| Season | string | Summer / Fall / Winter / Spring |
| Factory | string | IND1–IND5, CHN1–CHN4 |
| Product Name | string | Name of the product |
| Quantity Produced | int64 | Produced quantity (aggregated) |

---

## 5. File Organization (Virtual)

```
data/
└── <Year>/
    └── <Season>/
        ├── IND1.xlsx   (PO records for IND1 in that Year/Season)
        ├── IND2.xlsx
        ├── ...
        └── CHN4.xlsx
```

When a transaction is committed, a best-effort Excel file is written to the local filesystem to simulate enterprise persistence. Each file contains all records for that Year + Season + Factory combination.

---

## 6. Key Algorithms

### 6.1. UPSERT Logic

```
IF a row exists where (Year = input.Year AND Season = input.Season
    AND Factory = input.Factory AND Product Name = input.Product Name):
    UPDATE row.Quantity += input.Quantity (or Quantity Produced)
ELSE:
    INSERT new row
```

### 6.2. Completion Rate Calculation

```
For each product:
    IF Quantity == 0 AND Quantity Produced > 0:  rate = 100%
    IF Quantity == 0 AND Quantity Produced == 0: rate = 0%
    ELSE: rate = (Quantity Produced / Quantity) × 100

Overall:
    IF Total Quantity == 0 AND Total Produced > 0:  rate = 100%
    IF Total Quantity == 0 AND Total Produced == 0: rate = 0%
    ELSE: rate = (Total Produced / Total Quantity) × 100
```

---

## 7. Dependencies

| Package | Minimum Version | Purpose |
|---------|----------------|---------|
| streamlit | 1.28.0 | Web framework & UI |
| pandas | 2.0.0 | Data manipulation |
| plotly | 5.15.0 | Interactive charts |
| openpyxl | 3.1.0 | Excel file I/O |

---

## 8. Future Enhancements (v2.0)

- Persistent data storage using SQLite or cloud database
- Multi-user authentication and role-based access
- Historical trend charts (across multiple seasons/years)
- Batch CSV import for mass PO/production entries
- Email alerts when completion rate drops below threshold
- Real-time data refresh across sessions (WebSocket)