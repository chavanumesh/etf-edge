import pandas as pd
import yfinance as yf
import requests
import threading
import time
import datetime

# ── Cache ─────────────────────────────────────────────────────────────────────
_PORTFOLIO_CACHE = {
    "raw_df":       pd.DataFrame(),
    "enriched_df":  pd.DataFrame(),
    "last_updated": None,
    "inav_source":  "—"
}
_CACHE_LOCK = threading.Lock()

# ── ETF Name → yfinance ticker ────────────────────────────────────────────────
TICKER_MAP = {
    "CPSE ETF":                                "CPSEETF.NS",
    "Groww BSE Power ETF":                     "POWERETF.NS",
    "HDFC Nifty 200 Momentum 30 ETF":          "HDFCMOM30.NS",
    "HDFC Nifty Bank ETF":                     "HDFCBANKETF.NS",
    "ICICI Pru Nifty 100 Low Vol 30 ETF":      "ICICILOVOL.NS",
    "ICICI Pru Nifty 200 Value 30 ETF":        "ICICIVALUE.NS",
    "ICICI Pru Nifty 50 Value 20 ETF":         "ICICINV20.NS",
    "ICICI Pru Nifty Alpha Low Volatility 30": "ICICIALV30.NS",
    "ICICI Pru Nifty Auto ETF":                "ICICIAUTO.NS",
    "ICICI Pru Nifty FMCG ETF":               "ICICIFMCG.NS",
    "ICICI Pru Nifty Metal ETF":              "ICICIMETAL.NS",
    "ICICI Pru Nifty Midcap 150 ETF":         "ICICIMID150.NS",
    "ICICI Pru Nifty Next 50 ETF":            "ICICINXT50.NS",
    "ICICI Pru Nifty Oil & Gas ETF":          "ICICIOIL.NS",
    "ICICI Pru Nifty Private Bank ETF":       "ICICIPRIVAT.NS",
    "Mirae Asset Gold ETF":                   "MAFITGOLDA.NS",
    "Mirae Asset Hang Seng Tech ETF":         "MAHKTECH.NS",
    "Mirae Asset Nifty Midcap 150 ETF":       "MANF150ETF.NS",
    "Motilal Oswal Nasdaq 100 ETF":           "MON100.NS",
    "Motilal Oswal Nifty 500 ETF":            "MONIFTY500.NS",
    "Motilal Oswal Nifty India Defence ETF":  "MODEFENCE.NS",
    "Motilal Oswal Nifty Smallcap 250 ETF":   "MASPTOP50.NS",
    "Nippon Nifty 50 ETF (NIFTYBEES)":        "NIFTYBEES.NS",
    "Nippon Nifty IT ETF (ITBEES)":           "ITBEES.NS",
    "Nippon Pharma ETF (PHARMABEES)":         "PHARMABEES.NS",
    "Nippon Silver ETF (SILVERBEES)":         "SILVERBEES.NS",
    "TATA Silver ETF":                        "TATASILVER.NS",
    "Tata Gold ETF":                          "TATAGOLD.NS",
    "Zerodha Nifty 50 ETF":                   "ZETFNIF50.NS",
    "Embassy Office Parks REIT":              "EMBASSY.NS",
    "IRB InvIT Fund":                         "IRBINVIT.NS",
    "Powergrid Infrastructure":               "PGINVIT.NS",
}

# NSE symbol → ETF display name (for iNAV matching)
_NSE_SYMBOL_TO_NAME = {v.replace(".NS", ""): k for k, v in TICKER_MAP.items()}

# ── NSE iNAV session ──────────────────────────────────────────────────────────
_NSE_SESSION = requests.Session()
_NSE_SESSION.headers.update({
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
    "X-Requested-With": "XMLHttpRequest",
})
_NSE_COOKIE_INITIALIZED = False


def _init_nse_session():
    global _NSE_COOKIE_INITIALIZED
    if not _NSE_COOKIE_INITIALIZED:
        try:
            _NSE_SESSION.get("https://www.nseindia.com", timeout=12)
            _NSE_COOKIE_INITIALIZED = True
        except Exception as e:
            print(f"NSE session init failed: {e}")


def fetch_inav_from_nse() -> dict:
    """Fetch real iNAV values from NSE. Returns {ETF name: iNAV float}."""
    global _NSE_COOKIE_INITIALIZED
    _init_nse_session()
    inav_map = {}
    try:
        resp = _NSE_SESSION.get("https://www.nseindia.com/api/etf", timeout=12)
        resp.raise_for_status()
        records = resp.json().get("data", [])
        for item in records:
            symbol    = str(item.get("symbol", "")).strip()
            raw_inav  = item.get("iNavValue", None)
            if raw_inav and str(raw_inav).strip() not in ("", "-", "N/A"):
                try:
                    inav_val     = float(str(raw_inav).replace(",", ""))
                    display_name = _NSE_SYMBOL_TO_NAME.get(symbol)
                    if display_name:
                        inav_map[display_name] = inav_val
                except ValueError:
                    pass
        print(f"NSE iNAV: fetched {len(inav_map)} values.")
    except Exception as e:
        print(f"NSE iNAV fetch failed — using LTP proxy: {e}")
        _NSE_COOKIE_INITIALIZED = False
    return inav_map


# ── Core pipeline ─────────────────────────────────────────────────────────────
def process_data_snapshot():
    global _PORTFOLIO_CACHE

    with _CACHE_LOCK:
        working_df = _PORTFOLIO_CACHE["raw_df"].copy()

    if working_df.empty or "Name" not in working_df.columns:
        return

    # 1. Fetch LTP via yfinance
    tickers       = [TICKER_MAP.get(str(n).strip()) for n in working_df["Name"]]
    valid_tickers = [t for t in tickers if t]
    ltp_dict      = {}

    if valid_tickers:
        try:
            data = yf.download(valid_tickers, period="1d", group_by="ticker",
                               progress=False, threads=True)
            for t in valid_tickers:
                try:
                    ltp_dict[t] = float(
                        data["Close"].iloc[-1] if len(valid_tickers) == 1
                        else data[t]["Close"].iloc[-1]
                    )
                except Exception:
                    ltp_dict[t] = None
        except Exception as e:
            print(f"yfinance error: {e}")

    working_df["Last Traded"] = [
        ltp_dict.get(TICKER_MAP.get(str(n).strip())) for n in working_df["Name"]
    ]

    # 2. Fetch real iNAV from NSE (falls back to LTP proxy if NSE is unavailable)
    inav_from_nse = fetch_inav_from_nse()
    inav_source   = "NSE (real)" if inav_from_nse else "LTP proxy (−0.12%)"

    inav_list = []
    for name in working_df["Name"]:
        name_str = str(name).strip()
        if name_str in inav_from_nse:
            inav_list.append(round(inav_from_nse[name_str], 2))
        else:
            sym = TICKER_MAP.get(name_str)
            ltp = ltp_dict.get(sym) if sym else None
            inav_list.append(round(ltp * 0.9988, 2) if ltp else None)

    working_df["iNAV"] = inav_list

    # 3. P&L calculations
    if "Quantity" in working_df.columns and "Avg Price" in working_df.columns:
        working_df["Quantity"]      = pd.to_numeric(working_df["Quantity"],  errors="coerce")
        working_df["Avg Price"]     = pd.to_numeric(working_df["Avg Price"], errors="coerce")
        working_df["Investment"]    = working_df["Quantity"] * working_df["Avg Price"]
        working_df["Current Value"] = working_df["Quantity"] * working_df["Last Traded"]
        working_df["P&L"]           = working_df["Current Value"] - working_df["Investment"]
        working_df["P&L %"]         = (working_df["P&L"] / working_df["Investment"]) * 100

    # 4. Save to cache
    with _CACHE_LOCK:
        _PORTFOLIO_CACHE["enriched_df"]  = working_df
        _PORTFOLIO_CACHE["last_updated"] = datetime.datetime.now()
        _PORTFOLIO_CACHE["inav_source"]  = inav_source


# ── Public functions (called by app.py) ───────────────────────────────────────
def update_uploaded_portfolio(df: pd.DataFrame):
    global _PORTFOLIO_CACHE
    with _CACHE_LOCK:
        _PORTFOLIO_CACHE["raw_df"] = df
    try:
        process_data_snapshot()
    except Exception as e:
        print(f"Snapshot error on upload: {e}")


def _background_ticker_worker():
    while True:
        try:
            process_data_snapshot()
        except Exception as e:
            print(f"Background worker error: {e}")
        time.sleep(300)


def init_portfolio_pipeline():
    if not any(t.name == "PortfolioFetcher" for t in threading.enumerate()):
        t = threading.Thread(
            target=_background_ticker_worker,
            name="PortfolioFetcher",
            daemon=True
        )
        t.start()


def get_portfolio_metrics():
    with _CACHE_LOCK:
        return (
            _PORTFOLIO_CACHE["enriched_df"].copy(),
            _PORTFOLIO_CACHE["last_updated"],
            _PORTFOLIO_CACHE["inav_source"],
        )
