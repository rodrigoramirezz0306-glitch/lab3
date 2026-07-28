"""
Page 1: Stock Market Explorer
CS 1301 - Web Development Lab 03
Nayan Bhogaraju

Fetches historical stock market data from the Massive.com REST API
(https://massive.com/docs) and lets the user analyze and visualize it
interactively.
"""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st


# Constants

BASE_URL = "https://api.massive.com"

# Default Massive API key so the app runs out of the box.

DEFAULT_API_KEY = st.secrets["stockKey"]

# Preset look-back windows -> number of calendar days back from today.

LOOKBACK_OPTIONS = {
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
    "2 Years": 730,
    "5 Years": 1825,
}

# A few well-known tickers so the app is easy to demo / grade.

POPULAR_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]



# Data access


@st.cache_data(ttl=600, show_spinner=False)

def fetch_aggregates(api_key, ticker, multiplier, timespan, from_date, to_date):
    """Call the Massive 'Custom Bars (OHLC)' endpoint and return the raw JSON.

    Endpoint:
        GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}

    Returns a tuple (data_dict, error_message). Exactly one of them is set.
    """
    url = (
        f"{BASE_URL}/v2/aggs/ticker/{ticker.upper()}/range/"
        f"{multiplier}/{timespan}/{from_date}/{to_date}"
    )
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000,
        "apiKey": api_key,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
    except requests.exceptions.RequestException as exc:
        return None, f"Network error while contacting Massive: {exc}"

    if resp.status_code == 401:
        return None, "Unauthorized (401). Double-check your Massive API key."
    if resp.status_code == 403:
        return None, "Forbidden (403). Your plan may not include this data."
    if resp.status_code == 429:
        return None, "Rate limited (429). Wait a moment and try again."
    if resp.status_code != 200:
        return None, f"Massive returned HTTP {resp.status_code}: {resp.text[:200]}"

    return resp.json(), None


def aggregates_to_dataframe(data):
    """Turn the Massive JSON payload into a tidy pandas DataFrame."""
    results = data.get("results") or []
    if not results:
        return pd.DataFrame()

    df = pd.DataFrame(results)
    # Massive returns short OHLCV keys; rename them to something readable.
    df = df.rename(
        columns={
            "t": "timestamp",
            "o": "Open",
            "h": "High",
            "l": "Low",
            "c": "Close",
            "v": "Volume",
            "vw": "VWAP",
            "n": "Transactions",
        }
    )
    df["Date"] = pd.to_datetime(df["timestamp"], unit="ms")
    df = df.sort_values("Date").reset_index(drop=True)
    return df



# Page config + intro

st.set_page_config(page_title="Stock Market Explorer", page_icon="📈", layout="wide")

st.title("📈 Stock Market Explorer")
st.write(
    "Explore historical U.S. stock prices using the "
    "[Massive.com](https://massive.com/docs) financial market data API. "
    "Pick a ticker, choose a time range, and analyze the price action with "
    "interactive charts, moving averages, and daily returns."
)


# Sidebar controls (user inputs that change the app's behavior)

with st.sidebar:
    st.header("⚙️ Controls")

    # API key comes from secrets if available, otherwise the built-in key.
    try:
        api_key = st.secrets.get("MASSIVE_API_KEY", DEFAULT_API_KEY)
        
    except Exception:
        api_key = DEFAULT_API_KEY


    st.divider()

    # Input #1: which stock to look at.
    ticker = st.selectbox("Ticker symbol", POPULAR_TICKERS, index=0)
    custom = st.text_input("...or type your own", value="").strip().upper()
    if custom:
        ticker = custom

    # Input #2: how far back to pull data.
    lookback_label = st.selectbox(
        "Time range", list(LOOKBACK_OPTIONS.keys()), index=2
    )
    lookback_days = LOOKBACK_OPTIONS[lookback_label]

    # Input #3: candle size.
    timespan = st.selectbox(
        "Bar size", ["day", "week", "month", "hour"], index=0
    )

    # Input #4: how to draw the price chart.
    chart_type = st.radio("Price chart style", ["Candlestick", "Line"], index=0)

    # Input #5: moving-average overlay.
    show_sma = st.checkbox("Show moving average", value=True)
    sma_window = st.slider(
        "Moving-average window (bars)", 2, 100, 20, disabled=not show_sma
    )

    # Input #6: second stock to compare against.
    compare_options = ["None"] + [t for t in POPULAR_TICKERS if t != ticker]
    
    compare_choice = st.selectbox(
        "Compare with another stock",
        compare_options,
        index=0,
        help="Pick a second stock to overlay its performance against the one above.",
    )
    compare_ticker = "" if compare_choice == "None" else compare_choice

# Guard: need an API key before we can do anything

if not api_key:
    st.info(
        "👈 Enter your Massive API key in the sidebar to load data. "
        "You can create a free key at "
        "[massive.com/dashboard/keys](https://massive.com/dashboard/keys)."
    )
    st.stop()


# Fetch the primary ticker

to_date = date.today()
from_date = to_date - timedelta(days=lookback_days)

with st.spinner(f"Fetching {ticker} data from Massive..."):
    data, error = fetch_aggregates(
        api_key, ticker, 1, timespan, from_date.isoformat(), to_date.isoformat()
    )

if error:
    st.error(error)
    st.stop()

df = aggregates_to_dataframe(data)

if df.empty:
    st.warning(
        f"No data returned for **{ticker}** over the selected range. "
        "Try a different ticker or a longer time range. "
        "(Free plans are often limited to end-of-day data and ~2 years of history.)"
    )
    st.stop()


# Key metrics (update whenever inputs change)

latest = df.iloc[-1]
first = df.iloc[0]
price_change = latest["Close"] - first["Close"]
pct_change = (price_change / first["Close"]) * 100 if first["Close"] else 0

st.subheader(f"{ticker} — {lookback_label}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest close", f"${latest['Close']:,.2f}",
          f"{pct_change:+.2f}% over range")

c2.metric("Period high", f"${df['High'].max():,.2f}")
c3.metric("Period low", f"${df['Low'].min():,.2f}")
c4.metric("Avg daily volume", f"{df['Volume'].mean():,.0f}")


# VISUAL #1: interactive price chart (dynamic + interactive)

price_fig = go.Figure()

if chart_type == "Candlestick":
    price_fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name=ticker,
        )
    )
else:
    price_fig.add_trace(
        go.Scatter(
            x=df["Date"], y=df["Close"], mode="lines",
            name=f"{ticker} Close", line=dict(width=2),
        )
    )

if show_sma and len(df) >= sma_window:
    df["SMA"] = df["Close"].rolling(window=sma_window).mean()
    price_fig.add_trace(
        go.Scatter(
            x=df["Date"], y=df["SMA"], mode="lines",
            name=f"{sma_window}-bar SMA",
            line=dict(width=1.5, dash="dot"),
        )
    )

price_fig.update_layout(
    title=f"{ticker} price ({timespan} bars)",
    xaxis_title="Date",
    yaxis_title="Price (USD)",
    xaxis_rangeslider_visible=False,
    height=500,
    hovermode="x unified",
    showlegend = True,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(price_fig, use_container_width=True)


# VISUAL #2: volume bar chart (dynamic)

vol_fig = go.Figure(
    go.Bar(x=df["Date"], y=df["Volume"], name="Volume",
           marker=dict(color="#7c9cff"))
)
vol_fig.update_layout(
    title=f"{ticker} trading volume",
    xaxis_title="Date",
    yaxis_title="Shares traded",
    height=280,
)
st.plotly_chart(vol_fig, use_container_width=True)


# VISUAL #3: daily returns (dynamic) — green/red bars per period

df["Return %"] = df["Close"].pct_change() * 100
returns = df.dropna(subset=["Return %"])
ret_fig = go.Figure(
    go.Bar(
        x=returns["Date"],
        y=returns["Return %"],
        marker=dict(
            color=["#2ecc71" if r >= 0 else "#e74c3c" for r in returns["Return %"]]
        ),
        name="Return %",
    )
)
ret_fig.update_layout(
    title=f"{ticker} period-over-period returns (%)",
    xaxis_title="Date",
    yaxis_title="Return (%)",
    height=280,
)
st.plotly_chart(ret_fig, use_container_width=True)


# Optional comparison overlay (normalized performance)

if compare_ticker and compare_ticker != ticker:
    with st.spinner(f"Fetching {compare_ticker} for comparison..."):
        cmp_data, cmp_error = fetch_aggregates(
            api_key, compare_ticker, 1, timespan,
            from_date.isoformat(), to_date.isoformat(),
        )

    st.subheader(f"Normalized performance: {ticker} vs {compare_ticker}")
    if cmp_error:
        st.warning(f"Couldn't load {compare_ticker}: {cmp_error}")
    else:
        cmp_df = aggregates_to_dataframe(cmp_data)
        if cmp_df.empty:
            st.warning(f"No data returned for {compare_ticker}.")
        else:
            # Normalize both series to 100 at the start so % moves are comparable.
            base_a = df["Close"].iloc[0]
            base_b = cmp_df["Close"].iloc[0]
            comp_fig = go.Figure()
            comp_fig.add_trace(go.Scatter(
                x=df["Date"], y=df["Close"] / base_a * 100,
                mode="lines", name=ticker))
            comp_fig.add_trace(go.Scatter(
                x=cmp_df["Date"], y=cmp_df["Close"] / base_b * 100,
                mode="lines", name=compare_ticker))
            comp_fig.update_layout(
                yaxis_title="Growth of $100",
                xaxis_title="Date",
                height=400,
                hovermode="x unified",
            )
            st.plotly_chart(comp_fig, use_container_width=True)

# Raw data

with st.expander("🔎 View raw data table"):
    display_cols = ["Date", "Open", "High", "Low", "Close", "Volume", "VWAP"]
    display_cols = [c for c in display_cols if c in df.columns]
    st.dataframe(df[display_cols], use_container_width=True)
    csv = df[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download as CSV", csv, file_name=f"{ticker}_{lookback_label}.csv",
        mime="text/csv",
    )

st.caption("Data provided by Massive.com. For educational use — not financial advice.")
 
