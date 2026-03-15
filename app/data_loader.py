import streamlit as st
import requests
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

BASE_URL = os.getenv("BASE_API_URL")


def fetch_data(endpoint, params=None):
    """
    Fetch data from the OpenF1 API and return it as a DataFrame.

    Args:
        endpoint (str): API endpoint (e.g., "meetings", "sessions").
        params (dict): Optional query parameters for the API.

    Returns:
        pd.DataFrame: DataFrame containing the API response data.

    Notes:
        The OpenF1 API requires properly URL-encoded query strings,
        especially when using complex filters (e.g., strings with spaces).
        Using `requests.get(url, params=params)` sometimes causes issues with
        formatting, so we manually prepare the full URL using `requests.Request`.
    """
    if params is None:
        params = {}

    url = f"{BASE_URL}{endpoint}"
    full_url = requests.Request('GET', url, params=params).prepare().url
    response = requests.get(full_url, timeout=15)
    response.raise_for_status()
    return pd.DataFrame(response.json())


# Cached API calls using Streamlit's cache_data decorator

@st.cache_data
def fetch_all_meetings(year):
    """
    Fetch all meetings (races) for a given year.
    Cached so the API is not called again on every widget interaction.
    """
    df = fetch_data("meetings", {"year": year})
    if df.empty:
        st.error("⚠️ No meeting data found.")
        return pd.DataFrame()
    return df


@st.cache_data
def fetch_sessions(meeting_key):
    # The 'sessions' endpoint returns all session types (FP1, Qualifying, Race) for a specific Grand Prix.
    # Filtered here using 'meeting_key' from the 'meetings' endpoint.
    df = fetch_data("sessions", {"meeting_key": meeting_key})

    # Combine session name and start date for display
    df["label"] = df["session_name"] + " (" + df["date_start"] + ")"

    # Only keep necessary columns for dropdowns
    return df[["session_key", "label"]].drop_duplicates()


@st.cache_data
def fetch_laps(session_key):
    # Retrieves detailed lap timing data for a given session
    return fetch_data("laps", {"session_key": session_key})


@st.cache_data
def fetch_stints(session_key):
    # Fetches tire stint data, which includes tire compound and start/end laps
    return fetch_data("stints", {"session_key": session_key})


@st.cache_data
def fetch_pit_stop(session_key):
    # Returns pit stop information, including duration and lap number
    return fetch_data("pit", {"session_key": session_key})


@st.cache_data
def fetch_drivers(session_key):
    # Provides driver metadata such as name, number, and team color
    return fetch_data("drivers", {"session_key": session_key})
