import yfinance as yf
import pandas as pd
import concurrent.futures
from datetime import datetime, time as dt_time
import pytz

# ─── Market Hours (IST) ───────────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")
MARKET_OPEN  = dt_time(9, 15)
MARKET_CLOSE = dt_time(15, 30)


def is_market_open() -> bool:
    """Return True if the current IST time is within NSE trading hours."""
    now_ist = datetime.now(IST).time()
    return MARKET_OPEN <= now_ist <= MARKET_CLOSE


# ─── Data Fetching ────────────────────────────────────────────────────────────

def fetch_data(symbol: str, interval: str = "5m", period: str = "5d") -> pd.DataFrame:
    """Fetch intraday OHLCV data."""
    try:
        df = yf.Ticker(symbol).history(interval=interval, period=period)
        return df
    except Exception as e:
        print(f"[fetch_data] {symbol}: {e}")
        return pd.DataFrame()


def fetch_daily_data(symbol: str, period: str = "3mo") -> pd.DataFrame:
    """Fetch daily OHLCV data for trend confirmation."""
    try:
        df = yf.Ticker(symbol).history(interval="1d", period=period)
        return df
    except Exception as e:
        print(f"[fetch_daily] {symbol}: {e}")
        return pd.DataFrame()


# ─── Indicator Calculation ────────────────────────────────────────────────────

def apply_indicators(df: pd.DataFrame, ema_fast: int, ema_slow: int) -> pd.DataFrame:
    """Add EMA columns using native pandas."""
    if len(df) < ema_slow + 5:
        return df
    df[f"EMA_{ema_fast}"] = df["Close"].ewm(span=ema_fast, adjust=False).mean()
    df[f"EMA_{ema_slow}"] = df["Close"].ewm(span=ema_slow, adjust=False).mean()
    return df


def apply_daily_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add daily SMA indicators using native pandas."""
    if len(df) >= 50:
        df["SMA_50"] = df["Close"].rolling(window=50).mean()
    if len(df) >= 100:
        df["SMA_100"] = df["Close"].rolling(window=100).mean()
    if len(df) >= 200:
        df["SMA_200"] = df["Close"].rolling(window=200).mean()
    return df


# ─── Signal Logic ─────────────────────────────────────────────────────────────

def _crossover_up(prev_fast, prev_slow, cur_fast, cur_slow) -> bool:
    """Fast EMA crossed above slow EMA."""
    return (prev_fast <= prev_slow) and (cur_fast > cur_slow)


def _crossover_down(prev_fast, prev_slow, cur_fast, cur_slow) -> bool:
    """Fast EMA crossed below slow EMA."""
    return (prev_fast >= prev_slow) and (cur_fast < cur_slow)


def analyze_stock(symbol: str, config: dict) -> dict | None:
    """
    Analyze a single stock.

    BUY  → 5m EMA fast crosses above slow  +  daily price > SMA50  +  today's
            price closed above previous day's high.
    SELL → 5m EMA fast crosses below slow  +  daily price < SMA50.

    Returns a result dict or None.
    """
    try:
        ema_fast = int(config.get("ema9", 9))
        ema_slow = int(config.get("ema21", 21))

        # ── Intraday data ────────────────────────────────────────────────────
        df_5m = fetch_data(symbol, interval="5m", period="5d")
        if df_5m.empty or len(df_5m) < max(ema_fast, ema_slow) + 5:
            return None

        df_5m = apply_indicators(df_5m, ema_fast, ema_slow)

        fast_col = f"EMA_{ema_fast}"
        slow_col = f"EMA_{ema_slow}"

        # ── Check last 3 candles for a signal ───────────────────────────────
        # This ensures signals stay on the dashboard for at least 15 mins
        lookback = 3
        best_res = None
        
        for i in range(1, lookback + 1):
            idx = -i
            prev_idx = -i - 1
            
            last = df_5m.iloc[idx]
            prev = df_5m.iloc[prev_idx]
            
            cross_up   = _crossover_up(prev[fast_col], prev[slow_col], last[fast_col], last[slow_col])
            cross_down = _crossover_down(prev[fast_col], prev[slow_col], last[fast_col], last[slow_col])
            
            if not (cross_up or cross_down):
                continue

            # ── Daily data (only fetch once if needed) ───────────────────────
            df_1d = fetch_daily_data(symbol, period="1y")
            if df_1d.empty or len(df_1d) < 2:
                return None

            df_1d = apply_daily_indicators(df_1d)
            d_last = df_1d.iloc[-1]
            d_prev = df_1d.iloc[-2]

            above_sma50  = ("SMA_50"  in d_last and not pd.isna(d_last["SMA_50"])  and d_last["Close"] > d_last["SMA_50"])
            below_sma50  = ("SMA_50"  in d_last and not pd.isna(d_last["SMA_50"])  and d_last["Close"] < d_last["SMA_50"])
            above_prev_high = d_last["Close"] > d_prev["High"]

            current_price = round(float(last["Close"]), 2)
            ema_fast_val  = round(float(last[fast_col]), 2)
            ema_slow_val  = round(float(last[slow_col]), 2)
            volume        = int(last["Volume"])
            signal_time   = last.name.strftime("%H:%M") # Format for dashboard

            sl_pct = 0.5 / 100
            signal = None
            
            if cross_up and above_sma50 and above_prev_high:
                signal = "BUY"
                stop_loss = round(current_price * (1 - sl_pct), 2)
                target    = round(current_price + 2 * (current_price - stop_loss), 2)
            elif cross_down and below_sma50:
                signal = "SELL"
                stop_loss = round(current_price * (1 + sl_pct), 2)
                target    = round(current_price - 2 * (stop_loss - current_price), 2)

            if signal:
                best_res = {
                    "Stock Symbol": symbol,
                    "Signal Type":  signal,
                    "Signal Time":  signal_time,
                    "Current Price": current_price,
                    f"EMA{ema_fast}": ema_fast_val,
                    f"EMA{ema_slow}": ema_slow_val,
                    "Stop Loss":    stop_loss,
                    "Target":       target,
                    "Volume":       volume,
                }
                break # Found latest signal

        return best_res

    except Exception as e:
        print(f"[analyze] {symbol}: {e}")
        return None


# ─── Batch Scanning ───────────────────────────────────────────────────────────

def scan_all(symbols: list[str], config: dict, max_workers: int = 12) -> list[dict]:
    """Scan all symbols concurrently and return a list of signal dicts."""
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        future_map = {pool.submit(analyze_stock, sym, config): sym for sym in symbols}
        for future in concurrent.futures.as_completed(future_map):
            try:
                res = future.result()
                if res:
                    results.append(res)
            except Exception as e:
                print(f"[scan_all] {future_map[future]}: {e}")
    # Sort: BUY first, then SELL; then by time descending
    results.sort(key=lambda r: (r["Signal Type"] != "BUY", r["Signal Time"]), reverse=False)
    return results
