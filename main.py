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

# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(
        "<div style='display:flex;align-items:center;gap:10px;margin-bottom:16px'>"
        "<span style='font-size:28px;font-weight:900;color:#E8002D;letter-spacing:-1px'>F1</span>"
        "<span style='font-size:12px;font-weight:600;color:#B8B8C8;letter-spacing:3px;"
        "text-transform:uppercase'>Strategy</span></div>",
        unsafe_allow_html=True,
    )

    page = st.radio(
        "Navigation",
        ["📊 Session Analysis", "📅 Schedule & Results", "🏆 Championship"],
        label_visibility="collapsed",
    )
    st.divider()

# ── Page routing ──────────────────────────────────────────────────────────────

_AVAILABLE_YEARS = list(range(2023, datetime.now().year + 1))

if page == "📅 Schedule & Results":
    st.title("📅 Schedule & Results")
    year_col, _ = st.columns([1, 3])
    with year_col:
        sel_year = st.selectbox("Year", _AVAILABLE_YEARS, index=len(_AVAILABLE_YEARS) - 1, key="sched_year")
    from app.pages import schedule
    schedule.render(sel_year)
    st.stop()

if page == "🏆 Championship":
    st.title("🏆 Championship Standings")
    year_col, _ = st.columns([1, 3])
    with year_col:
        sel_year = st.selectbox("Year", _AVAILABLE_YEARS, index=len(_AVAILABLE_YEARS) - 1, key="champ_year")
    from app.pages import standings
    standings.render(sel_year)
    st.stop()

# ── Session Analysis page ─────────────────────────────────────────────────────

st.title("🏎️ Formula 1 Strategy Dashboard")
st.markdown("_Powered by FastF1 & OpenF1.org • Originally forked from OpenF1 project by Attila Bordan_")

sel_col1, sel_col2, sel_col3, sel_col4 = st.columns([1, 1, 2, 2])

with sel_col1:
    selected_year = st.selectbox("Year", _AVAILABLE_YEARS, index=len(_AVAILABLE_YEARS) - 1)

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
        if date_start.tzinfo is None:
            date_start = date_start.replace(tzinfo=timezone.utc)
        if date_end.tzinfo is None:
            date_end = date_end.replace(tzinfo=timezone.utc)
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

# ── Sidebar (continued) ───────────────────────────────────────────────────────

with st.sidebar:
    if live:
        st.markdown(
            "<div style='background:#E8002D;color:white;padding:8px 14px;"
            "border-radius:10px;font-weight:bold;text-align:center;margin-bottom:12px'>"
            "🔴 LIVE SESSION</div>",
            unsafe_allow_html=True,
        )
        st.markdown(f"Auto-refresh every **{LIVE_REFRESH_SECONDS}s**")
        st.divider()

    st.markdown("### 🏎️ Drivers")
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
    st.write(f"**Source:** {'FastF1' if fastf1_mode else 'Local API'}")
    if live:
        st.write("**Status:** 🔴 Live")

if not selected_drivers:
    st.warning("No drivers selected. Use the sidebar to select drivers.")
    st.stop()

# ── Live badge in header ──────────────────────────────────────────────────────

if live:
    st.markdown(
        "<span style='background:#E8002D;color:white;padding:4px 12px;"
        "border-radius:12px;font-weight:bold;font-size:0.85rem'>🔴 LIVE</span>",
        unsafe_allow_html=True,
    )

# ── Build context ─────────────────────────────────────────────────────────────

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

# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_labels = [chart.tab_label for chart in REGISTRY]
tabs = st.tabs(tab_labels)

for tab, chart in zip(tabs, REGISTRY):
    with tab:
        if not chart.is_available(selected_session_type):
            st.info(f"ℹ️ {chart.unavailable_message}")
            continue
        if live:
            @st.fragment(run_every=LIVE_REFRESH_SECONDS)
            def _live_render(c=chart, ctx=context):
                c.render(ctx)
            _live_render()
        else:
            chart.render(context)
