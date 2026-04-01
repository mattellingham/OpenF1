import base64
import json
import re
import subprocess
import time
from pathlib import Path

import streamlit as st
from datetime import datetime, timezone

_OPENF1_ENV = Path("/home/mellingham/openf1/.env-openf1")
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
        ["📊 Session Analysis", "📅 Schedule & Results", "🏆 Championship", "🔑 Token"],
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

# ── Token Update page ────────────────────────────────────────────────────────

if page == "🔑 Token":
    st.title("🔑 F1TV Token Update")

    def _decode_token(token: str) -> dict | None:
        try:
            payload = token.strip().split(".")[1]
            payload += "=" * (4 - len(payload) % 4)
            return json.loads(base64.b64decode(payload))
        except Exception:
            return None

    st.markdown(
        "Use the **F1TV bookmarklet** in your browser while logged into F1TV to copy "
        "your entitlement token, then paste it below. "
        "Tokens expire every 4 days — update before each race weekend."
    )

    with st.expander("📎 Bookmarklet setup (one-time)", expanded=False):
        bookmarklet = (
            "javascript:(function(){"
            "var t=null;"
            "var cookies=document.cookie.split(';');"
            "for(var i=0;i<cookies.length;i++){"
            "var parts=cookies[i].trim().split('=');"
            "var name=parts[0],val=decodeURIComponent(parts.slice(1).join('='));"
            "if(name==='entitlement_token'&&val.startsWith('eyJ')){t=val;break;}"
            "if(name==='login-session'){"
            "try{var d=JSON.parse(val);var s=d.data&&d.data.subscriptionToken;if(s&&s.startsWith('eyJ'))t=t||s;}catch(e){}}"
            "}"
            "if(!t){alert('F1TV token not found. Make sure you are logged into f1tv.formula1.com.');return;}"
            "navigator.clipboard.writeText(t)"
            ".then(function(){alert('Token copied!\\n\\nPaste it in your OpenF1 dashboard \\u2192 Token page.');})"
            ".catch(function(){prompt('Copy this token:',t);});"
            "})();"
        )
        st.markdown("1. Create a new bookmark in your browser")
        st.markdown("2. Set the **URL** to the code below (the name can be anything, e.g. *F1TV Token*)")
        st.code(bookmarklet, language=None)
        st.markdown("3. When logged into F1TV, click the bookmark — it copies your token to clipboard")
        st.markdown("4. Come back here and paste it")

    token_input = st.text_area("Paste token here", height=120, placeholder="eyJ...")
    if st.button("Update Token", type="primary", disabled=not token_input.strip()):
        token = token_input.strip()
        claims = _decode_token(token)
        if not claims:
            st.error("Not a valid token — could not decode.")
        elif claims.get("exp", 0) <= time.time():
            st.error("Token has already expired — get a fresh one from F1TV.")
        else:
            expires_in_h = (claims["exp"] - time.time()) / 3600
            try:
                content = _OPENF1_ENV.read_text()
                if re.search(r"^F1_TOKEN=.*$", content, re.MULTILINE):
                    content = re.sub(r"^F1_TOKEN=.*$", f"F1_TOKEN={token}", content, flags=re.MULTILINE)
                else:
                    content = content.rstrip("\n") + f"\nF1_TOKEN={token}\n"
                _OPENF1_ENV.write_text(content)
                subprocess.run(["sudo", "systemctl", "restart", "openf1-ingestor"], check=True)
                st.success(f"Token updated. Valid for {expires_in_h:.1f} hours. Ingestor restarted.")
            except subprocess.CalledProcessError:
                st.error("Token saved but could not restart ingestor — run `sudo systemctl restart openf1-ingestor` manually.")
            except Exception as e:
                st.error(f"Failed to update token: {e}")

    st.divider()
    st.markdown("#### Current token status")
    try:
        env = {
            k.strip(): v.strip()
            for line in _OPENF1_ENV.read_text().splitlines()
            if "=" in line and not line.startswith("#")
            for k, _, v in [line.partition("=")]
        }
        current = env.get("F1_TOKEN", "")
        claims = _decode_token(current) if current else None
        if not claims:
            st.warning("No valid token found in .env-openf1.")
        else:
            exp = claims.get("exp", 0)
            expires_in = exp - time.time()
            expires_dt = datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M")
            if expires_in <= 0:
                st.error(f"Token **expired** at {expires_dt}.")
            elif expires_in < 24 * 3600:
                st.warning(f"Token expires at {expires_dt} ({expires_in/3600:.1f}h remaining).")
            else:
                st.success(f"Token valid until {expires_dt} ({expires_in/3600:.1f}h remaining).")
    except Exception as e:
        st.error(f"Could not read token status: {e}")

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
    _meeting_rows = filtered_meetings.loc[filtered_meetings["label"] == selected_meeting, "meeting_key"]
    if _meeting_rows.empty:
        st.error("Could not resolve the selected Grand Prix. Please try a different selection.")
        st.stop()
    selected_meeting_key = _meeting_rows.values[0]

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
_session_row = sessions_df.loc[sessions_df["label"] == selected_session]
if _session_row.empty:
    st.error("Could not resolve the selected session. Please try a different selection.")
    st.stop()
selected_session_type = _session_row["session_type"].values[0]
selected_session_key = _session_row["session_key"].values[0]


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

if driver_df.empty:
    st.info("No data available for this session yet. It may not have taken place.")
    st.stop()

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
