"""
FastF1 fallback data source.

Used when OpenF1's API is unavailable (502/503). Loads session data from
F1's official live timing feed via the FastF1 library, then reshapes it
into DataFrames that match the column names the rest of the app expects.

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

# FastF1 session identifier mapped from OpenF1's session_name strings
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


def _load_session(year: int, country: str, session_type: str):
    """
    Load a FastF1 session. Telemetry and weather are skipped — we only need
    lap/stint/pit/driver data, which loads much faster without them.
    """
    ff1_id = SESSION_NAME_MAP.get(session_type, session_type)
    session = fastf1.get_session(year, country, ff1_id)
    session.load(telemetry=False, weather=False, messages=False)
    return session


@st.cache_data(show_spinner="OpenF1 unavailable — loading from FastF1...")
def get_laps_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a laps DataFrame with columns matching OpenF1's /laps endpoint:
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


@st.cache_data(show_spinner="OpenF1 unavailable — loading from FastF1...")
def get_stints_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a stints DataFrame with columns matching OpenF1's /stints endpoint:
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


@st.cache_data(show_spinner="OpenF1 unavailable — loading from FastF1...")
def get_pit_stops_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a pit stops DataFrame with columns matching OpenF1's /pit endpoint:
      driver_number, lap_number, pit_duration (seconds)

    FastF1 gives PitInTime (session time on the inlap) and PitOutTime
    (session time on the outlap). We join them by driver + consecutive lap
    number to calculate duration.
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
        merged = merged.rename(columns={
            "DriverNumber": "driver_number",
            "LapNumber": "lap_number",
        })
        merged = merged[merged["pit_duration"].notna() & (merged["pit_duration"] > 0)]
        return merged[["driver_number", "lap_number", "pit_duration"]]
    except Exception as e:
        st.warning(f"FastF1 fallback could not load pit stop data: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner="OpenF1 unavailable — loading from FastF1...")
def get_drivers_fastf1(year: int, country: str, session_type: str) -> pd.DataFrame:
    """
    Returns a drivers DataFrame with columns matching OpenF1's /drivers endpoint:
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
