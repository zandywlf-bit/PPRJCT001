# 🏭 Supply Chain Control Tower — Interactive Dashboard

A **3-page interactive Streamlit dashboard** for supply chain management that handles Distributor PO intake, Factory Production reporting, and Cross-Functional performance analytics with Excel export.

## Features

### 📦 Page 1 — Distributor PO Intake Engine
- Submit purchase orders by selecting **Year**, **Season** (Summer/Fall/Winter/Spring), and **Factory** (IND1–IND5, CHN1–CHN4)
- Enter date, product name, and quantity
- Duplicate products with the same Year + Season + Factory are **auto-aggregated** (quantities summed)
- Data is organized in a virtual folder hierarchy: `data/<Year>/<Season>/<Factory>.xlsx`

### ⚙️ Page 2 — Factory Production Ledger Terminal
- Record actual production yields with the same Year/Season/Factory taxonomy
- Same auto-aggregation logic for same-product entries
- Mirror data structure to Page 1 for seamless comparison

### 📊 Page 3 — Cross-Functional Performance Analytics
- **KPI Cards**: Total Requested, Total Produced, Product Count, Completion Rate (%)
- **Grouped Bar Chart**: Demand vs Yield per product (Plotly Express)
- **Comparison Grid**: Per-product breakdown with completion percentage
- **Excel Export**: Download a compiled `.xlsx` report with detailed metrics + summary sheet

## Data Architecture

All data is stored in-memory via **Streamlit `st.session_state`** (ephemeral per session). An optional file-system mock simulates the enterprise layout:

```
data/
├── <Year>/
│   ├── <Season>/
│   │   ├── <Factory>.xlsx
│   │   └── ...
│   └── ...
└── ...
```

## Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. Log in to [share.streamlit.io](https://share.streamlit.io).
3. Click **"New app"**, select your repo, branch, and set **Main file path** to `Streamlit_app.py`.
4. Click **Deploy**.

No external database is required. The app is fully self-contained.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Framework | Streamlit ≥ 1.28.0 |
| Data Processing | Pandas ≥ 2.0.0 |
| Charts | Plotly ≥ 5.15.0 |
| Excel Export | OpenPyXL ≥ 3.1.0 |
| File Mocks | Standard `io` / `os` modules |

## Local Development

```bash
# Clone the repo
git clone <repo-url>
cd <project-folder>

# (Recommended) Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## Project Structure

```
.
├── Streamlit_app.py    # Main Streamlit application (deploy this file)
├── app.py              # Identical copy (aliased for local dev)
├── requirements.txt    # Python dependencies
├── README.md           # This file
├── PRD.md              # Product Requirements Document
├── AGENT.md            # AI/LLM Agent development guidelines
└── data/               # Auto-created folder for Excel file mocks
    └── (generated at runtime)
```

---

> **Note:** The main entry point for Streamlit Community Cloud is `Streamlit_app.py`.  
> `app.py` is a local alias — both files are identical.

**Version:** 1.0.0  
**License:** MIT
