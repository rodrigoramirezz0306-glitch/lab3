# Page 3: AI Market Analyst
# Web Dev Lab 4 - Processing Web API Data
# Nayan Bhogaraju
#
# This page takes stock data from the Massive API (same API as Lab 3) and
# feeds it into the Google Gemini LLM so it can write a market report about it.
# The user picks the stock, the time range, and the writing style, so both the
# data AND the report change based on what they choose.

import requests
import pandas as pd
import streamlit as st
from google import genai
from google.genai.errors import ClientError
from datetime import date, timedelta
import plotly.graph_objects as go


# ===== settings =====
BASE_URL = "https://api.massive.com"
MASSIVE_API_KEY = st.secrets["stockKey"]   # same key from page 1

# Gemini key (same one from page 2). Hardcoded so nothing shows up in the app.
GEMINI_API_KEY = "AQ.Ab8RN6JJyVKaJXyfibjk4Ew1bvslqk3HnViZAOJq4cKw2G1GyA"
GEMINI_MODEL = "gemini-3.5-flash"

POPULAR_TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META"]

# how many days back each option means
TIME_RANGES = {
    "1 Month": 30,
    "3 Months": 90,
    "6 Months": 180,
    "1 Year": 365,
}

# the different writing styles - the text is the instruction we give Gemini
STYLES = {
    "Professional analyst": "Write like a professional stock analyst. Keep it short and use finance words.",
    "Beginner friendly": "Explain it in simple terms for someone new to investing. No confusing jargon.",
    "Bullish (buy side)": "Be optimistic and make the case for why this stock looks good, but stay honest.",
    "Skeptical (bear case)": "Be cautious and point out the risks and weak spots in the numbers.",
}



# ===== get data from the Massive API =====

@st.cache_data(ttl=600, show_spinner=False)

def get_stock_data(ticker, days_back):
    
    # figure out the start and end dates
    end = date.today()
    start = end - timedelta(days=days_back)

    url = BASE_URL + "/v2/aggs/ticker/" + ticker.upper() + "/range/1/day/" + str(start) + "/" + str(end)
    params = {
        "adjusted": "true",
        "sort": "asc",
        "limit": 50000,
        "apiKey": MASSIVE_API_KEY,
    }

    response = requests.get(url, params=params)

    # if something went wrong just return None and handle it later
    if response.status_code != 200:
        return None

    data = response.json()
    if "results" not in data or len(data["results"]) == 0:
        return None

    # make a dataframe and rename the short column names Massive uses
    df = pd.DataFrame(data["results"])
    df = df.rename(columns={"t": "date", "o": "open", "h": "high",
                            "l": "low", "c": "close", "v": "volume"})
    df["date"] = pd.to_datetime(df["date"], unit="ms")
    return df


# ===== turn the price data into some basic stats =====
def get_stats(df):
    start_price = float(df["close"].iloc[0])
    end_price = float(df["close"].iloc[-1])
    total_return = (end_price - start_price) / start_price * 100

    # daily percent changes, used for volatility and up/down days
    daily_change = df["close"].pct_change().dropna()

    stats = {
        "start_price": round(start_price, 2),
        "end_price": round(end_price, 2),
        "total_return": round(total_return, 2),
        "high": round(float(df["high"].max()), 2),
        "low": round(float(df["low"].min()), 2),
        "avg_volume": int(df["volume"].mean()),
        "volatility": round(float(daily_change.std() * 100), 2),
        "up_days": int((daily_change > 0).sum()),
        "down_days": int((daily_change < 0).sum()),
        "days": len(df),
    }
    return stats


# make the stats into a text block to send to Gemini

def stats_to_text(ticker, s):
    
    text = "Ticker: " + ticker.upper() + "\n"
    text += "Trading days: " + str(s["days"]) + "\n"
    text += "Start price: $" + str(s["start_price"]) + "\n"
    text += "End price: $" + str(s["end_price"]) + "\n"
    text += "Total return: " + str(s["total_return"]) + "%\n"
    text += "High: $" + str(s["high"]) + "\n"
    text += "Low: $" + str(s["low"]) + "\n"
    text += "Average volume: " + str(s["avg_volume"]) + "\n"
    text += "Volatility: " + str(s["volatility"]) + "%\n"
    text += "Up days: " + str(s["up_days"]) + " / Down days: " + str(s["down_days"])
    
    return text


# ===== ask Gemini to write the report =====

@st.cache_data(ttl=600, show_spinner=False)

def make_report(data_text, style_instruction, length):
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = (
        style_instruction + "\n\n"
        "Using only the stock data below, write about " + str(length) + " words. "
        "Don't make up numbers that aren't given. Mention the real numbers where it helps.\n\n"
        "DATA:\n" + data_text
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt
    )
    return response.text

# build a nicer price chart for the report - green if the stock went up over
# the period, red if it went down, with a title and axis labels

def make_price_chart(df, ticker):
    
    went_up = df["close"].iloc[-1] >= df["close"].iloc[0]
    color = "#2ca02c" if went_up else "#d62728"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["close"],
        mode="lines",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor="rgba(44,160,44,0.1)" if went_up else "rgba(214,39,40,0.1)",
        name=ticker.upper(),
    ))
    fig.update_layout(
        title=ticker.upper() + " Closing Price",
        xaxis_title="Date",
        yaxis_title="Price ($)",
        template="plotly_dark",
        height=400,
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


# ===== the actual page =====
st.set_page_config(page_title="AI Market Analyst", page_icon="📈", layout="wide")

st.title("📈 AI Market Analyst")
st.write("This page pulls real stock data from the Massive API and uses Google Gemini "
         "to write a market report about it. Pick your options below.")

# --- controls in a bordered container with 2 columns (layout extra credit) ---

with st.container(border=True):
    st.subheader("1. Pick the stock data")
    col1, col2 = st.columns(2)

    with col1:
        
        picked = st.selectbox("Stock", POPULAR_TICKERS)
        typed = st.text_input("Or type any ticker")
        
        # if they typed something use that, otherwise use the dropdown
        
        if typed.strip() != "":
            ticker1 = typed.strip().upper()
        else:
            ticker1 = picked

    with col2:
        range_choice = st.selectbox("Time range", list(TIME_RANGES.keys()))
        days_back = TIME_RANGES[range_choice]

    # optional second stock to compare (pulls a 2nd set of API data)
    
    compare = st.checkbox("Compare with a second stock")
    ticker2 = None
    
    if compare:
        
        options2 = [t for t in POPULAR_TICKERS if t != ticker1]
        ticker2 = st.selectbox("Second stock", options2)

# --- second bordered container for the report options ---

with st.container(border=True):
    
    st.subheader("2. Pick the report style")
    col3, col4 = st.columns(2)
    
    with col3:
        style_choice = st.radio("Writing style", list(STYLES.keys()))
    with col4:
        length = st.select_slider("Length (words)", options=[100, 150, 200, 300], value=150)

run = st.button("Generate AI Report", type="primary", use_container_width=True)


# ===== when the button is pressed =====
if run:
    # get the first stock's data
    with st.spinner("Getting data from Massive..."):
        df1 = get_stock_data(ticker1, days_back)

    if df1 is None:
        st.error("Couldn't get data for " + ticker1 + ". Try a different ticker or a wider time range.")
        st.stop()

    stats1 = get_stats(df1)
    data_text = stats_to_text(ticker1, stats1)

    # get the second stock too if they wanted to compare
    df2 = None
    if compare and ticker2 is not None:
        with st.spinner("Getting data for " + ticker2 + "..."):
            df2 = get_stock_data(ticker2, days_back)
        if df2 is None:
            st.error("Couldn't get data for " + ticker2 + ".")
            st.stop()
        stats2 = get_stats(df2)
        data_text = data_text + "\n\n" + stats_to_text(ticker2, stats2)

    # quick stat cards using columns inside a container (layout extra credit)
    with st.container(border=True):
        title = ticker1
        if compare:
            title = ticker1 + " vs " + ticker2
        st.subheader("Snapshot: " + title)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("End Price", "$" + str(stats1["end_price"]))
        m2.metric("Total Return", str(stats1["total_return"]) + "%")
        m3.metric("High", "$" + str(stats1["high"]))
        m4.metric("Volatility", str(stats1["volatility"]) + "%")

    # send it to Gemini
    with st.spinner("Gemini is writing the report..."):
        
        try:
            report = make_report(data_text, STYLES[style_choice], length)
            
        except ClientError as e:
            
            # only 429 is a real rate limit; show the actual message otherwise
            
            if getattr(e, "code", None) == 429:
                
                report = "Sorry, you have reached the maximum of 15 calls per minute. Try again later."
                
            else:
                report = "Gemini error: " + str(e)
                
        except Exception as e:
            report = "Error: " + str(e)
            
    # show the results in tabs (layout extra credit)
    tab1, tab2, tab3 = st.tabs(["🧠 AI Report", "📊 Data", "ℹ️ How it works"])

    with tab1:
        
        # dollar signs get read as math by markdown, so escape them first
        st.markdown(report.replace("$", "\\$"))

    with tab2:
        
        if compare and df2 is not None:
            # two columns side by side, one chart each
            left, right = st.columns(2)
            with left:
                st.plotly_chart(make_price_chart(df1, ticker1), use_container_width=True)
            with right:
                st.plotly_chart(make_price_chart(df2, ticker2), use_container_width=True)
        else:
            st.plotly_chart(make_price_chart(df1, ticker1), use_container_width=True)

        # expander to hide the raw numbers we sent to Gemini
        with st.expander("See the exact data sent to Gemini"):
            st.code(data_text)

    with tab3:
        st.write("Step 1: your inputs decide which stock and how much history we ask the "
                 "Massive API for.")
        st.write("Step 2: we calculate stats from that data (return, high/low, volatility, etc).")
        st.write("Step 3: those numbers plus your writing style get sent to Google Gemini, "
                 "which writes the report.")
        st.write("Changing the stock, time range, or comparison stock changes the API data. "
                 "Changing the style or length changes how Gemini writes about it.")

else:
    st.info("Pick your options and click Generate AI Report to start.")
