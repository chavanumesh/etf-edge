import pandas as pd
import threading
import time
import datetime

_DATA_CACHE = {"df": pd.DataFrame(), "last_updated": None}
_CACHE_LOCK = threading.Lock()

def get_free_google_sheet_data():
    now = datetime.datetime.now()
    mock_data = {
        "ticker": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"],
        "weight": [0.12, 0.10, 0.09, 0.07],
        "underlying_price": [2450.0 + (now.second * 0.1), 3200.0, 1600.0, 1450.0]
    }
    return pd.DataFrame(mock_data)

def _background_worker(interval_seconds=600):
    global _DATA_CACHE
    while True:
        try:
            fresh_df = get_free_google_sheet_data()
            with _CACHE_LOCK:
                _DATA_CACHE["df"] = fresh_df
                _DATA_CACHE["last_updated"] = datetime.datetime.now()
        except Exception as e:
            print(f"Error fetching background data: {e}")
        time.sleep(interval_seconds)

def initialize_data_pipeline():
    if not any(t.name == "DataFetcher" for t in threading.enumerate()):
        worker_thread = threading.Thread(
            target=_background_worker, 
            args=(600,), 
            name="DataFetcher", 
            daemon=True
        )
        worker_thread.start()

def get_latest_metrics():
    with _CACHE_LOCK:
        return _DATA_CACHE["df"].copy(), _DATA_CACHE["last_updated"]
