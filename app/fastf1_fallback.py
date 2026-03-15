"""
FastF1 fallback data source.

Used when OpenF1's API is unavailable (502/503). Provides both the top-level
calendar/session listings (so dropdowns still populate) and the session data
itself (laps, stints, pit stops, drivers).

FastF1 maintains its own disk cache (~/.fastf1_cache), so the first load
of a session downloads ~50-200 MB; subsequent calls return in seconds.
"""

import os
import fastf1
import pandas as pd
import streamlit as st

CACHE_DIR = os.path.expanduser("~/.fastf1_cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# Map OpenF1 session names to FastF1 session identifiers
SESSION_NAME_MAP = {
    "Race": "R",
    "Qualifying": "Q",
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Sprint": "S",
    "Sprint Qualifying": "SQ",
    "Sprint Shootout": "SQ",
}


# ── Calendar/schedule ─────────────────────────────────────────────────────────

@st.cache_data(show_spinner="OpenF1 unavailable — loading calendar from FastF1...")
def get_meetings_fastf1(year: int) -> pd.DataFrame:
    """
    Returns a meetings DataFrame with columns matching what main.py expects
    from OpenF1's /meetings endpoint:
      meeting_key, country_name, meeting_name, location

    meeting_key is synthesised from FastF1's RoundNumber so the rest of
    the app can treat it like a real key.
    """
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        df = schedule[["RoundNumber", "Country", "EventName", "Location"]].copy()
        df = df.rename(columns={
            "RoundNumber": "meeting_key",
            "Country": "country_name",
            "EventName": "meeting_name",
            "Location": "location",
        })
        return df
    except Exception as e:
        st.warning(f"FastF1 fallback could not load calendar: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner="OpenF1 unavailable — loading sessions from FastF1...")
def get_sessions_fastf1(year: int, country: str) -> pd.DataFrame:
    """
    Returns a sessions DataFrame with columns matching what main.py expects
    from OpenF1's /sessions endpoint:
      session_key, label, session_name, date_start

    session_key is the human-readable session name (e.g. "Race", "Qualifying")
    rather than an integer. main.py stores this in session_state so the
    chart render functions can pass it to FastF1 directly.
    """
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        event = schedule[schedule["Country"] == country]
        if event.empty:
            # Try partial match in case FastF1 uses a slightly different country name
            event = schedule[schedule["Country"].str.contains(country, case=False, na=False)]
        if event.empty:
            st.warning(f"FastF1 could not find {country} in the {year} calendar.")
            return pd.DataFrame()

        event = event.iloc[0]
        rows = []
        for i in range(1, 6):
            name = event.get(f"Session{i}")
            date = event.get(f"Session{i}DateUtc")
            if pd.isna(name) or not name or name == "None":
                continue
            date_str = str(date)[:16].replace("T", " ") if pd.notna(date) else "TBC"
            rows.append({
                "session_key": name,          # e.g. "Race", "Qualifying"
                "session_name": name,
                "label": f"{name} ({date_str})",
                "date_start": str(date) if pd.notna(date) else "",
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"FastF1 fallback could not load sessions: {e}")
        return pd.DataFrame()


# ── Session data ──────────────────────────────────────────────────────────────

def _load_session(year: int, country: str, session_type: str):
    """
    Load a FastF1 session without telemetry/weather (much faster).
    session_type should be an OpenF1-style name like "Race" or "Qualifying".
    """
    ff1_id = SESSION_NAME_MAP.get(session_type, session_type)
    session = fastf1.get_session(year, country, ff1_id)
    session.load(telemetry=False, weather=False, messages=False)
    return session


@st.cache_data(show_spinner="OpenF1 unavailable — loading laps from FastF1...")
def get_laps_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a laps DataFrame matching OpenF1's /laps columns:
      driver_number, lap_number, lap_duration (seconds), is_pit_out_lap
    """
    try:
        session = _load_session(year, country, session_type)
        laps = session.laps[["DriverNumber", "LapNumber", "LapTime", "PitOutTime"]].copy()
        laps["lap_duration"] = laps["LapTime"].dt.total_seconds()
        laps["is_pit_out_lap"] = laps["PitOutTime"].notna()
        laps = laps.rename(columns={
            "DriverNumber": "driver_number",
            "LapNumber": "lap_number",
        })
        return laps[["driver_number", "lap_number", "lap_duration", "is_pit_out_lap"]].dropna(subset=["lap_duration"])
    except Exception as e:
        st.warning(f"FastF1 fallback could not load lap data: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner="OpenF1 unavailable — loading stints from FastF1...")
def get_stints_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a stints DataFrame matching OpenF1's /stints columns:
      driver_number, stint_number, compound, lap_start, lap_end
    """
    try:
        session = _load_session(year, country, session_type)
        laps = session.laps[["DriverNumber", "LapNumber", "Stint", "Compound"]].copy()
        stints = (
            laps.groupby(["DriverNumber", "Stint", "Compound"], as_index=False)
            .agg(lap_start=("LapNumber", "min"), lap_end=("LapNumber", "max"))
        )
        stints = stints.rename(columns={
            "DriverNumber": "driver_number",
            "Stint": "stint_number",
            "Compound": "compound",
        })
        return stints[["driver_number", "stint_number", "compound", "lap_start", "lap_end"]]
    except Exception as e:
        st.warning(f"FastF1 fallback could not load stint data: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner="OpenF1 unavailable — loading pit stops from FastF1...")
def get_pit_stops_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a pit stops DataFrame matching OpenF1's /pit columns:
      driver_number, lap_number, pit_duration (seconds)

    FastF1 provides PitInTime and PitOutTime as session-elapsed timedeltas.
    We match inlaps to their subsequent outlap to calculate duration.
    """
    try:
        session = _load_session(year, country, session_type)
        laps = session.laps[["DriverNumber", "LapNumber", "PitInTime", "PitOutTime"]].copy()

        inlaps = laps[laps["PitInTime"].notna()][["DriverNumber", "LapNumber", "PitInTime"]].copy()
        inlaps["outlap_number"] = inlaps["LapNumber"] + 1

        outlaps = laps[laps["PitOutTime"].notna()][["DriverNumber", "LapNumber", "PitOutTime"]].copy()
        outlaps = outlaps.rename(columns={"LapNumber": "outlap_number"})

        merged = pd.merge(inlaps, outlaps, on=["DriverNumber", "outlap_number"], how="left")
        merged["pit_duration"] = (merged["PitOutTime"] - merged["PitInTime"]).dt.total_seconds()
        merged = merged.rename(columns={"DriverNumber": "driver_number", "LapNumber": "lap_number"})
        merged = merged[merged["pit_duration"].notna() & (merged["pit_duration"] > 0)]
        return merged[["driver_number", "lap_number", "pit_duration"]]
    except Exception as e:
        st.warning(f"FastF1 fallback could not load pit stop data: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner="OpenF1 unavailable — loading drivers from FastF1...")
def get_drivers_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a drivers DataFrame matching OpenF1's /drivers columns:
      driver_number, name_acronym, team_colour
    """
    try:
        session = _load_session(year, country, session_type)
        rows = []
        for drv_num in session.drivers:
            info = session.get_driver(drv_num)
            rows.append({
                "driver_number": str(drv_num),
                "name_acronym": info.get("Abbreviation", info.get("Tla", drv_num)),
                "team_colour": info.get("TeamColour", "AAAAAA"),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"FastF1 fallback could not load driver data: {e}")
        return pd.DataFrame()
