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

_token_cache: dict = {
    "access_token": None,
    "expires_at": None,
}


class OpenF1Unavailable(Exception):
    """Raised when OpenF1's servers return a 5xx error.
    Callers should catch this and try the FastF1 fallback instead."""
    pass


def _get_access_token() -> str | None:
    """
    Return a valid OAuth2 bearer token, fetching or refreshing as needed.
    Returns None if no credentials are configured (unauthenticated mode).
    Tokens expire after 1 hour; we refresh 60s early to avoid edge cases.
    """
    if not OPENF1_USERNAME or not OPENF1_PASSWORD:
        return None

    now = datetime.now(timezone.utc)
    expires_at = _token_cache.get("expires_at")

    if _token_cache["access_token"] and expires_at and expires_at - now > timedelta(seconds=60):
        return _token_cache["access_token"]

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

    Raises:
        OpenF1Unavailable: when the API returns 502/503 (server overload/outage).
            Callers should catch this and use the FastF1 fallback.
    Returns:
        pd.DataFrame: empty DataFrame on 404 (session not yet available).
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

    # 404 = session exists in schedule but no data yet (future race)
    if response.status_code == 404:
        return pd.DataFrame()

    # 502/503 = OpenF1 servers down or overloaded — raise so callers can
    # fall back to FastF1. Don't return empty DF or st.cache_data will cache it.
    if response.status_code in (502, 503):
        raise OpenF1Unavailable(f"OpenF1 returned {response.status_code} for {endpoint}")

    response.raise_for_status()
    return pd.DataFrame(response.json())


# ── Cached API calls ──────────────────────────────────────────────────────────

@st.cache_data
def fetch_all_meetings(year):
    df = fetch_data("meetings", {"year": year})
    if df.empty:
        st.error("⚠️ No meeting data found.")
        return pd.DataFrame()
    return df


@st.cache_data
def fetch_sessions(meeting_key):
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
