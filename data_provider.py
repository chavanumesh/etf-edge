import streamlit as st
import pandas as pd
import time
from data_provider import init_portfolio_pipeline, update_uploaded_portfolio, get_portfolio_metrics

st.set_page_config(
    page_title="ETF Edge Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Page background */
.stApp { background: #0f172a; }

/* Hide default Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 1.5rem 2rem 2rem; max-width: 1400px; }

/* ── Hero header ── */
.hero {
    background: linear-gradient(135deg, #1e3a5f 0%, #1d4ed8 60%, #7c3aed 100%);
    border-radius: 16px;
    padding: 24px 28px 20px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -40px; right: -40px;
    width: 200px; height: 200px;
    background: rgba(255,255,255,0.05);
    border-radius: 50%;
}
.hero-title {
    font-size: 24px; font-weight: 800;
    color: #ffffff; letter-spacing: -0.5px; margin: 0;
}
.hero-sub {
    font-size: 13px; color: #93c5fd;
    margin-top: 4px;
}
.hero-sync {
    font-size: 11px; color: #94a3b8;
    margin-top: 10px; display: flex; align-items: center; gap: 6px;
}
.pulse {
    width: 8px; height: 8px; border-radius: 50%;
    background: #22c55e;
    animation: pulse 1.5s infinite;
    display: inline-block;
}
@keyframes pulse {
    0%,100% { opacity: 1; transform: scale(1); }
    50%      { opacity: 0.4; transform: scale(0.8); }
}

/* ── Metric cards ── */
.cards-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 14px;
    margin-bottom: 24px;
}
.mcard {
    border-radius: 14px;
    padding: 18px 20px;
    position: relative; overflow: hidden;
}
.mcard-invested { background: linear-gradient(135deg, #1e3a5f, #1d4ed8); }
.mcard-value    { background: linear-gradient(135deg, #064e3b, #059669); }
.mcard-pnl-pos  { background: linear-gradient(135deg, #052e16, #16a34a); }
.mcard-pnl-neg  { background: linear-gradient(135deg, #450a0a, #dc2626); }
.mcard-holdings { background: linear-gradient(135deg, #1e1b4b, #7c3aed); }

.mcard-label {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.08em; color: rgba(255,255,255,0.65); margin-bottom: 8px;
}
.mcard-value-text {
    font-size: 22px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px;
}
.mcard-delta {
    font-size: 12px; font-weight: 600; margin-top: 5px;
    display: inline-flex; align-items: center; gap: 4px;
    background: rgba(255,255,255,0.12);
    padding: 2px 8px; border-radius: 99px; color: #fff;
}

/* ── Section header ── */
.section-header {
    font-size: 16px; font-weight: 700; color: #f1f5f9;
    margin-bottom: 12px; display: flex; align-items: center; gap: 8px;
}
.section-badge {
    font-size: 11px; background: #1d4ed8; color: #fff;
    padding: 2px 8px; border-radius: 99px; font-weight: 600;
}

/* ── Upload zone ── */
.uploadzone {
    background: #1e293b;
    border: 2px dashed #334155;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 20px;
    transition: border-color .2s;
}

/* ── Table styling ── */
.stDataFrame {
    border-radius: 12px !important;
    overflow: hidden !important;
    border: 1px solid #1e293b !important;
}
.stDataFrame thead tr th {
    background: #1e293b !important;
    color: #94a3b8 !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.06em !important;
    padding: 10px 14px !important;
    border-bottom: 1px solid #334155 !important;
}
.stDataFrame tbody tr { background: #0f172a !important; }
.stDataFrame tbody tr:nth-child(even) { background: #111827 !important; }
.stDataFrame tbody tr:hover { background: #1e293b !important; }
.stDataFrame tbody tr td {
    color: #e2e8f0 !important;
    font-size: 13px !important;
    padding: 9px 14px !important;
    border-bottom: 1px solid #1e293b !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    background: #1e293b !important;
    border-radius: 12px !important;
    padding: 6px !important;
}
[data-testid="stFileUploader"] label { color: #94a3b8 !important; font-size: 13px !important; }

/* Spinner */
.stSpinner > div { border-top-color: #1d4ed8 !important; }

/* Info box */
.stAlert { background: #1e293b !important; border: 1px solid #334155 !important; border-radius: 10px !important; color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

# ── Init ──────────────────────────────────────────────────────────────────────
init_portfolio_pipeline()

# ── Upload ────────────────────────────────────────────────────────────────────
uploaded_file = st.file_uploader(
    "📂  Upload today's Portfolio CSV or Excel",
    type=["csv", "xlsx"],
    label_visibility="visible"
)

if uploaded_file is not None:
    if "last_uploaded_name" not in st.session_state or st.session_state.last_uploaded_name != uploaded_file.name:
        with st.spinner("Fetching live prices & computing P&L…"):
            try:
                user_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith(".csv") else pd.read_excel(uploaded_file)
                update_uploaded_portfolio(user_df)
                st.session_state.last_uploaded_name = uploaded_file.name
                st.rerun()
            except Exception as e:
                st.error(f"Upload error: {e}")

# ── Data ──────────────────────────────────────────────────────────────────────
df, last_sync, inav_source = get_portfolio_metrics()

# ── Hero header ───────────────────────────────────────────────────────────────
sync_str = last_sync.strftime('%d %b %Y · %H:%M:%S IST') if last_sync else "Awaiting data…"
st.markdown(f"""
<div class="hero">
  <div class="hero-title">📊 ETF Edge Portfolio Tracker</div>
  <div class="hero-sub">Indian ETF · Real-time iNAV · P&amp;L Intelligence</div>
  <div class="hero-sync">
    <span class="pulse"></span>
    Live Sync &nbsp;·&nbsp; {sync_str} &nbsp;·&nbsp; 5-min auto-refresh
  </div>
</div>
""", unsafe_allow_html=True)

# ── Empty state ───────────────────────────────────────────────────────────────
if df.empty:
    st.markdown("""
    <div style="text-align:center; padding:60px 20px; color:#475569;">
      <div style="font-size:48px">📋</div>
      <div style="font-size:16px; font-weight:700; color:#94a3b8; margin-top:12px;">No portfolio loaded</div>
      <div style="font-size:13px; margin-top:6px;">Upload your daily CSV / Excel above to get started.</div>
    </div>
    """, unsafe_allow_html=True)
else:
    # ── Compute totals ────────────────────────────────────────────────────────
    total_inv  = df["Investment"].sum()    if "Investment"    in df.columns else 0
    total_cur  = df["Current Value"].sum() if "Current Value" in df.columns else 0
    total_pnl  = total_cur - total_inv
    pnl_pct    = (total_pnl / total_inv * 100) if total_inv > 0 else 0
    n_holdings = len(df)
    pnl_card   = "mcard-pnl-pos" if total_pnl >= 0 else "mcard-pnl-neg"
    pnl_arrow  = "▲" if total_pnl >= 0 else "▼"

    # Count signals
    if "iNAV" in df.columns and "Last Traded" in df.columns:
        df["_sig_pct"] = ((df["Last Traded"] - df["iNAV"]) / df["iNAV"] * 100).round(2)
        n_discount = (df["_sig_pct"] < -0.5).sum()
        n_premium  = (df["_sig_pct"] >  0.5).sum()
    else:
        n_discount = n_premium = 0

    # ── Metric cards ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="cards-row">
      <div class="mcard mcard-invested">
        <div class="mcard-label">Total Invested</div>
        <div class="mcard-value-text">₹{total_inv:,.0f}</div>
        <div class="mcard-delta">📂 {n_holdings} holdings</div>
      </div>
      <div class="mcard mcard-value">
        <div class="mcard-label">Portfolio Value</div>
        <div class="mcard-value-text">₹{total_cur:,.0f}</div>
        <div class="mcard-delta">📡 iNAV live</div>
      </div>
      <div class="mcard {pnl_card}">
        <div class="mcard-label">Net P&amp;L</div>
        <div class="mcard-value-text">₹{abs(total_pnl):,.0f}</div>
        <div class="mcard-delta">{pnl_arrow} {abs(pnl_pct):.2f}%</div>
      </div>
      <div class="mcard mcard-holdings">
        <div class="mcard-label">iNAV Signals</div>
        <div class="mcard-value-text" style="font-size:18px">
          🟢 {n_discount} &nbsp; 🔴 {n_premium}
        </div>
        <div class="mcard-delta">Discount · Premium</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Asset matrix ──────────────────────────────────────────────────────────
    st.markdown(f"""
    <div class="section-header">
      📋 Asset Matrix
      <span class="section-badge">{n_holdings} ETFs</span>
    </div>
    """, unsafe_allow_html=True)

    ordered_cols = ["Name", "Quantity", "Avg Price", "Investment",
                    "Last Traded", "iNAV", "P&L", "P&L %"]
    existing_cols = [c for c in ordered_cols if c in df.columns]
    display_df = df[existing_cols].copy()
    display_df.rename(columns={"Investment": "Total Invested"}, inplace=True)

    # Add Buy/Sell/Hold signal column
    if "iNAV" in display_df.columns and "Last Traded" in display_df.columns:
        def signal(row):
            try:
                pct = (float(str(row["Last Traded"]).replace("₹","").replace(",",""))
                       - float(str(row["iNAV"]).replace("₹","").replace(",",""))) \
                      / float(str(row["iNAV"]).replace("₹","").replace(",","")) * 100
                if pct < -0.5:  return "🟢 BUY"
                if pct >  0.5:  return "🔴 SELL"
                return "🟡 HOLD"
            except Exception:
                return "-"

    # Format columns
    for col in ["Avg Price", "Total Invested", "Last Traded", "iNAV"]:
        if col in display_df.columns:
            display_df[col] = display_df[col].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) and x != "-" else "-")

    if "P&L" in display_df.columns:
        display_df["P&L"] = display_df["P&L"].map(
            lambda x: f"+₹{x:,.2f}" if pd.notnull(x) and x >= 0 else (f"-₹{abs(x):,.2f}" if pd.notnull(x) else "-")
        )
    if "P&L %" in display_df.columns:
        display_df["P&L %"] = display_df["P&L %"].map(
            lambda x: f"+{x:.2f}%" if pd.notnull(x) and x >= 0 else (f"{x:.2f}%" if pd.notnull(x) else "-")
        )

    # Signal column (compute on raw df before formatting)
    if "iNAV" in df.columns and "Last Traded" in df.columns:
        display_df["Signal"] = df.apply(signal, axis=1)

    st.dataframe(display_df, use_container_width=True, hide_index=True, height=460)

    # ── Footer ────────────────────────────────────────────────────────────────
    st.markdown(f"""
    <div style="margin-top:20px; padding:14px 18px; background:#1e293b; border-radius:10px;
                font-size:11px; color:#64748b; display:flex; gap:24px; flex-wrap:wrap;">
      <span>🟢 <b style="color:#94a3b8">BUY</b> — trading at discount to iNAV (&lt;−0.5%)</span>
      <span>🔴 <b style="color:#94a3b8">SELL</b> — trading at premium to iNAV (&gt;+0.5%)</span>
      <span>🟡 <b style="color:#94a3b8">HOLD</b> — within fair value band (±0.5%)</span>
      <span style="margin-left:auto">iNAV source: <b style="color:#93c5fd">{inav_source}</b></span>
    </div>
    """, unsafe_allow_html=True)

time.sleep(300)
st.rerun()
