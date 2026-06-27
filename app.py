import streamlit as st
import time
from data_provider import initialize_data_pipeline, get_latest_metrics
from metrics import calculate_proxy_inav

st.set_page_config(
    page_title="Mobile iNAV", 
    layout="centered", 
    initial_sidebar_state="collapsed"
)

initialize_data_pipeline()
df, last_update = get_latest_metrics()

st.markdown("### 📱 Personal Proxy iNAV")

if df.empty:
    st.info("Syncing background data layer...")
    time.sleep(2)
    st.rerun()

current_inav = calculate_proxy_inav(df)

st.metric(label="Calculated Proxy iNAV", value=f"₹ {current_inav}")
st.caption(f"⏱️ Delay: ~10m | Last Sync: {last_update.strftime('%H:%M:%S') if last_update else 'N/A'}")

with st.expander("🔍 View Component Allocations", expanded=False):
    st.dataframe(df[["ticker", "underlying_price"]], use_container_width=True)

time.sleep(5)
st.rerun()
