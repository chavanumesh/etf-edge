import pandas as pd

def calculate_proxy_inav(df: pd.DataFrame) -> float:
    if df.empty or "underlying_price" not in df.columns:
        return 0.0
    df["weighted_val"] = df["underlying_price"] * df["weight"]
    proxy_inav = df["weighted_val"].sum()
    return round(proxy_inav, 2)
