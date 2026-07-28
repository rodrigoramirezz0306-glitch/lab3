from google import genai
import streamlit as st
from google.genai.errors import ClientError
from datetime import date, timedelta
import pandas as pd
import requests




#SECTION 1- Getting Stock API data


st.title("Stock Chat Bot")

# API url
BASE_URL = "https://api.massive.com"

# API Key
DEFAULT_API_KEY = "lqxOOJppGZJtPmRKJBF7awXkJp5RVuzv"

# Data access 
@st.cache_data(ttl=600, show_spinner=False)
def fetch_aggregates(api_key, ticker, multiplier, timespan, from_date, to_date):
    """Call the Massive 'Custom Bars (OHLC)' endpoint and return the raw JSON."""
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


# !!!!!!!!!SESSION STATE SECTION (ISOLATED TO THIS PAGE)!!!!!!!!!#

if 'context_chat_history' not in st.session_state:
    st.session_state.context_chat_history = []

# Allows us to keep a visual convo history safely isolated
for message in st.session_state.context_chat_history:


    #isinstance (identifies data type and excutes accordingly) was used
    #to prevent errors data types.


    
    if isinstance(message, dict):
        role = message.get("role", "user")
        content = message.get("content", "")
        with st.chat_message(role):
            st.write(content)
    else:
        with st.chat_message("user"):
            st.write(message)







#SECTION 2- COMBINING CHAT BOT WITH DATA





            

# Gemini API key string goes here
key = "keyContext"

# Initialize client.
client = genai.Client(api_key=key)

selectedTicket = st.selectbox("Choose a stock to analyse:", ["AAPL", "MSFT", "GOOGL", "TSLA"])

# FETCHING specific API ticket info 
rawData, errorMsg = fetch_aggregates(
    api_key=DEFAULT_API_KEY,
    ticker=selectedTicket,
    multiplier=1,
    timespan='day',
    from_date='2026-01-01',
    to_date='2026-01-31',
)

if errorMsg:
    st.error(errorMsg)
    st.stop()

df = aggregates_to_dataframe(rawData)
st.subheader(f'Recent Data for {selectedTicket}')
st.dataframe(df)

chat_prompt = st.chat_input(f"Ask me about {selectedTicket} stock!")

if chat_prompt:
    st.session_state.context_chat_history.append({"role": "user", "content": chat_prompt})
    with st.chat_message("user"):
        st.write(chat_prompt)

    compact_data_str = df.to_string(index=False)

    context_prompt = f"""
You are designed to help the user to answer their question using specific data.
Here is the data summary for {selectedTicket}:
{compact_data_str}

Answer the user question based only on this specific data:
{chat_prompt}
"""
    try:
        
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=context_prompt
        )
        st.session_state.context_chat_history.append(
            {"role": "assistant", "content": response.text}
        )
        with st.chat_message("assistant"):
            st.write(response.text)

    except ClientError:
        response1 = "Sorry, you have reached the maximum of 15 calls per minute. Try again later."
        st.session_state.context_chat_history.append(
            {"role": "assistant", "content": response1}
        )
        with st.chat_message("assistant"):
            st.write(response1)

    except Exception:
        response2 = "Sorry, I am unable to answer your question. Care to try another one?"
        st.session_state.context_chat_history.append(
            {"role": "assistant", "content": response2}
        )
        with st.chat_message("assistant"):
            st.write(response2)








#CONCEPT CHECKS

# Session States (st.session_states): this functions helps store user input,
#that way it does not get lost when the page reruns.

#Connecting to External APIs & LLMs: to connect the chat box and to the API the
#usage of a client was used. A client carries the requests to the destination
#establishing a link where data is obtained and returned for usage.


