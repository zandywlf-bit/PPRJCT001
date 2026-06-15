import streamlit as st
import pandas as pd
import plotly.express as px
from io import BytesIO
from datetime import date
import os

# ═══════════════════════════════════════════════════════════════════════
# Page Configuration
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Supply Chain Control Tower",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════════
# Constants & Schema Definitions
# ═══════════════════════════════════════════════════════════════════════
SEASONS: list = ['Summer', 'Fall', 'Winter', 'Spring']
FACTORIES: list = ['IND1', 'IND2', 'IND3', 'IND4', 'IND5',
                   'CHN1', 'CHN2', 'CHN3', 'CHN4']
YEARS: list = list(range(2024, 2036))  # 2024 – 2035 inclusive

# ── Explicit Column Schemas ───────────────────────────────────────────
PO_LEDGER_SCHEMA: dict = {
    'Date': 'datetime64[ns]',
    'Year': 'int64',
    'Season': 'object',
    'Factory': 'object',
    'Product Name': 'object',
    'Product Size': 'object',
    'Quantity': 'int64',
}

PRODUCTION_LEDGER_SCHEMA: dict = {
    'Date': 'datetime64[ns]',
    'Year': 'int64',
    'Season': 'object',
    'Factory': 'object',
    'Product Name': 'object',
    'Product Size': 'object',
    'Quantity Produced': 'int64',
}

# ── Shared match columns for UPSERT ───────────────────────────────────
MATCH_COLS: list = ['Year', 'Season', 'Factory', 'Product Name', 'Product Size']


# ═══════════════════════════════════════════════════════════════════════
# Mock Data Warehouse Layer (st.session_state as In-Memory Store)
# ═══════════════════════════════════════════════════════════════════════
def initialize_data_warehouse() -> None:
    """Seed empty DataFrames into session state if they do not yet exist."""
    if 'po_ledger' not in st.session_state:
        df = pd.DataFrame(columns=list(PO_LEDGER_SCHEMA.keys()))
        st.session_state.po_ledger = df.astype(PO_LEDGER_SCHEMA)

    if 'production_ledger' not in st.session_state:
        df = pd.DataFrame(columns=list(PRODUCTION_LEDGER_SCHEMA.keys()))
        st.session_state.production_ledger = df.astype(PRODUCTION_LEDGER_SCHEMA)


# ═══════════════════════════════════════════════════════════════════════
# Data Engine — Helper Functions
# ═══════════════════════════════════════════════════════════════════════
def load_data(ledger_name: str) -> pd.DataFrame:
    """Return a *copy* of the requested ledger from session state."""
    return st.session_state[ledger_name].copy()


def aggregate_ledger(df: pd.DataFrame,
                     group_cols: list,
                     agg_col: str) -> pd.DataFrame:
    """Group a ledger by `group_cols` and sum `agg_col`."""
    if df.empty:
        return df
    return df.groupby(group_cols, as_index=False)[agg_col].sum()


def _upsert_record(df: pd.DataFrame,
                   new_record: dict,
                   match_cols: list,
                   quantity_col: str) -> pd.DataFrame:
    """
    Core UPSERT engine.

    If a row exists where all `match_cols` equal the new record's values,
    *add* the new quantity to that existing row.  Otherwise, append a new row.
    """
    if df.empty:
        return pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)

    mask = pd.Series([True] * len(df))
    for col in match_cols:
        mask &= (df[col] == new_record[col])

    if mask.any():
        idx = df[mask].index[0]
        df.loc[idx, quantity_col] += new_record[quantity_col]
        df.loc[idx, 'Date'] = new_record['Date']
    else:
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)

    return df


def _simulate_persist(record: dict, ledger_name: str) -> None:
    """
    Simulate writing to the enterprise folder hierarchy:

        /data/YEAR/SEASON/FACTORY_NAME.xlsx
    """
    year = str(record.get('Year', 'unknown'))
    season = record.get('Season', 'unknown')
    factory = record.get('Factory', 'unknown')

    dir_path = os.path.join('data', year, season)
    os.makedirs(dir_path, exist_ok=True)
    filepath = os.path.join(dir_path, f'{factory}.xlsx')

    ledger_df = st.session_state.get(ledger_name, pd.DataFrame())
    factory_slice = ledger_df[ledger_df['Factory'] == factory]

    if not factory_slice.empty:
        try:
            with BytesIO() as buf:
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    factory_slice.to_excel(writer, index=False,
                                           sheet_name=ledger_name)
                with open(filepath, 'wb') as f:
                    f.write(buf.getvalue())
        except Exception:
            pass


def commit_transaction(ledger_name: str,
                       record: dict,
                       schema: dict,
                       match_cols: list,
                       quantity_col: str) -> None:
    """
    High-level commit function:
    1. Load current ledger
    2. UPSERT incoming record
    3. Re-cast to canonical schema
    4. Persist back to session state
    5. Simulate file-system write
    """
    df = load_data(ledger_name)
    df = _upsert_record(df, record, match_cols, quantity_col)
    df = df.astype(schema)
    st.session_state[ledger_name] = df
    _simulate_persist(record, ledger_name)


def bulk_commit_from_df(ledger_name: str,
                        df: pd.DataFrame,
                        schema: dict,
                        match_cols: list,
                        quantity_col: str) -> int:
    """
    Commit every row of a DataFrame to the ledger using UPSERT logic.
    Returns the number of rows processed.
    """
    count = 0
    for _, row in df.iterrows():
        record = row.to_dict()
        commit_transaction(ledger_name, record, schema, match_cols, quantity_col)
        count += 1
    return count


def delete_selected_records(ledger_name: str, indices: list) -> None:
    """Delete rows by index from the ledger in session state."""
    df = st.session_state[ledger_name]
    df = df.drop(index=indices).reset_index(drop=True)
    st.session_state[ledger_name] = df


# ═══════════════════════════════════════════════════════════════════════
# Shared UI Helper — Excel Upload Section
# ═══════════════════════════════════════════════════════════════════════
EXPECTED_EXCEL_COLS_PO = ['Product Name', 'Product Size', 'Quantity']
EXPECTED_EXCEL_COLS_PROD = ['Product Name', 'Product Size', 'Quantity Produced']


def render_excel_upload_section(page_key: str,
                                ledger_name: str,
                                schema: dict,
                                quantity_col: str,
                                expected_cols: list,
                                date_label: str,
                                date_key: str,
                                year_key: str,
                                season_key: str,
                                factory_key: str) -> None:
    """
    Render an expandable Excel upload area.  The user selects Year, Season,
    Factory and uploads a .xlsx file.  Rows are upserted into the ledger.
    """
    with st.expander("📂 Upload via Excel File", expanded=False):
        st.markdown(
            "Upload an **.xlsx** file with columns: "
            f"`{', '.join(expected_cols)}`. "
            "The **Year**, **Season**, **Factory**, and **Date** you select "
            "below will be applied to ALL rows in the uploaded file."
        )

        up_date = st.date_input("Date (applied to all rows)",
                                value=date.today(), key=date_key)
        up_year = st.selectbox("Year", YEARS, index=0, key=year_key)
        up_season = st.selectbox("Season", SEASONS, key=season_key)
        up_factory = st.selectbox("Factory", FACTORIES, key=factory_key)

        uploaded_file = st.file_uploader(
            "Choose an Excel file",
            type=['xlsx'],
            key=f"uploader_{page_key}",
        )

        if uploaded_file is not None:
            try:
                upload_df = pd.read_excel(uploaded_file, engine='openpyxl')
            except Exception as e:
                st.error(f"Failed to read Excel file: {e}")
                return

            # Validate columns
            missing = [c for c in expected_cols if c not in upload_df.columns]
            if missing:
                st.error(
                    f"Missing required columns: {', '.join(missing)}. "
                    f"Your file has: {', '.join(upload_df.columns)}."
                )
                return

            # Strip whitespace from text columns
            for col in ['Product Name', 'Product Size']:
                if col in upload_df.columns:
                    upload_df[col] = upload_df[col].astype(str).str.strip()

            # Validate no empty product names/sizes
            empty_names = upload_df['Product Name'].isna() | (upload_df['Product Name'] == '')
            empty_sizes = upload_df['Product Size'].isna() | (upload_df['Product Size'] == '')
            if empty_names.any() or empty_sizes.any():
                st.error("All rows must have a Product Name and Product Size.")
                return

            # Validate quantity column is numeric
            upload_df[quantity_col] = pd.to_numeric(upload_df[quantity_col], errors='coerce')
            if upload_df[quantity_col].isna().any():
                st.error(f"Column '{quantity_col}' must contain numeric values.")
                return
            upload_df[quantity_col] = upload_df[quantity_col].astype('int64')

            # Inject metadata columns
            upload_df['Date'] = pd.Timestamp(up_date)
            upload_df['Year'] = up_year
            upload_df['Season'] = up_season
            upload_df['Factory'] = up_factory

            # Reorder to canonical schema
            upload_df = upload_df[list(schema.keys())]

            preview_rows = min(len(upload_df), 5)
            st.markdown(f"**Preview** ({preview_rows} of {len(upload_df)} rows):")
            st.dataframe(upload_df.head(preview_rows), use_container_width=True, hide_index=True)

            if st.button(
                f"✅ Confirm Upload — {len(upload_df)} rows",
                use_container_width=True,
                type="primary",
                key=f"confirm_upload_{page_key}",
            ):
                count = bulk_commit_from_df(
                    ledger_name=ledger_name,
                    df=upload_df,
                    schema=schema,
                    match_cols=MATCH_COLS,
                    quantity_col=quantity_col,
                )
                st.toast(f"✅ {count} rows uploaded & merged successfully!", icon="✅")
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════
# Shared UI Helper — Inline Editable Ledger with Delete Checkbox
# ═══════════════════════════════════════════════════════════════════════
def render_ledger_with_delete(ledger_name: str,
                               sort_cols: list,
                               quantity_col: str,
                               delete_warning: str) -> None:
    """
    Render the ledger as an editable table with a delete checkbox column
    and an inline delete button.  Returns immediately if the ledger is empty.
    """
    df = st.session_state.get(ledger_name, pd.DataFrame())
    if df.empty:
        return

    df_sorted = df.sort_values(by=sort_cols).reset_index(drop=True)

    # Add a Delete checkbox column at the beginning
    editable = df_sorted.copy()
    editable.insert(0, 'Delete', False)

    # Convert Date to string for safe editing in data_editor
    if 'Date' in editable.columns:
        editable['Date'] = editable['Date'].dt.strftime('%Y-%m-%d')

    edited = st.data_editor(
        editable,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Delete': st.column_config.CheckboxColumn(
                "🗑️ Delete",
                default=False,
                width="small",
            ),
            'Date':          st.column_config.TextColumn("Date", width="small"),
            'Year':          st.column_config.NumberColumn("Year", width="small"),
            'Season':        st.column_config.TextColumn("Season", width="small"),
            'Factory':       st.column_config.TextColumn("Factory", width="small"),
            'Product Name':  st.column_config.TextColumn("Product Name"),
            'Product Size':  st.column_config.TextColumn("Size", width="small"),
            'Quantity':      st.column_config.NumberColumn("Qty", width="small"),
            'Quantity Produced': st.column_config.NumberColumn("Produced", width="small"),
        },
        key=f"ledger_editor_{ledger_name}",
    )

    selected = edited[edited['Delete'] == True]
    if not selected.empty:
        st.warning(f"🗑️ **{len(selected)} row(s)** checked for deletion. {delete_warning}")

        if st.button(
            f"🗑️ Delete {len(selected)} Checked Row(s)",
            use_container_width=True,
            type="secondary",
            key=f"delete_btn_{ledger_name}",
        ):
            # Map back to original DataFrame indices before the sort
            # We use the position-based index since we reset_index
            indices_to_drop = selected.index.tolist()
            delete_selected_records(ledger_name, indices_to_drop)
            st.toast(f"🗑️ Deleted {len(indices_to_drop)} record(s).", icon="🗑️")
            st.rerun()
    else:
        st.caption("Check the 🗑️ **Delete** box on rows you want to remove, then click the delete button that appears.")


# ═══════════════════════════════════════════════════════════════════════
# Sidebar Navigation
# ═══════════════════════════════════════════════════════════════════════
def render_sidebar_nav() -> str:
    """Render the navigation radio and warehouse status, return page label."""
    with st.sidebar:
        st.markdown("## 🏭 Supply Chain\nControl Tower")
        st.markdown("---")

        page = st.radio(
            "Navigate",
            [
                "📦 Distributor PO Intake",
                "⚙️ Factory Production Ledger",
                "📊 Cross-Functional Analytics",
            ],
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("### Warehouse Status")
        po_count = len(st.session_state.get('po_ledger', pd.DataFrame()))
        pr_count = len(st.session_state.get('production_ledger', pd.DataFrame()))
        st.metric("PO Records", po_count)
        st.metric("Production Records", pr_count)

        st.markdown("---")
        st.caption("v1.0.0 · Streamlit Community Cloud Ready")
        return page


# ═══════════════════════════════════════════════════════════════════════
# Page 1 — Distributor PO Intake Engine
# ═══════════════════════════════════════════════════════════════════════
def render_po_intake() -> None:
    """Distributor PO Intake page — manual form + Excel upload + ledger + delete."""
    st.header("📦 Distributor PO Intake Engine")
    st.markdown(
        "Submit purchase orders **manually** or **upload via Excel**. "
        "Duplicate product entries (same "
        "**Year + Season + Factory + Product Name + Size**) are "
        "**auto-aggregated** (quantities summed)."
    )

    # ── Manual Input Form ───────────────────────────────────────────
    with st.expander("➕ New Purchase Order (Manual)", expanded=True):
        with st.form("po_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                po_date = st.date_input("Date", value=date.today())
                po_year = st.selectbox("Year", YEARS, index=0)
                po_season = st.selectbox("Season", SEASONS)
            with c2:
                po_factory = st.selectbox("Factory", FACTORIES)
                po_product = st.text_input("Product Name",
                                           placeholder="e.g. Widget-A")
                po_size = st.text_input("Product Size",
                                        placeholder="e.g. M or 10x20cm")
            with c3:
                po_qty = st.number_input("Quantity",
                                         min_value=1, step=1, value=1)

            submitted = st.form_submit_button("📥 Submit PO",
                                              use_container_width=True,
                                              type="primary")
            if submitted:
                product_name = po_product.strip()
                product_size = po_size.strip()
                if not product_name:
                    st.error("Product Name is required.")
                elif not product_size:
                    st.error("Product Size is required.")
                else:
                    record = {
                        'Date': pd.Timestamp(po_date),
                        'Year': po_year,
                        'Season': po_season,
                        'Factory': po_factory,
                        'Product Name': product_name,
                        'Product Size': product_size,
                        'Quantity': po_qty,
                    }
                    commit_transaction(
                        ledger_name='po_ledger',
                        record=record,
                        schema=PO_LEDGER_SCHEMA,
                        match_cols=MATCH_COLS,
                        quantity_col='Quantity',
                    )
                    st.toast(
                        f"✅ PO committed — {product_name} ({product_size})"
                        f" ×{po_qty} → {po_factory}",
                        icon="✅",
                    )

    # ── Excel Upload Section ────────────────────────────────────────
    render_excel_upload_section(
        page_key='po',
        ledger_name='po_ledger',
        schema=PO_LEDGER_SCHEMA,
        quantity_col='Quantity',
        expected_cols=EXPECTED_EXCEL_COLS_PO,
        date_label='Date',
        date_key='up_po_date',
        year_key='up_po_year',
        season_key='up_po_season',
        factory_key='up_po_factory',
    )

    # ── Stateful Ledger ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Purchase Order Ledger")

    po_df = load_data('po_ledger')
    if po_df.empty:
        st.info("No purchase orders have been submitted yet.")
    else:
        render_ledger_with_delete(
            ledger_name='po_ledger',
            sort_cols=['Year', 'Season', 'Factory', 'Product Name', 'Product Size'],
            quantity_col='Quantity',
            delete_warning='Click the delete button below to permanently remove these rows.',
        )


# ═══════════════════════════════════════════════════════════════════════
# Page 2 — Factory Production Ledger Terminal
# ═══════════════════════════════════════════════════════════════════════
def render_production_ledger() -> None:
    """Factory Production Ledger page — manual form + Excel upload + ledger + delete."""
    st.header("⚙️ Factory Production Ledger Terminal")
    st.markdown(
        "Record actual production yields **manually** or **upload via Excel**. "
        "Entries are **auto-aggregated** by product name and size."
    )

    # ── Manual Input Form ───────────────────────────────────────────
    with st.expander("➕ Record Production (Manual)", expanded=True):
        with st.form("prod_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                prod_date = st.date_input("Date", value=date.today(),
                                          key="pd")
                prod_year = st.selectbox("Year", YEARS, index=0, key="py")
                prod_season = st.selectbox("Season", SEASONS, key="ps")
            with c2:
                prod_factory = st.selectbox("Factory", FACTORIES, key="pf")
                prod_product = st.text_input("Product Name",
                                             placeholder="e.g. Widget-A",
                                             key="pp")
                prod_size = st.text_input("Product Size",
                                          placeholder="e.g. M or 10x20cm",
                                          key="psz")
            with c3:
                prod_qty = st.number_input("Quantity Produced",
                                           min_value=1, step=1, value=1,
                                           key="pq")

            submitted = st.form_submit_button("🏭 Record Production",
                                              use_container_width=True,
                                              type="primary")
            if submitted:
                product_name = prod_product.strip()
                product_size = prod_size.strip()
                if not product_name:
                    st.error("Product Name is required.")
                elif not product_size:
                    st.error("Product Size is required.")
                else:
                    record = {
                        'Date': pd.Timestamp(prod_date),
                        'Year': prod_year,
                        'Season': prod_season,
                        'Factory': prod_factory,
                        'Product Name': product_name,
                        'Product Size': product_size,
                        'Quantity Produced': prod_qty,
                    }
                    commit_transaction(
                        ledger_name='production_ledger',
                        record=record,
                        schema=PRODUCTION_LEDGER_SCHEMA,
                        match_cols=MATCH_COLS,
                        quantity_col='Quantity Produced',
                    )
                    st.toast(
                        f"✅ Production recorded — {product_name} ({product_size})"
                        f" ×{prod_qty} at {prod_factory}",
                        icon="✅",
                    )

    # ── Excel Upload Section ────────────────────────────────────────
    render_excel_upload_section(
        page_key='prod',
        ledger_name='production_ledger',
        schema=PRODUCTION_LEDGER_SCHEMA,
        quantity_col='Quantity Produced',
        expected_cols=EXPECTED_EXCEL_COLS_PROD,
        date_label='Date',
        date_key='up_pr_date',
        year_key='up_pr_year',
        season_key='up_pr_season',
        factory_key='up_pr_factory',
    )

    # ── Stateful Ledger ─────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📋 Production Ledger")

    pr_df = load_data('production_ledger')
    if pr_df.empty:
        st.info("No production records have been submitted yet.")
    else:
        render_ledger_with_delete(
            ledger_name='production_ledger',
            sort_cols=['Year', 'Season', 'Factory', 'Product Name', 'Product Size'],
            quantity_col='Quantity Produced',
            delete_warning='Click the delete button below to permanently remove these rows.',
        )


# ═══════════════════════════════════════════════════════════════════════
# Page 3 — Cross-Functional Performance Analytics & Export Matrix
# ═══════════════════════════════════════════════════════════════════════
def render_analytics() -> None:
    """Analytics dashboard: filters, OUTER JOIN, KPI, chart, grid, export."""
    st.header("📊 Cross-Functional Performance Analytics")
    st.markdown(
        "Compare **demand** (Purchase Orders) vs **actual yield** "
        "(Production) with KPI computation and export."
    )

    po_df = load_data('po_ledger')
    pr_df = load_data('production_ledger')

    if po_df.empty and pr_df.empty:
        st.info("No data available.  Submit POs and Production records first.")
        return

    # ── Sidebar Filters ─────────────────────────────────────────────
    st.sidebar.markdown("### 🔍 Analytics Filters")

    avail_years = sorted(
        set(po_df['Year'].unique()) | set(pr_df['Year'].unique())
    ) if not (po_df.empty or pr_df.empty) else sorted(
        set(po_df['Year'].unique()) if not po_df.empty
        else set(pr_df['Year'].unique())
    )
    if not avail_years:
        avail_years = YEARS

    sel_year = st.sidebar.selectbox("Year", avail_years, key="ay")

    po_seas = set(po_df[po_df['Year'] == sel_year]['Season'].unique()) if not po_df.empty else set()
    pr_seas = set(pr_df[pr_df['Year'] == sel_year]['Season'].unique()) if not pr_df.empty else set()
    avail_seasons = sorted(
        po_seas | pr_seas,
        key=lambda s: ['Spring', 'Summer', 'Fall', 'Winter'].index(s)
        if s in ('Spring', 'Summer', 'Fall', 'Winter') else 4,
    )
    if not avail_seasons:
        avail_seasons = SEASONS
    sel_season = st.sidebar.selectbox("Season", avail_seasons, key="as")

    po_fact = set(
        po_df[(po_df['Year'] == sel_year) & (po_df['Season'] == sel_season)]['Factory'].unique()
    ) if not po_df.empty else set()
    pr_fact = set(
        pr_df[(pr_df['Year'] == sel_year) & (pr_df['Season'] == sel_season)]['Factory'].unique()
    ) if not pr_df.empty else set()
    avail_factories = sorted(po_fact | pr_fact)
    if not avail_factories:
        avail_factories = FACTORIES
    sel_factory = st.sidebar.selectbox("Factory", avail_factories, key="af")

    # ── ETL: Extract Slices ─────────────────────────────────────────
    po_slice = (
        po_df[
            (po_df['Year'] == sel_year)
            & (po_df['Season'] == sel_season)
            & (po_df['Factory'] == sel_factory)
        ].copy()
        if not po_df.empty else pd.DataFrame()
    )
    pr_slice = (
        pr_df[
            (pr_df['Year'] == sel_year)
            & (pr_df['Season'] == sel_season)
            & (pr_df['Factory'] == sel_factory)
        ].copy()
        if not pr_df.empty else pd.DataFrame()
    )

    if po_slice.empty and pr_slice.empty:
        st.warning(f"No data for **{sel_factory}** · {sel_season} {sel_year}.")
        return

    # ── Aggregation (sum per product + size) ────────────────────────
    GROUP_AGGS = ['Product Name', 'Product Size']

    po_agg = (
        po_slice.groupby(GROUP_AGGS, as_index=False)['Quantity'].sum()
        if not po_slice.empty
        else pd.DataFrame(columns=GROUP_AGGS + ['Quantity'])
    )
    pr_agg = (
        pr_slice.groupby(GROUP_AGGS, as_index=False)['Quantity Produced'].sum()
        if not pr_slice.empty
        else pd.DataFrame(columns=GROUP_AGGS + ['Quantity Produced'])
    )

    if po_agg.empty and pr_agg.empty:
        st.warning(f"No data for **{sel_factory}** · {sel_season} {sel_year}.")
        return

    # ── OUTER JOIN on 'Product Name' + 'Product Size' ───────────────
    if po_agg.empty:
        comparison = pr_agg.copy()
        comparison['Quantity'] = 0
    elif pr_agg.empty:
        comparison = po_agg.copy()
        comparison['Quantity Produced'] = 0
    else:
        comparison = pd.merge(po_agg, pr_agg, on=GROUP_AGGS, how='outer')

    comparison = comparison.fillna(0)
    comparison['Quantity'] = comparison['Quantity'].astype('int64')
    comparison['Quantity Produced'] = comparison['Quantity Produced'].astype('int64')

    # ── KPI: Completion Rate ────────────────────────────────────────
    def completion_rate(row):
        req = row['Quantity']
        prod = row['Quantity Produced']
        if req == 0 and prod > 0:
            return 100.0
        if req == 0:
            return 0.0
        return round((prod / req) * 100, 2)

    comparison['Completion Rate (%)'] = comparison.apply(completion_rate, axis=1)

    total_requested = int(comparison['Quantity'].sum())
    total_produced = int(comparison['Quantity Produced'].sum())
    n_products = len(comparison)

    if total_requested == 0 and total_produced > 0:
        overall_kpi = 100.0
    elif total_requested == 0:
        overall_kpi = 0.0
    else:
        overall_kpi = round((total_produced / total_requested) * 100, 2)

    # ── KPI Metric Cards ────────────────────────────────────────────
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("📦 Total Requested", f"{total_requested:,}")
    k2.metric("🏭 Total Produced", f"{total_produced:,}")
    k3.metric("📊 Product-Size Variants", n_products)
    k4.metric("✅ Completion Rate", f"{overall_kpi}%")

    st.markdown("---")

    # ── Grouped Bar Chart ───────────────────────────────────────────
    st.subheader("📈 Demand vs Yield Comparison")

    chart_df = comparison.copy()
    chart_df['Product (Size)'] = chart_df['Product Name'] + ' (' + chart_df['Product Size'] + ')'

    fig = px.bar(
        chart_df,
        x='Product (Size)',
        y=['Quantity', 'Quantity Produced'],
        barmode='group',
        title=f"Demand vs Production — {sel_factory} ({sel_season} {sel_year})",
        labels={
            'value': 'Quantity',
            'variable': 'Metric',
            'Product (Size)': 'Product (Size)',
        },
        color_discrete_map={
            'Quantity': '#1f77b4',
            'Quantity Produced': '#2ca02c',
        },
        text_auto='.0f',
    )
    fig.update_layout(
        xaxis_title="Product (Size)",
        yaxis_title="Quantity",
        legend_title="Metric",
        height=500,
        hovermode='x unified',
        template='plotly_white',
    )
    fig.update_traces(textposition='outside', textfont_size=10)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── Comparison Grid ─────────────────────────────────────────────
    st.subheader("📋 Compiled Comparison Matrix")
    display = comparison.copy()
    display['Completion Rate (%)'] = display['Completion Rate (%)'].apply(
        lambda v: f"{v:.2f}%"
    )
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Product Name':         st.column_config.TextColumn("Product"),
            'Product Size':         st.column_config.TextColumn("Size"),
            'Quantity':             st.column_config.NumberColumn("Requested"),
            'Quantity Produced':    st.column_config.NumberColumn("Produced"),
            'Completion Rate (%)':  st.column_config.TextColumn("Completion"),
        },
    )

    # ── Excel Export ────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📤 Export to Excel")

    export = comparison.copy()
    export['Year'] = sel_year
    export['Season'] = sel_season
    export['Factory'] = sel_factory
    export = export[
        ['Year', 'Season', 'Factory', 'Product Name', 'Product Size',
         'Quantity', 'Quantity Produced', 'Completion Rate (%)']
    ]

    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
        export.to_excel(writer, index=False, sheet_name='SCM Metrics')
        pd.DataFrame({
            'Metric': [
                'Factory', 'Season', 'Year',
                'Total Requested', 'Total Produced',
                'Overall Completion Rate (%)',
            ],
            'Value': [
                sel_factory, sel_season, sel_year,
                total_requested, total_produced, overall_kpi,
            ],
        }).to_excel(writer, index=False, sheet_name='Summary')

    fname = f"SCM_Metrics_{sel_year}_{sel_season}_{sel_factory}.xlsx"
    st.download_button(
        label="⬇️ Download Excel Report",
        data=buf.getvalue(),
        file_name=fname,
        mime=(
            "application/vnd.openxmlformats-officedocument"
            ".spreadsheetml.sheet"
        ),
        use_container_width=True,
        type="primary",
    )


# ═══════════════════════════════════════════════════════════════════════
# Application Entry Point
# ═══════════════════════════════════════════════════════════════════════
def main() -> None:
    """Top-level orchestrator: seed warehouse, render sidebar, dispatch pages."""
    initialize_data_warehouse()

    page = render_sidebar_nav()

    if "Distributor PO" in page:
        render_po_intake()
    elif "Factory Production" in page:
        render_production_ledger()
    elif "Cross-Functional" in page:
        render_analytics()


if __name__ == "__main__":
    main()