import streamlit as st
from datetime import datetime, timezone
from app.data_loader import (
    OpenF1Unavailable,
    fetch_all_meetings,
    fetch_sessions,
    fetch_drivers,
    fetch_drivers_live,
)
from app.fastf1_fallback import (
    get_meetings_fastf1,
    get_sessions_fastf1,
    get_drivers_fastf1,
)
from app.data_processor import build_driver_color_map
from app.charts import REGISTRY

LIVE_REFRESH_SECONDS = 30

st.set_page_config(
    page_title="F1 Strategy Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Header ────────────────────────────────────────────────────────────────────

st.title("🏎️ Formula 1 Strategy Dashboard")
st.markdown("_Powered by FastF1 & OpenF1.org • Originally forked from OpenF1 project by Attila Bordan_")

# ── Session selection ─────────────────────────────────────────────────────────

sel_col1, sel_col2, sel_col3, sel_col4 = st.columns([1, 1, 2, 2])

with sel_col1:
    available_years = [2023, 2024, 2025, 2026]
    selected_year = st.selectbox("Year", available_years, index=len(available_years) - 1)

# Fetch meetings — try local API, fall back to FastF1
fastf1_mode = False
try:
    all_meetings = fetch_all_meetings(selected_year)
except OpenF1Unavailable:
    fastf1_mode = True
    all_meetings = get_meetings_fastf1(selected_year)

if all_meetings.empty:
    st.error("No calendar data available from either the local API or FastF1.")
    st.stop()

with sel_col2:
    available_countries = sorted(all_meetings["country_name"].dropna().unique())
    selected_country = st.selectbox("Country", available_countries)

filtered_meetings = all_meetings[all_meetings["country_name"] == selected_country].copy()
filtered_meetings["label"] = filtered_meetings["meeting_name"] + " – " + filtered_meetings["location"]
filtered_meetings = filtered_meetings.sort_values(by="meeting_key", ascending=False)

with sel_col3:
    selected_meeting = st.selectbox("Grand Prix", filtered_meetings["label"], disabled=True)
    selected_meeting_key = filtered_meetings.loc[
        filtered_meetings["label"] == selected_meeting, "meeting_key"
    ].values[0]

# Fetch sessions
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

with sel_col4:
    selected_session = st.selectbox("Session", sessions_df["label"])

sessions_df["session_type"] = sessions_df["label"].str.extract(r"^(.*?)\s\(")
selected_session_type = sessions_df.loc[
    sessions_df["label"] == selected_session, "session_type"
].values[0]
selected_session_key = sessions_df.loc[
    sessions_df["label"] == selected_session, "session_key"
].values[0]


# ── Live detection ────────────────────────────────────────────────────────────

def is_session_live(session_key) -> bool:
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

# ── Driver data ───────────────────────────────────────────────────────────────

if fastf1_mode:
    driver_df = get_drivers_fastf1(selected_year, selected_country, selected_session_type)
else:
    try:
        fn = fetch_drivers_live if live else fetch_drivers
        driver_df = fn(selected_session_key)
    except OpenF1Unavailable:
        driver_df = get_drivers_fastf1(selected_year, selected_country, selected_session_type)

driver_df["driver_number"] = driver_df["driver_number"].astype(str)
color_map = build_driver_color_map(driver_df)
driver_info = driver_df[["driver_number", "name_acronym"]]
all_drivers = sorted(driver_df["name_acronym"].dropna().unique().tolist())

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## 🏎️ Filters")

    # Live badge
    if live:
        st.markdown(
            "<div style='background:#e00000;color:white;padding:8px 14px;"
            "border-radius:10px;font-weight:bold;text-align:center;margin-bottom:12px'>"
            "🔴 LIVE SESSION</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"Auto-refresh every **{LIVE_REFRESH_SECONDS}s**")
        st.divider()

    st.markdown("### Drivers")
    select_all = st.checkbox("Select all", value=True)
    if select_all:
        selected_drivers = all_drivers
    else:
        selected_drivers = st.multiselect(
            "Choose drivers",
            options=all_drivers,
            default=all_drivers[:3] if len(all_drivers) >= 3 else all_drivers,
        )

    st.divider()
    st.markdown("### Session Info")
    st.write(f"**Year:** {selected_year}")
    st.write(f"**Country:** {selected_country}")
    st.write(f"**Session:** {selected_session_type}")
    st.write(f"**Data source:** {'FastF1' if fastf1_mode else 'Local API'}")
    if live:
        st.write(f"**Status:** 🔴 Live")

if not selected_drivers:
    st.warning("No drivers selected. Use the sidebar to select drivers.")
    st.stop()

# ── Build context dict passed to every chart ──────────────────────────────────

context = {
    "session_key": selected_session_key,
    "session_type": selected_session_type,
    "country": selected_country,
    "year": selected_year,
    "driver_info": driver_info,
    "color_map": color_map,
    "selected_drivers": selected_drivers,
    "fastf1_mode": fastf1_mode,
    "is_live": live,
}

# ── Tab layout ────────────────────────────────────────────────────────────────

tab_labels = [chart.tab_label for chart in REGISTRY]
tabs = st.tabs(tab_labels)

for tab, chart in zip(tabs, REGISTRY):
    with tab:
        if not chart.is_available(selected_session_type):
            st.info(f"ℹ️ {chart.unavailable_message}")
            continue

        if live:
            # Wrap each chart in a fragment so it refreshes independently
            # without rebuilding the whole page
            @st.fragment(run_every=LIVE_REFRESH_SECONDS)
            def _live_render(c=chart, ctx=context):
                c.render(ctx)
            _live_render()
        else:
            chart.render(context)
