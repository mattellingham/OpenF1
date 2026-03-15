import streamlit as st
import requests
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import os

load_dotenv()

BASE_URL = os.getenv("BASE_API_URL")
OPENF1_USERNAME = os.getenv("OPENF1_USERNAME")
OPENF1_PASSWORD = os.getenv("OPENF1_PASSWORD")
TOKEN_URL = "https://api.openf1.org/token"

# Module-level token cache — persists for the life of the process.
# Streamlit re-runs the script on each interaction but doesn't restart the
# process, so this survives across page interactions without hitting the
# token endpoint every time.
_token_cache: dict = {
    "access_token": None,
    "expires_at": None,   # datetime (UTC)
}


def _get_access_token() -> str | None:
    """
    Return a valid OAuth2 bearer token, fetching or refreshing as needed.
    Returns None if no credentials are configured (unauthenticated mode).
    Tokens expire after 1 hour; we refresh 60s early to avoid edge cases.
    """
    if not OPENF1_USERNAME or not OPENF1_PASSWORD:
        return None  # Unauthenticated — fine for historical data

    now = datetime.now(timezone.utc)
    expires_at = _token_cache.get("expires_at")

    # Return cached token if still valid with >60s remaining
    if _token_cache["access_token"] and expires_at and expires_at - now > timedelta(seconds=60):
        return _token_cache["access_token"]

    # Fetch a new token
    try:
        response = requests.post(
            TOKEN_URL,
            data={"username": OPENF1_USERNAME, "password": OPENF1_PASSWORD},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        expires_in = int(token_data.get("expires_in", 3600))

        _token_cache["access_token"] = access_token
        _token_cache["expires_at"] = now + timedelta(seconds=expires_in)
        return access_token

    except Exception as e:
        st.warning(f"⚠️ Could not authenticate with OpenF1: {e}. Falling back to unauthenticated access.")
        return None


def fetch_data(endpoint, params=None):
    """
    Fetch data from the OpenF1 API and return it as a DataFrame.

    Automatically attaches a Bearer token if credentials are configured in .env.
    Falls back to unauthenticated requests if no credentials are set.

    Args:
        endpoint (str): API endpoint (e.g., "meetings", "sessions").
        params (dict): Optional query parameters for the API.

    Returns:
        pd.DataFrame: DataFrame containing the API response data.
    """
    if params is None:
        params = {}

    url = f"{BASE_URL}{endpoint}"
    full_url = requests.Request("GET", url, params=params).prepare().url

    headers = {"accept": "application/json"}
    token = _get_access_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(full_url, headers=headers, timeout=15)

    # 404 means the session exists in the schedule but has no data yet
    # (e.g. a future race). Return empty DataFrame instead of crashing.
    if response.status_code == 404:
        return pd.DataFrame()

    response.raise_for_status()
    return pd.DataFrame(response.json())

# ── Cached API calls ──────────────────────────────────────────────────────────

@st.cache_data
def fetch_all_meetings(year):
    """
    Fetch all meetings (races) for a given year.
    Cached indefinitely — the calendar for a completed year won't change.
    """
    df = fetch_data("meetings", {"year": year})
    if df.empty:
        st.error("⚠️ No meeting data found.")
        return pd.DataFrame()
    return df


@st.cache_data
def fetch_sessions(meeting_key):
    """All sessions for a given meeting (FP1, Quali, Race etc.)."""
    df = fetch_data("sessions", {"meeting_key": meeting_key})
    df["label"] = df["session_name"] + " (" + df["date_start"] + ")"
    return df[["session_key", "label"]].drop_duplicates()


@st.cache_data
def fetch_laps(session_key):
    return fetch_data("laps", {"session_key": session_key})


@st.cache_data
def fetch_stints(session_key):
    return fetch_data("stints", {"session_key": session_key})


@st.cache_data
def fetch_pit_stop(session_key):
    return fetch_data("pit", {"session_key": session_key})


@st.cache_data
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
