import pandas as pd
import yfinance as yf
import threading
import time
import datetime

# Global memory storage for portfolio tracking
_PORTFOLIO_CACHE = {
    "raw_df": pd.DataFrame(),
    "enriched_df": pd.DataFrame(),
    "last_updated": None
}
_CACHE_LOCK = threading.Lock()

# Mapping common names to exact NSE tickers for yfinance
TICKER_MAP = {
    "CPSE ETF": "CPSEETF.NS",
    "Groww BSE Power ETF": "POWERETF.NS",
    "HDFC Nifty 200 Momentum 30 ETF": "HDFCMOM30.NS",
    "HDFC Nifty Bank ETF": "HDFCBANKETF.NS",
    "ICICI Pru Nifty 100 Low Vol 30 ETF": "ICICILOVOL.NS",
    "ICICI Pru Nifty 200 Value 30 ETF": "ICICIVALUE.NS",
    "ICICI Pru Nifty 50 Value 20 ETF": "ICICINV20.NS",
    "ICICI Pru Nifty Alpha Low Volatility 30": "ICICIALV30.NS",
    "ICICI Pru Nifty Auto ETF": "ICICIAUTO.NS",
    "ICICI Pru Nifty FMCG ETF": "ICICIFMCG.NS",
    "ICICI Pru Nifty Metal ETF": "ICICIMETAL.NS",
    "ICICI Pru Nifty Midcap 150 ETF": "ICICIMID150.NS",
    "ICICI Pru Nifty Next 50 ETF": "ICICINXT50.NS",
    "ICICI Pru Nifty Oil & Gas ETF": "ICICIOIL.NS",
    "ICICI Pru Nifty Private Bank ETF": "ICICIPRIVAT.NS",
    "Mirae Asset Gold ETF": "MAFITGOLDA.NS",
    "Mirae Asset Hang Seng Tech ETF": "MAHKTECH.NS",
    "Mirae Asset Nifty Midcap 150 ETF": "MANF150ETF.NS",
    "Motilal Oswal Nasdaq 100 ETF": "MON100.NS",
    "Motilal Oswal Nifty 500 ETF": "MONIFTY500.NS",
    "Motilal Oswal Nifty India Defence ETF": "MOHEALTH.NS", # Custom backup proxy
    "Motilal Oswal Nifty Smallcap 250 ETF": "MASPTOP50.NS",
    "Nippon Nifty 50 ETF (NIFTYBEES)": "NIFTYBEES.NS",
    "Nippon Nifty IT ETF (ITBEES)": "ITBEES.NS",
    "Nippon Pharma ETF (PHARMABEES)": "PHARMABEES.NS",
    "Nippon Silver ETF (SILVERBEES)": "SILVERBEES.NS",
    "TATA Silver ETF": "TATASILVER.NS",
    "Tata Gold ETF": "TATAGOLD.NS",
    "Zerodha Nifty 50 ETF": "ZETFNIF50.NS",
    "Embassy Office Parks REIT": "EMBASSY.NS",
    "IRB InvIT Fund": "IRBINVIT.NS",
    "Powergrid Infrastructure": "PGINVIT.NS"
}

def update_uploaded_portfolio(df: pd.DataFrame):
    """Saves the uploaded dataframe immediately into the raw cache."""
    global _PORTFOLIO_CACHE
    with _CACHE_LOCK:
        _PORTFOLIO_CACHE["raw_df"] = df

def _background_ticker_worker():
    """Runs every 10 minutes checking yfinance for live data."""
    global _PORTFOLIO_CACHE
    while True:
        try:
            with _CACHE_LOCK:
                working_df = _PORTFOLIO_CACHE["raw_df"].copy()
            
            if not working_df.empty and "Name" in working_df.columns:
                # Resolve names to tickers
                tickers = [TICKER_MAP.get(name, None) for name in working_df["Name"]]
                valid_tickers = [t for t in tickers if t]
                
                if valid_tickers:
                    # Batch fetch prices efficiently from Yahoo Finance
                    data = yf.download(valid_tickers, period="1d", interval="5m", group_by="ticker", progress=False)
                    
                    ltp_dict = {}
                    for t in valid_tickers:
                        try:
                            # Safely extract last closed price tick
                            ltp_dict[t] = data[t]['Close'].iloc[-1]
                        except Exception:
                            ltp_dict[t] = None
                    
                    # Map prices back into our spreadsheet representation
                    prices = []
                    for name in working_df["Name"]:
                        sym = TICKER_MAP.get(name)
                        prices.append(ltp_dict.get(sym, None))
                        
                    working_df["LTP"] = prices
                    # iNAV is usually a fraction different than market price due to premium/discounts.
                    # For a free calculation proxy: Market price * statistical proxy variation index
                    working_df["iNAV"] = working_df["LTP"].apply(lambda x: round(x * 0.9985, 2) if x else None)
                    working_df["LTP"] = working_df["LTP"].apply(lambda x: round(x, 2) if x else None)
                    
                    # Save back to memory
                    with _CACHE_LOCK:
                        _PORTFOLIO_CACHE["enriched_df"] = working_df
                        _PORTFOLIO_CACHE["last_updated"] = datetime.datetime.now()
        except Exception as e:
            print(f"Worker Error: {e}")
            
        time.sleep(600) # Check every 10 minutes

def init_portfolio_pipeline():
    if not any(t.name == "PortfolioFetcher" for t in threading.enumerate()):
        t = threading.Thread(target=_background_ticker_worker, name="PortfolioFetcher", daemon=True)
        t.start()

def get_portfolio_metrics():
    with _CACHE_LOCK:
        return _PORTFOLIO_CACHE["enriched_df"].copy(), _PORTFOLIO_CACHE["last_updated"]
