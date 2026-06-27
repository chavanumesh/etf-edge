import streamlit as st
import pandas as pd
import time
from data_provider import init_portfolio_pipeline, update_uploaded_portfolio, get_portfolio_metrics

st.set_page_config(page_title="ETF Edge Tracker", layout="centered", initial_sidebar_state="collapsed")

init_portfolio_pipeline()

st.markdown("### 📱 My ETF Edge Portfolio Tracker")

uploaded_file = st.file_uploader("Upload Portfolio Layout (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    if "last_uploaded_name" not in st.session_state or st.session_state.last_uploaded_name != uploaded_file.name:
        with st.spinner("Processing template structures & fetching live price quotes..."):
            try:
                if uploaded_file.name.endswith(".csv"):
                    user_df = pd.read_csv(uploaded_file)
                else:
                    user_df = pd.read_excel(uploaded_file)

                update_uploaded_portfolio(user_df)
                st.session_state.last_uploaded_name = uploaded_file.name
                st.rerun()
            except Exception as e:
                st.error(f"Error handling document: {e}")

df, last_sync = get_portfolio_metrics()

if df.empty:
    st.info("💡 Drop your portfolio Excel/CSV above to visualize current values, iNAV & P&L.")
else:
    # ── Summary metrics ──────────────────────────────────────────────────────
    total_inv = df["Investment"].sum() if "Investment" in df.columns else 0
    total_cur = df["Current Value"].sum() if "Current Value" in df.columns else 0
    total_pnl = total_cur - total_inv
    pnl_pct   = (total_pnl / total_inv * 100) if total_inv > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Total Invested", value=f"₹ {total_inv:,.2f}")
    with col2:
        st.metric(label="Portfolio Value", value=f"₹ {total_cur:,.2f}")
    with col3:
        st.metric(
            label="Net P&L",
            value=f"₹ {total_pnl:,.2f}",
            delta=f"{pnl_pct:.2f}%"
        )

    if last_sync:
        st.caption(f"⏱️ Live Sync: {last_sync.strftime('%H:%M:%S')} (5-min refresh)")

    # ── Asset Matrix ─────────────────────────────────────────────────────────
    st.write("#### 📊 Asset Matrix Details")

    # Column order: Avg Price + Investment added after Quantity
    ordered_cols = [
        "Name",
        "Quantity",
        "Avg Price",        # ← NEW
        "Investment",       # ← NEW  (Total Amount Invested = Qty × Avg Price)
        "Last Traded",
        "iNAV",
        "P&L",
        "P&L %",
    ]
    existing_cols = [c for c in ordered_cols if c in df.columns]

    formatted_df = df[existing_cols].copy()

    # Rename for cleaner display
    formatted_df.rename(columns={"Investment": "Total Invested"}, inplace=True)

    # Format numeric columns
    rupee_cols = ["Avg Price", "Total Invested", "Last Traded", "iNAV", "P&L"]
    for col in rupee_cols:
        if col in formatted_df.columns:
            formatted_df[col] = formatted_df[col].map(
                lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "-"
            )

    if "P&L %" in formatted_df.columns:
        formatted_df["P&L %"] = formatted_df["P&L %"].map(
            lambda x: f"{x:.2f}%" if pd.notnull(x) else "-"
        )

    st.dataframe(formatted_df, use_container_width=True, hide_index=True)

time.sleep(5)
st.rerun()
