import streamlit as st
from datetime import datetime, timezone
from app.data_loader import (
    fetch_all_meetings,
    fetch_sessions,
    fetch_laps,
    fetch_stints,
    fetch_pit_stop,
    fetch_drivers,
    fetch_laps_live,
    fetch_stints_live,
    fetch_pit_stop_live,
    fetch_drivers_live,
)
from app.data_processor import (
    process_lap_data,
    process_stints,
    process_pit_stops,
    build_driver_color_map
)
from app.visualizer import (
    plot_lap_times,
    plot_tire_strategy,
    plot_pit_stop
)

LIVE_REFRESH_SECONDS = 30

st.set_page_config(page_title="F1 Dashboard", layout="wide")

st.title("🏎️ Formula 1 Strategy Dashboard")
st.markdown("_Powered by OpenF1.org • Forked from a project by Attila Bordan_")

col1, col2 = st.columns(2)

with col1:
    available_years = [2023, 2024, 2025, 2026]
    selected_year = st.selectbox("Select Year", available_years, index=len(available_years) - 1)

    all_meetings = fetch_all_meetings(selected_year)

    if all_meetings.empty:
        st.error("No meetings found for this year.")
        st.stop()

    available_countries = sorted(all_meetings["country_name"].dropna().unique())
    selected_country = st.selectbox("Select Country", available_countries)

    filtered_meetings = all_meetings[all_meetings["country_name"] == selected_country].copy()
    filtered_meetings["label"] = filtered_meetings["meeting_name"] + " - " + filtered_meetings["location"]
    filtered_meetings = filtered_meetings.sort_values(by="meeting_key", ascending=False)

with col2:
    selected_meeting = st.selectbox("Select Grand Prix", filtered_meetings["label"], disabled=True)
    selected_meeting_key = filtered_meetings.loc[
        filtered_meetings["label"] == selected_meeting, "meeting_key"
    ].values[0]

    full_sessions = fetch_sessions(selected_meeting_key)
    selected_session = st.selectbox("Select Session", full_sessions["label"])
    full_sessions["session_type"] = full_sessions["label"].str.extract(r"^(.*?)\s\(")
    selected_session_type = full_sessions.loc[full_sessions["label"] == selected_session, "session_type"].values[0]
    selected_session_key = full_sessions.loc[full_sessions["label"] == selected_session, "session_key"].values[0]


def is_session_live(session_key) -> bool:
    """
    Return True if the selected session is currently in progress.
    Compares the session's date_start and date_end against the current UTC time.
    """
    try:
        from app.data_loader import fetch_data
        session_rows = fetch_data("sessions", {"session_key": session_key})
        if session_rows.empty:
            return False
        row = session_rows.iloc[0]
        date_start_str = row.get("date_start")
        date_end_str = row.get("date_end")
        if not date_start_str or not date_end_str:
            return False
        date_start = datetime.fromisoformat(str(date_start_str))
        date_end = datetime.fromisoformat(str(date_end_str))
        now = datetime.now(timezone.utc)
        return date_start <= now <= date_end
    except Exception:
        return False


live = is_session_live(selected_session_key)

# Session header with live badge
header_col, badge_col = st.columns([8, 1])
with header_col:
    st.markdown(f"### 🏁 Session Overview: `{selected_session}`")
with badge_col:
    if live:
        st.markdown(
            "<span style='background:#e00000;color:white;padding:4px 10px;"
            "border-radius:12px;font-weight:bold;font-size:0.85rem'>🔴 LIVE</span>",
            unsafe_allow_html=True
        )

with st.expander("📋 Session Details", expanded=False):
    st.write(f"**Meeting Key:** {selected_meeting_key}")
    st.write(f"**Session Key:** {selected_session_key}")
    st.write(f"**Live session:** {'Yes' if live else 'No'}")
    if live:
        st.write(f"**Auto-refresh:** every {LIVE_REFRESH_SECONDS}s")


def render_lap_times(session_key, session_type, country, year, is_live):
    get_laps = fetch_laps_live if is_live else fetch_laps
    get_drivers = fetch_drivers_live if is_live else fetch_drivers

    driver_df = get_drivers(session_key)
    driver_df["driver_number"] = driver_df["driver_number"].astype(str)
    driver_color_map = build_driver_color_map(driver_df)
    driver_info = driver_df[["driver_number", "name_acronym"]]

    with st.expander(f"📈 Lap Time Chart for {session_type} at {country} {year}", expanded=True):
        lap_df = get_laps(session_key)
        processed_df = process_lap_data(lap_df)
        processed_df["driver_number"] = processed_df["driver_number"].astype(str)
        processed_df = processed_df.merge(driver_info, on="driver_number", how="left")

        if processed_df.empty:
            st.warning("No lap time data found.")
        else:
            fig = plot_lap_times(processed_df, driver_color_map)
            if fig:
                st.plotly_chart(fig, use_container_width=True)

    return driver_color_map, driver_info


def render_tire_strategy(session_key, session_type, country, year, driver_info, driver_color_map, is_live):
    get_stints = fetch_stints_live if is_live else fetch_stints

    with st.expander(f"🛞 Tire strategy for {session_type} at {country} {year}", expanded=True):
        stints = get_stints(session_key)
        stints_df = process_stints(stints)
        stints_df["driver_number"] = stints_df["driver_number"].astype(str)
        stints_df = stints_df.merge(driver_info, on="driver_number", how="left")

        if stints_df.empty:
            st.warning("No tire strategy data found.")
        else:
            fig = plot_tire_strategy(stints_df, driver_color_map)
            if fig:
                st.plotly_chart(fig, use_container_width=True)


def render_pit_stops(session_key, session_type, country, year, driver_info, driver_color_map, is_live):
    get_pit = fetch_pit_stop_live if is_live else fetch_pit_stop

    with st.expander(f"⏱  Pit stop durations for {session_type} at {country} {year}", expanded=True):
        pit_stop = get_pit(session_key)
        pit_stop_df = process_pit_stops(pit_stop)
        pit_stop_df["driver_number"] = pit_stop_df["driver_number"].astype(str)
        pit_stop_df = pit_stop_df.merge(driver_info, on="driver_number", how="left")

        if pit_stop_df.empty:
            st.warning("No pit stop data found.")
        else:
            fig = plot_pit_stop(pit_stop_df, driver_color_map)
            if fig:
                st.plotly_chart(fig, use_container_width=True)


if live:
    @st.fragment(run_every=LIVE_REFRESH_SECONDS)
    def live_lap_times():
        render_lap_times(
            selected_session_key, selected_session_type,
            selected_country, selected_year, is_live=True
        )

    @st.fragment(run_every=LIVE_REFRESH_SECONDS)
    def live_tire_strategy():
        driver_df = fetch_drivers_live(selected_session_key)
        driver_df["driver_number"] = driver_df["driver_number"].astype(str)
        color_map = build_driver_color_map(driver_df)
        info = driver_df[["driver_number", "name_acronym"]]
        render_tire_strategy(
            selected_session_key, selected_session_type,
            selected_country, selected_year, info, color_map, is_live=True
        )

    @st.fragment(run_every=LIVE_REFRESH_SECONDS)
    def live_pit_stops():
        driver_df = fetch_drivers_live(selected_session_key)
        driver_df["driver_number"] = driver_df["driver_number"].astype(str)
        color_map = build_driver_color_map(driver_df)
        info = driver_df[["driver_number", "name_acronym"]]
        render_pit_stops(
            selected_session_key, selected_session_type,
            selected_country, selected_year, info, color_map, is_live=True
        )

    live_lap_times()
    live_tire_strategy()
    live_pit_stops()

else:
    color_map, driver_info = render_lap_times(
        selected_session_key, selected_session_type,
        selected_country, selected_year, is_live=False
    )
    render_tire_strategy(
        selected_session_key, selected_session_type,
        selected_country, selected_year, driver_info, color_map, is_live=False
    )
    render_pit_stops(
        selected_session_key, selected_session_type,
        selected_country, selected_year, driver_info, color_map, is_live=False
    )
