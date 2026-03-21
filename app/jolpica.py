"""
Jolpica API client (successor to the Ergast F1 API).

Used for season-level data: schedule, race results, championship standings.
All functions return plain DataFrames or dicts and are cached with st.cache_data.
"""

import logging
import requests
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

BASE = "https://api.jolpi.ca/ergast/f1"

# Constructor ID → hex colour (matches the current 2026 team palette)
CONSTRUCTOR_COLORS = {
    "red_bull":         "#3671C6",
    "ferrari":          "#E8002D",
    "mercedes":         "#27F4D2",
    "mclaren":          "#FF8000",
    "aston_martin":     "#229971",
    "alpine":           "#FF87BC",
    "williams":         "#64C4FF",
    "haas":             "#B6BABD",
    "rb":               "#6692FF",
    "visa_rb_f1_team":  "#6692FF",
    "kick_sauber":      "#52E252",
    "sauber":           "#52E252",
}

COUNTRY_FLAGS = {
    "Australia": "🇦🇺", "Bahrain": "🇧🇭", "Saudi Arabia": "🇸🇦",
    "Japan": "🇯🇵", "China": "🇨🇳", "USA": "🇺🇸", "United States": "🇺🇸",
    "Italy": "🇮🇹", "Monaco": "🇲🇨", "Canada": "🇨🇦", "Spain": "🇪🇸",
    "Austria": "🇦🇹", "Britain": "🇬🇧", "Hungary": "🇭🇺", "Belgium": "🇧🇪",
    "Netherlands": "🇳🇱", "Singapore": "🇸🇬", "Azerbaijan": "🇦🇿",
    "Mexico": "🇲🇽", "Brazil": "🇧🇷", "Las Vegas": "🇺🇸", "Qatar": "🇶🇦",
    "Abu Dhabi": "🇦🇪", "UAE": "🇦🇪", "Bahrain": "🇧🇭",
    "Imola": "🇮🇹", "Miami": "🇺🇸",
}


def _get(url: str, timeout: int = 10) -> dict:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()


# Team display name → constructor ID (covers OpenF1 API and FastF1 team name variants)
_TEAM_NAME_TO_CONSTRUCTOR = {
    "red bull racing":  "red_bull",
    "red bull":         "red_bull",
    "ferrari":          "ferrari",
    "scuderia ferrari": "ferrari",
    "mercedes":         "mercedes",
    "mclaren":          "mclaren",
    "aston martin":     "aston_martin",
    "aston martin aramco": "aston_martin",
    "alpine":           "alpine",
    "alpine f1 team":   "alpine",
    "williams":         "williams",
    "williams racing":  "williams",
    "haas":             "haas",
    "haas f1 team":     "haas",
    "rb":               "rb",
    "visa cash app rb": "rb",
    "racing bulls":     "rb",
    "kick sauber":      "kick_sauber",
    "sauber":           "sauber",
}


def team_color(constructor_id: str) -> str:
    return CONSTRUCTOR_COLORS.get(constructor_id.lower().replace("-", "_"), "#888888")


def team_color_by_name(team_name: str) -> str:
    """Resolve a team display name (from OpenF1 or FastF1) to its canonical hex colour."""
    constructor_id = _TEAM_NAME_TO_CONSTRUCTOR.get(team_name.lower().strip(), "")
    return CONSTRUCTOR_COLORS.get(constructor_id, "")


def country_flag(country: str) -> str:
    for k, v in COUNTRY_FLAGS.items():
        if k.lower() in country.lower():
            return v
    return "🏁"


@st.cache_data(ttl=300)
def get_schedule(year: int) -> list:
    """Return list of races for the given year from Jolpica."""
    try:
        data = _get(f"{BASE}/{year}.json?limit=30")
        return data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
    except Exception as e:
        logger.warning("Jolpica get_schedule(%s) failed: %s", year, e, exc_info=True)
        return []


@st.cache_data(ttl=60)
def get_driver_standings(year: int = None) -> list:
    """Return current driver championship standings."""
    try:
        path = f"{BASE}/{year}/driverStandings.json" if year else f"{BASE}/current/driverStandings.json"
        data = _get(path)
        tables = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
        return tables[0].get("DriverStandings", []) if tables else []
    except Exception as e:
        logger.warning("Jolpica get_driver_standings(%s) failed: %s", year, e, exc_info=True)
        return []


@st.cache_data(ttl=60)
def get_constructor_standings(year: int = None) -> list:
    """Return current constructor championship standings."""
    try:
        path = f"{BASE}/{year}/constructorStandings.json" if year else f"{BASE}/current/constructorStandings.json"
        data = _get(path)
        tables = data.get("MRData", {}).get("StandingsTable", {}).get("StandingsLists", [])
        return tables[0].get("ConstructorStandings", []) if tables else []
    except Exception as e:
        logger.warning("Jolpica get_constructor_standings(%s) failed: %s", year, e, exc_info=True)
        return []


@st.cache_data(ttl=300)
def get_race_results(year: int, round_num: int) -> dict | None:
    """Return full results for a specific race."""
    try:
        data = _get(f"{BASE}/{year}/{round_num}/results.json")
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        return races[0] if races else None
    except Exception as e:
        logger.warning("Jolpica get_race_results(%s, %s) failed: %s", year, round_num, e, exc_info=True)
        return None


@st.cache_data(ttl=300)
def get_qualifying_results(year: int, round_num: int) -> dict | None:
    """Return qualifying results for a specific race."""
    try:
        data = _get(f"{BASE}/{year}/{round_num}/qualifying.json")
        races = data.get("MRData", {}).get("RaceTable", {}).get("Races", [])
        return races[0] if races else None
    except Exception as e:
        logger.warning("Jolpica get_qualifying_results(%s, %s) failed: %s", year, round_num, e, exc_info=True)
        return None
