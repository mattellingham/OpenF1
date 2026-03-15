import streamlit as st
from datetime import datetime, timezone
from app.data_loader import (
    OpenF1Unavailable,
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
from app.fastf1_fallback import (
    get_meetings_fastf1,
    get_sessions_fastf1,
    get_laps_fastf1,
    get_stints_fastf1,
    get_pit_stops_fastf1,
    get_drivers_fastf1,
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

st.set_page_config(page_title="F1 Strategy Dashboard", layout="wide")

st.title("🏎️ Formula 1 Strategy Dashboard")
st.markdown("_Powered by FastF1 & OpenF1.org • Originally forked from OpenF1 project by Attila Bordan_")

# ── Year / Country / Meeting selection ────────────────────────────────────────

col1, col2 = st.columns(2)

with col1:
    available_years = [2023, 2024, 2025, 2026]
    selected_year = st.selectbox("Select Year", available_years, index=len(available_years) - 1)

    # Try OpenF1 first; fall back to FastF1 for the full calendar
    fastf1_mode = False
    try:
        all_meetings = fetch_all_meetings(selected_year)
        if all_meetings.empty:
            raise OpenF1Unavailable("No meetings returned")
    except OpenF1Unavailable:
        fastf1_mode = True
        all_meetings = get_meetings_fastf1(selected_year)

    if all_meetings.empty:
        st.error("No calendar data available from either OpenF1 or FastF1.")
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

    # Fetch sessions — use FastF1 if we're already in fallback mode or if
    # OpenF1 fails for this specific meeting
    if fastf1_mode:
        sessions_df = get_sessions_fastf1(selected_year, selected_country)
    else:
        try:
            sessions_df = fetch_sessions(selected_meeting_key)
        except OpenF1Unavailable:
            fastf1_mode = True
            sessions_df = get_sessions_fastf1(selected_year, selected_country)

    if sessions_df.empty:
        st.error("No session data available.")
        st.stop()

    selected_session = st.selectbox("Select Session", sessions_df["label"])
    sessions_df["session_type"] = sessions_df["label"].str.extract(r"^(.*?)\s\(")
    selected_session_type = sessions_df.loc[
        sessions_df["label"] == selected_session, "session_type"
    ].values[0]
    selected_session_key = sessions_df.loc[
        sessions_df["label"] == selected_session, "session_key"
    ].values[0]


# ── Live detection ────────────────────────────────────────────────────────────

def is_session_live(session_key) -> bool:
    """Returns False immediately in FastF1 mode — can't check without OpenF1."""
    if fastf1_mode:
        return False
    try:
        from app.data_loader import fetch_data
        session_rows = fetch_data("sessions", {"session_key": session_key})
        if session_rows.empty:
            return False
        row = session_rows.iloc[0]
        date_start = datetime.fromisoformat(str(row.get("date_start", "")))
        date_end = datetime.fromisoformat(str(row.get("date_end", "")))
        return date_start <= datetime.now(timezone.utc) <= date_end
    except Exception:
        return False


live = is_session_live(selected_session_key)

# ── Session header ────────────────────────────────────────────────────────────

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
    st.write(f"**Data source:** {'FastF1 (historical) / Local ingestor (live)' if fastf1_mode else 'Local OpenF1'}")
    st.write(f"**Live session:** {'Yes' if live else 'No'}")
    if live:
        st.write(f"**Auto-refresh:** every {LIVE_REFRESH_SECONDS}s")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _get_drivers_and_colors(session_key, year, country, session_type, is_live=False):
    """Fetch driver info, using FastF1 if OpenF1 is unavailable."""
    if fastf1_mode:
        driver_df = get_drivers_fastf1(year, country, session_type)
    else:
        try:
            fn = fetch_drivers_live if is_live else fetch_drivers
            driver_df = fn(session_key)
        except OpenF1Unavailable:
            driver_df = get_drivers_fastf1(year, country, session_type)

    driver_df["driver_number"] = driver_df["driver_number"].astype(str)
    color_map = build_driver_color_map(driver_df)
    info = driver_df[["driver_number", "name_acronym"]]
    return color_map, info


# ── Chart render functions ────────────────────────────────────────────────────

def _source_caption(source: str):
    if source == "FastF1":
        st.caption("Data source: FastF1")


def render_lap_times(session_key, session_type, country, year, is_live=False):
    color_map, driver_info = _get_drivers_and_colors(
        session_key, year, country, session_type, is_live
    )
    with st.expander(f"📈 Lap Time Chart for {session_type} at {country} {year}", expanded=True):
        if fastf1_mode:
            st.info("⚡ OpenF1 unavailable — using FastF1 data", icon="ℹ️")
            lap_df = get_laps_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                fn = fetch_laps_live if is_live else fetch_laps
                lap_df = fn(session_key)
                source = "OpenF1"
            except OpenF1Unavailable:
                st.info("⚡ OpenF1 unavailable — using FastF1 data", icon="ℹ️")
                lap_df = get_laps_fastf1(year, country, session_type)
                source = "FastF1"

        processed_df = process_lap_data(lap_df)
        processed_df["driver_number"] = processed_df["driver_number"].astype(str)
        processed_df = processed_df.merge(driver_info, on="driver_number", how="left")

        if processed_df.empty:
            st.warning("No lap time data found.")
        else:
            fig = plot_lap_times(processed_df, color_map)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                _source_caption(source)

    return color_map, driver_info


def render_tire_strategy(session_key, session_type, country, year, driver_info, color_map, is_live=False):
    with st.expander(f"🛞 Tire strategy for {session_type} at {country} {year}", expanded=True):
        if fastf1_mode:
            st.info("⚡ OpenF1 unavailable — using FastF1 data", icon="ℹ️")
            stints = get_stints_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                fn = fetch_stints_live if is_live else fetch_stints
                stints = fn(session_key)
                source = "OpenF1"
            except OpenF1Unavailable:
                st.info("⚡ OpenF1 unavailable — using FastF1 data", icon="ℹ️")
                stints = get_stints_fastf1(year, country, session_type)
                source = "FastF1"

        stints_df = process_stints(stints)
        stints_df["driver_number"] = stints_df["driver_number"].astype(str)
        stints_df = stints_df.merge(driver_info, on="driver_number", how="left")

        if stints_df.empty:
            st.warning("No tire strategy data found.")
        else:
            fig = plot_tire_strategy(stints_df, color_map)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                _source_caption(source)


def render_pit_stops(session_key, session_type, country, year, driver_info, color_map, is_live=False):
    with st.expander(f"⏱  Pit stop durations for {session_type} at {country} {year}", expanded=True):
        if fastf1_mode:
            st.info("⚡ OpenF1 unavailable — using FastF1 data", icon="ℹ️")
            pit_stop = get_pit_stops_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                fn = fetch_pit_stop_live if is_live else fetch_pit_stop
                pit_stop = fn(session_key)
                source = "OpenF1"
            except OpenF1Unavailable:
                st.info("⚡ OpenF1 unavailable — using FastF1 data", icon="ℹ️")
                pit_stop = get_pit_stops_fastf1(year, country, session_type)
                source = "FastF1"

        pit_stop_df = process_pit_stops(pit_stop)
        pit_stop_df["driver_number"] = pit_stop_df["driver_number"].astype(str)
        pit_stop_df = pit_stop_df.merge(driver_info, on="driver_number", how="left")

        if pit_stop_df.empty:
            st.warning("No pit stop data found.")
        else:
            fig = plot_pit_stop(pit_stop_df, color_map)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
                _source_caption(source)


# ── Routing: live fragments vs historical single render ───────────────────────

if live:
    @st.fragment(run_every=LIVE_REFRESH_SECONDS)
    def live_lap_times():
        render_lap_times(
            selected_session_key, selected_session_type,
            selected_country, selected_year, is_live=True
        )

    @st.fragment(run_every=LIVE_REFRESH_SECONDS)
    def live_tire_strategy():
        color_map, info = _get_drivers_and_colors(
            selected_session_key, selected_year,
            selected_country, selected_session_type, is_live=True
        )
        render_tire_strategy(
            selected_session_key, selected_session_type,
            selected_country, selected_year, info, color_map, is_live=True
        )

    @st.fragment(run_every=LIVE_REFRESH_SECONDS)
    def live_pit_stops():
        color_map, info = _get_drivers_and_colors(
            selected_session_key, selected_year,
            selected_country, selected_session_type, is_live=True
        )
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
