import streamlit as st
import pandas as pd
import time
from data_provider import init_portfolio_pipeline, update_uploaded_portfolio, get_portfolio_metrics

st.set_page_config(page_title="ETF Tracker", layout="centered")
init_portfolio_pipeline()

st.markdown("### 📊 Personal Portfolio Engine")

# 1. Automatic Frontend File Uploader Dropzone
uploaded_file = st.file_uploader(
    "Upload your Portfolio File (CSV or Excel)", 
    type=["csv", "xlsx", "xls"]
)

if uploaded_file is not None:
    try:
        # Load file dynamically based on file type extensions
        if uploaded_file.name.endswith(".csv"):
            user_df = pd.read_csv(uploaded_file)
        else:
            user_df = pd.read_excel(uploaded_file)
            
        # Push file to our streaming background layer
        update_uploaded_portfolio(user_df)
        st.success("Portfolio template parsed! Syncing live market tickers...")
    except Exception as e:
        st.error(f"Error loading your document format: {e}")

# 2. Grab current live tracking information
tracked_df, last_sync = get_portfolio_metrics()

if tracked_df.empty:
    st.info("💡 Please upload an Excel or CSV file matching your asset columns above to begin generating metrics.")
else:
    # 3. Structural metrics summaries for mobile display
    total_inv = tracked_df["Investment"].dropna().sum() if "Investment" in tracked_df.columns else 0
    
    st.metric(label="Total Tracked Core Base Value", value=f"₹ {round(total_inv, 2):,}")
    if last_sync:
        st.caption(f"🔄 Market Tickers Last Synced At: {last_sync.strftime('%H:%M:%S')} (10m delay interval)")
        
    # Rearranging layout to emphasize the requested iNAV and LTP columns
    display_cols = ["Name", "Quantity", "Avg Price", "LTP", "iNAV"]
    existing_cols = [c for c in display_cols if c in tracked_df.columns]
    
    st.write("#### 📈 Live Real-time Tracked Matrix")
    st.dataframe(tracked_df[existing_cols], use_container_width=True)

# 4. Mobile screen frame loop re-render ticks
time.sleep(5)
st.rerun()
