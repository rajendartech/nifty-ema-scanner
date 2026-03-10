import streamlit as st
import pandas as pd
import time
import json
import os
import plotly.graph_objects as go
import yfinance as yf
import requests
from datetime import datetime
import pytz

from scanner import scan_all, is_market_open
from symbols import NIFTY50, NIFTY100, NIFTY200, INDICES

# ─── Environment Setup ───────────────────────────────────────────────────────
_PLYER = False
_WINSOUND = False

try:
    from streamlit_autorefresh import st_autorefresh
    _AUTOREFRESH = True
except Exception:
    _AUTOREFRESH = False

# ─── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NIFTY EMA Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ── */
html, body, [class*="css"] {
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

/* ── Header gradient ── */
.main-header {
    background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
    padding: 1.2rem 1.5rem;
    border-radius: 12px;
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 12px;
}
.main-header h1 { color: #fff; margin: 0; font-size: 1.8rem; }
.main-header span { font-size: 2rem; }

/* ── Signal badge ── */
.badge-buy  { background:#00c853; color:#fff; padding:3px 10px; border-radius:20px; font-weight:700; font-size:.85rem; }
.badge-sell { background:#d50000; color:#fff; padding:3px 10px; border-radius:20px; font-weight:700; font-size:.85rem; }

/* ── Market status pill ── */
.market-open   { color:#00c853; font-weight:700; }
.market-closed { color:#ff5252; font-weight:700; }

/* ── Metric cards ── */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1a1a2e, #16213e);
    border-radius: 10px;
    padding: 10px;
    border: 1px solid #2e2e4d;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #0d1b2a !important;
}

/* ── DataFrame ── */
div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ─── Config ───────────────────────────────────────────────────────────────────
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "ema9": 9,
        "ema21": 21,
        "scan_interval": 5,
        "stocks_list": "NIFTY50",
        "custom_symbols": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "sound_alert": True,
        "desktop_alert": True,
    }

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass

config = load_config()

# ─── Auto-refresh ─────────────────────────────────────────────────────────────
if _AUTOREFRESH:
    st_autorefresh(interval=config["scan_interval"] * 60 * 1000, key="ema_autorefresh")

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Scanner Settings")
    config["ema9"]  = st.number_input("Fast EMA period", min_value=1, max_value=50,  value=int(config["ema9"]))
    config["ema21"] = st.number_input("Slow EMA period", min_value=2, max_value=200, value=int(config["ema21"]))
    config["scan_interval"] = st.number_input("Scan interval (min)", min_value=1, max_value=60, value=int(config["scan_interval"]))

    st.markdown("---")
    st.markdown("## 📊 Stock Universe")
    list_opts = ["Indices", "NIFTY50", "NIFTY100", "NIFTY200", "Custom"]
    if config["stocks_list"] not in list_opts:
        config["stocks_list"] = "Indices"
    config["stocks_list"] = st.selectbox("Stock list", list_opts, index=list_opts.index(config["stocks_list"]))
    if config["stocks_list"] == "Custom":
        config["custom_symbols"] = st.text_area(
            "Custom symbols (comma-separated, with .NS)",
            value=config.get("custom_symbols", ""),
            height=100,
        )

    st.markdown("---")
    st.markdown("## 🔔 Alerts")
    st.info("Desktop/Sound alerts are disabled on Cloud. Use Telegram below for mobile alerts.")
    config["sound_alert"]   = False
    config["desktop_alert"] = False

    st.markdown("---")
    st.markdown("## 📱 Telegram")
    config["telegram_bot_token"] = st.text_input("Bot token",  value=config.get("telegram_bot_token", ""), type="password")
    config["telegram_chat_id"]   = st.text_input("Chat ID",    value=config.get("telegram_chat_id", ""))

    st.markdown("---")
    st.caption("v2.0  •  NSE Data via yfinance")

save_config(config)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def send_telegram(token: str, chat_id: str, msg: str):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=6)
    except Exception as e:
        print(f"[Telegram] {e}")


def trigger_alert(symbol: str, sig_type: str, price: float):
    try:
        if _WINSOUND and config.get("sound_alert"):
            freq = 1200 if sig_type == "BUY" else 800
            winsound.Beep(freq, 500)
    except Exception:
        pass

    try:
        if _PLYER and config.get("desktop_alert"):
            plyer_notification.notify(
                title=f"{'🟢' if sig_type == 'BUY' else '🔴'} {sig_type} Signal — {symbol}",
                message=f"Price: ₹{price}",
                app_name="NIFTY EMA Scanner",
                timeout=6,
            )
    except Exception:
        pass

    token   = config.get("telegram_bot_token", "")
    chat_id = config.get("telegram_chat_id", "")
    if token and chat_id:
        emoji = "🟢" if sig_type == "BUY" else "🔴"
        msg   = f"{emoji} *{sig_type} Signal*\n*Symbol:* `{symbol}`\n*Price:* ₹{price}"
        send_telegram(token, chat_id, msg)


def get_symbols() -> list[str]:
    if config["stocks_list"] == "Indices":
        return INDICES
    if config["stocks_list"] == "NIFTY50":
        return NIFTY50
    if config["stocks_list"] == "NIFTY100":
        return NIFTY100
    if config["stocks_list"] == "NIFTY200":
        return NIFTY200
    return [s.strip() for s in config.get("custom_symbols", "").split(",") if s.strip()]


@st.cache_data(ttl=config["scan_interval"] * 60, show_spinner=False)
def get_scan_results() -> list[dict]:
    return scan_all(get_symbols(), config)


# ─── Session state ────────────────────────────────────────────────────────────
if "signals_history" not in st.session_state:
    st.session_state.signals_history: list[dict] = []
if "all_signals_log" not in st.session_state:
    st.session_state.all_signals_log: list[dict] = []

# ─── Header ───────────────────────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")
now_ist = datetime.now(IST)

market_open = is_market_open()
market_html = (
    '<span class="market-open">🟢 Market OPEN</span>'
    if market_open else
    '<span class="market-closed">🔴 Market CLOSED</span>'
)

st.markdown(f"""
<div class="main-header">
  <span>📈</span>
  <div>
    <h1>NIFTY EMA Scanner</h1>
    <div style="color:#ccc;font-size:.9rem;">{market_html} &nbsp;|&nbsp; {now_ist.strftime("%d %b %Y  %H:%M:%S IST")}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─── Top metrics row ──────────────────────────────────────────────────────────
universe = get_symbols()
m1, m2, m3, m4 = st.columns(4)
m1.metric("📋 Universe",    f"{len(universe)} stocks")
m2.metric("⚡ Fast EMA",    f"EMA {config['ema9']}")
m3.metric("📉 Slow EMA",    f"EMA {config['ema21']}")
m4.metric("🔄 Interval",    f"{config['scan_interval']} min")

st.divider()

# ─── Main layout ─────────────────────────────────────────────────────────────
tab_dashboard, tab_chart, tab_log = st.tabs(["🖥 Dashboard", "📊 Chart View", "📜 Signal Log"])

# ── Tab 1: Dashboard ─────────────────────────────────────────────────────────
with tab_dashboard:
    col_refresh, col_status = st.columns([1, 3])
    with col_refresh:
        force_refresh = st.button("🔄 Force Refresh", use_container_width=True)
        if force_refresh:
            st.cache_data.clear()

    with st.spinner(f"Scanning {config['stocks_list']} ({len(universe)} stocks)…"):
        results = get_scan_results()

    # Detect new signals and trigger alerts
    prev_keys = {f"{r['Stock Symbol']}|{r['Signal Time']}" for r in st.session_state.signals_history}
    new_signals = []
    for r in results:
        key = f"{r['Stock Symbol']}|{r['Signal Time']}"
        if key not in prev_keys:
            new_signals.append(r)
            trigger_alert(r["Stock Symbol"], r["Signal Type"], r["Current Price"])

    st.session_state.signals_history = results
    # Append new signals to permanent log
    st.session_state.all_signals_log = new_signals + st.session_state.all_signals_log

    if new_signals:
        st.success(f"🚨 {len(new_signals)} new signal(s) detected!")

    if results:
        buy_signals  = [r for r in results if r["Signal Type"] == "BUY"]
        sell_signals = [r for r in results if r["Signal Type"] == "SELL"]

        c1, c2 = st.columns(2)
        c1.metric("🟢 BUY Signals",  len(buy_signals))
        c2.metric("🔴 SELL Signals", len(sell_signals))

        df = pd.DataFrame(results)

        # Colour helper
        def _style_signal(val):
            if val == "BUY":
                return "color: #00c853; font-weight: 700"
            if val == "SELL":
                return "color: #ff5252; font-weight: 700"
            return ""

        styled = df.style.map(_style_signal, subset=["Signal Type"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Download
        csv = df.to_csv(index=False).encode()
        st.download_button("⬇️ Export CSV", csv, "ema_signals.csv", "text/csv", use_container_width=True)
    else:
        st.info(
            f"No stocks match the signal rules right now.\n\n"
            f"{'⚠️ Note: Market is currently closed.' if not market_open else ''}\n"
            f"Auto-scan runs every **{config['scan_interval']} minutes**."
        )

    st.caption(f"Last scan: {time.strftime('%Y-%m-%d %H:%M:%S')}")

# ── Tab 2: Chart View ─────────────────────────────────────────────────────────
with tab_chart:
    st.markdown("### 📊 Interactive Price Chart")
    
    col_sym, col_tf = st.columns([3, 1])
    with col_sym:
        search_symbol = st.text_input(
            "Symbol (with .NS suffix)",
            placeholder="e.g. RELIANCE.NS",
            label_visibility="collapsed",
        )
    with col_tf:
        timeframe = st.selectbox("Timeframe", ["5m", "15m", "1h", "1d"], index=0)

    period_map = {"5m": "5d", "15m": "10d", "1h": "1mo", "1d": "1y"}

    if search_symbol:
        with st.spinner(f"Loading {search_symbol}…"):
            try:
                import pandas_ta as pta
                ticker    = yf.Ticker(search_symbol)
                df_chart  = ticker.history(interval=timeframe, period=period_map[timeframe])

                if df_chart.empty:
                    st.warning("No data. Check symbol (e.g. INFY.NS)")
                else:
                    fast = int(config["ema9"])
                    slow = int(config["ema21"])
                    df_chart[f"EMA_{fast}"] = df_chart["Close"].ewm(span=fast, adjust=False).mean()
                    df_chart[f"EMA_{slow}"] = df_chart["Close"].ewm(span=slow, adjust=False).mean()

                    fig = go.Figure()
                    fig.add_trace(go.Candlestick(
                        x=df_chart.index,
                        open=df_chart["Open"], high=df_chart["High"],
                        low=df_chart["Low"],   close=df_chart["Close"],
                        name="Price",
                        increasing_line_color="#00c853",
                        decreasing_line_color="#ff5252",
                    ))
                    fig.add_trace(go.Scatter(
                        x=df_chart.index, y=df_chart[f"EMA_{fast}"],
                        name=f"EMA {fast}", line=dict(color="#2979ff", width=1.5)
                    ))
                    fig.add_trace(go.Scatter(
                        x=df_chart.index, y=df_chart[f"EMA_{slow}"],
                        name=f"EMA {slow}", line=dict(color="#ff9100", width=1.5)
                    ))

                    # Volume bar
                    fig.add_trace(go.Bar(
                        x=df_chart.index, y=df_chart["Volume"],
                        name="Volume", yaxis="y2",
                        marker_color="rgba(100,100,255,0.3)",
                    ))

                    fig.update_layout(
                        title=dict(text=f"{search_symbol}  •  {timeframe}", font=dict(size=16)),
                        xaxis_rangeslider_visible=False,
                        plot_bgcolor="#0d1b2a",
                        paper_bgcolor="#0d1b2a",
                        font=dict(color="#e0e0e0"),
                        legend=dict(bgcolor="rgba(0,0,0,0)"),
                        yaxis=dict(title="Price (₹)", gridcolor="#1e2d3d"),
                        yaxis2=dict(title="Volume", overlaying="y", side="right", showgrid=False),
                        xaxis=dict(gridcolor="#1e2d3d"),
                        margin=dict(l=0, r=0, t=40, b=0),
                        height=520,
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Quick stats
                    last_row  = df_chart.iloc[-1]
                    prev_row  = df_chart.iloc[-2]
                    chg       = round(last_row["Close"] - prev_row["Close"], 2)
                    chg_pct   = round(chg / prev_row["Close"] * 100, 2)
                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("Last Price",    f"₹{round(last_row['Close'], 2)}", delta=f"{chg} ({chg_pct}%)")
                    s2.metric("Open",          f"₹{round(last_row['Open'], 2)}")
                    s3.metric("High",          f"₹{round(last_row['High'], 2)}")
                    s4.metric("Volume",        f"{int(last_row['Volume']):,}")

            except Exception as e:
                st.error(f"Error loading chart: {e}")
    else:
        st.info("Enter a symbol above to view its chart with EMAs.")

# ── Tab 3: Signal Log ─────────────────────────────────────────────────────────
with tab_log:
    st.markdown("### 📜 Signal History  (this session)")

    if st.session_state.all_signals_log:
        log_df = pd.DataFrame(st.session_state.all_signals_log)

        def _style_log(val):
            if val == "BUY":  return "color:#00c853;font-weight:700"
            if val == "SELL": return "color:#ff5252;font-weight:700"
            return ""

        st.dataframe(
            log_df.style.map(_style_log, subset=["Signal Type"]),
            use_container_width=True, hide_index=True
        )
        csv_log = log_df.to_csv(index=False).encode()
        st.download_button("⬇️ Export Signal Log", csv_log, "signal_log.csv", "text/csv")

        if st.button("🗑 Clear Log"):
            st.session_state.all_signals_log = []
            st.rerun()
    else:
        st.info("No signals have been detected in this session yet.")
