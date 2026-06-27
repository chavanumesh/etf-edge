import streamlit as st
import pandas as pd
import time
from data_provider import init_portfolio_pipeline, update_uploaded_portfolio, get_portfolio_metrics

st.set_page_config(page_title="ETF Edge Tracker", layout="centered", initial_sidebar_state="collapsed")
init_portfolio_pipeline()

st.markdown("### 📱 My ETF Edge Portfolio Tracker")

uploaded_file = st.file_uploader("Upload Portfolio Layout (CSV or Excel)", type=["csv", "xlsx"])

if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            user_df = pd.read_csv(uploaded_file)
        else:
            user_df = pd.read_excel(uploaded_file)
        
        update_uploaded_portfolio(user_df)
        st.success("Structure Synchronized! Parsing ticker arrays...")
    except Exception as e:
        st.error(f"Error handling document: {e}")

df, last_sync = get_portfolio_metrics()

if df.empty:
    st.info("💡 Drop your Excel tracker sheet template above to visualize current values & iNAV.")
else:
    # Portfolio Aggregate Metrics Summaries
    total_inv = df["Investment"].sum()
    total_cur = df["Current Value"].sum()
    total_pnl = total_cur - total_inv
    pnl_pct = (total_pnl / total_inv) * 100 if total_inv > 0 else 0
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Total Portfolio Value", value=f"₹ {round(total_cur, 2):,}")
    with col2:
        st.metric(
            label="Net Return P&L", 
            value=f"₹ {round(total_pnl, 2):,}", 
            delta=f"{round(pnl_pct, 2)}%"
        )
        
    if last_sync:
        st.caption(f"⏱️ Live Sync Timestamp: {last_sync.strftime('%H:%M:%S')} (5m Refresh Mode)")
    
    st.write("#### 📊 Asset Matrix Details")
    
    # Clean display configuration ensuring requested target tracking columns are stacked first
    ordered_cols = ["Name", "Quantity", "Last Traded", "iNAV", "P&L", "P&L %"]
    existing_cols = [c for c in ordered_cols if c in df.columns]
    
    # Custom Number formatting adjustments for easy phone scanning
    formatted_df = df[existing_cols].copy()
    if "Last Traded" in formatted_df.columns:
        formatted_df["Last Traded"] = formatted_df["Last Traded"].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "-")
    if "iNAV" in formatted_df.columns:
        formatted_df["iNAV"] = formatted_df["iNAV"].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "-")
    if "P&L" in formatted_df.columns:
        formatted_df["P&L"] = formatted_df["P&L"].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) else "-")
    if "P&L %" in formatted_df.columns:
        formatted_df["P&L %"] = formatted_df["P&L %"].map(lambda x: f"{x:.2f}%" if pd.notnull(x) else "-")

    st.dataframe(formatted_df, use_container_width=True, hide_index=True)

# UI auto-update redraw tick loop
time.sleep(5)
st.rerun()
