import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import os

load_dotenv()

BASE_URL = os.getenv("BASE_API_URL")


class OpenF1Unavailable(Exception):
    """Raised when the local OpenF1 API has no data or is unreachable.
    Callers should catch this and use the FastF1 fallback instead."""
    pass


def fetch_data(endpoint, params=None):
    """
    Fetch data from the local OpenF1 query API and return it as a DataFrame.

    Raises:
        OpenF1Unavailable: on 5xx errors or connection failures.
    Returns:
        pd.DataFrame: empty DataFrame on 404 (session not yet available).
    """
    if params is None:
        params = {}

    url = f"{BASE_URL}{endpoint}"
    full_url = requests.Request("GET", url, params=params).prepare().url

    try:
        response = requests.get(full_url, timeout=15)
    except (requests.exceptions.ConnectionError, requests.exceptions.MissingSchema, requests.exceptions.InvalidURL):
        raise OpenF1Unavailable(f"Could not connect to local API — is BASE_API_URL configured?")

    # 404 = session exists in schedule but no data yet (future race)
    if response.status_code == 404:
        return pd.DataFrame()

    # 5xx = API or MongoDB not healthy
    if response.status_code >= 500:
        raise OpenF1Unavailable(f"Local API returned {response.status_code} for {endpoint}")

    response.raise_for_status()
    return pd.DataFrame(response.json())


# ── Cached API calls ──────────────────────────────────────────────────────────

import streamlit as st

@st.cache_data(ttl=300)
def fetch_all_meetings(year):
    """
    Fetch all meetings for a year from the local API.
    Raises OpenF1Unavailable if empty — triggers FastF1 fallback in main.py.
    TTL of 5 minutes so new ingestor data is picked up reasonably quickly.
    """
    df = fetch_data("meetings", {"year": year})
    if df.empty:
        raise OpenF1Unavailable(f"No meetings in local DB for {year}")
    return df


@st.cache_data(ttl=300)
def fetch_sessions(meeting_key):
    """
    Fetch sessions for a meeting from the local API.
    Raises OpenF1Unavailable if empty — triggers FastF1 fallback in main.py.
    """
    df = fetch_data("sessions", {"meeting_key": meeting_key})
    if df.empty:
        raise OpenF1Unavailable(f"No sessions in local DB for meeting {meeting_key}")
    df["label"] = df["session_name"] + " (" + df["date_start"] + ")"
    return df[["session_key", "label"]].drop_duplicates()


@st.cache_data(ttl=300)
def fetch_laps(session_key):
    return fetch_data("laps", {"session_key": session_key})


@st.cache_data(ttl=300)
def fetch_stints(session_key):
    return fetch_data("stints", {"session_key": session_key})


@st.cache_data(ttl=300)
def fetch_pit_stop(session_key):
    return fetch_data("pit", {"session_key": session_key})


@st.cache_data(ttl=300)
def fetch_drivers(session_key):
    return fetch_data("drivers", {"session_key": session_key})


# ── Live variants (TTL = 30s) ─────────────────────────────────────────────────

@st.cache_data(ttl=30)
def fetch_laps_live(session_key):
    return fetch_data("laps", {"session_key": session_key})


@st.cache_data(ttl=30)
def fetch_stints_live(session_key):
    return fetch_data("stints", {"session_key": session_key})


@st.cache_data(ttl=30)
def fetch_pit_stop_live(session_key):
    return fetch_data("pit", {"session_key": session_key})


@st.cache_data(ttl=30)
def fetch_drivers_live(session_key):
    return fetch_data("drivers", {"session_key": session_key})
