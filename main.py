import base64
import json
import re
import subprocess
import time
from pathlib import Path

import pandas as pd
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

# ── Global CSS + font ─────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700;900&display=swap');

html, body, [class*="css"], .stMarkdown p, .stText, button, input, select,
[data-testid="stSidebar"], [data-baseweb="tab"] {
    font-family: 'Titillium Web', sans-serif !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0F0F1A; }
::-webkit-scrollbar-thumb { background: #2E2E42; border-radius: 3px; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    border-bottom: 1px solid #2E2E42;
    padding-bottom: 0;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px 6px 0 0;
    padding: 6px 16px;
    color: #6B6B7B;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.4px;
    background: transparent;
    border: 1px solid transparent;
    border-bottom: none;
}
.stTabs [aria-selected="true"] {
    background: #15151E !important;
    color: #E8E8F0 !important;
    border-color: #2E2E42 !important;
    border-bottom-color: #15151E !important;
}

/* Sidebar border */
section[data-testid="stSidebar"] > div {
    border-right: 1px solid #2E2E42;
}

/* Tabular numbers for all timing/numeric data */
.stDataFrame, table, td, th, .stMetric {
    font-variant-numeric: tabular-nums;
}

/* Pulsing live ring */
@keyframes pulse-ring {
    0%   { box-shadow: 0 0 0 0   rgba(232,0,45,0.55); }
    70%  { box-shadow: 0 0 0 8px rgba(232,0,45,0);    }
    100% { box-shadow: 0 0 0 0   rgba(232,0,45,0);    }
}
.live-pulse { animation: pulse-ring 1.8s ease infinite; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar navigation ────────────────────────────────────────────────────────

with st.sidebar:
    st.html(
        "<div style='display:flex;align-items:center;gap:10px;margin-bottom:16px'>"
        "<span style='font-size:28px;font-weight:900;color:#E8002D;letter-spacing:-1px'>F1</span>"
        "<span style='font-size:12px;font-weight:600;color:#B8B8C8;letter-spacing:3px;"
        "text-transform:uppercase'>Strategy</span></div>"
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

# ── Helpers for smart defaults ───────────────────────────────────────────────

def _default_country_index(meetings_df: pd.DataFrame, year: int) -> int:
    """Return the selectbox index for the most recent or current race weekend."""
    try:
        import fastf1
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        today = datetime.now(timezone.utc).date()
        schedule["_start_date"] = pd.to_datetime(schedule["Session1DateUtc"]).dt.date
        past = schedule[schedule["_start_date"] <= today]
        row = past.iloc[-1] if not past.empty else schedule.iloc[0]
        country = row["Country"]
        countries = sorted(meetings_df["country_name"].dropna().unique().tolist())
        if country in countries:
            return countries.index(country)
    except Exception:
        pass
    return 0


def _default_session_index(sessions_df: pd.DataFrame) -> int:
    """Return the selectbox index for the most recently started session."""
    try:
        now = datetime.now(timezone.utc)
        df = sessions_df.copy()
        df["_dt"] = pd.to_datetime(df["date_start"], utc=True, errors="coerce")
        past = df[df["_dt"].notna() & (df["_dt"] <= now)]
        if not past.empty:
            last_label = past.iloc[-1]["label"]
            return sessions_df["label"].tolist().index(last_label)
    except Exception:
        pass
    return 0


# ── Session Analysis page ─────────────────────────────────────────────────────

st.html(
    "<div style='margin-bottom:4px'>"
    "<span style='font-size:22px;font-weight:900;color:#E8002D;letter-spacing:-0.5px'>F1</span>"
    "<span style='font-size:18px;font-weight:700;color:#E8E8F0;margin-left:8px'>Strategy Dashboard</span>"
    "<span style='font-size:11px;color:#6B6B7B;margin-left:12px'>"
    "Powered by FastF1 &amp; OpenF1.org</span></div>"
)

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
    selected_country = st.selectbox(
        "Country",
        available_countries,
        index=_default_country_index(all_meetings, selected_year),
    )

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
    selected_session = st.selectbox(
        "Session",
        sessions_df["label"],
        index=_default_session_index(sessions_df),
    )

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
        st.html(
            "<div class='live-pulse' style='background:#E8002D;color:white;padding:8px 14px;"
            "border-radius:10px;font-weight:bold;text-align:center;margin-bottom:8px'>"
            "● LIVE SESSION</div>"
            f"<div style='font-size:11px;color:#8E8EA8;text-align:center;margin-bottom:12px'>"
            f"Auto-refresh every {LIVE_REFRESH_SECONDS}s</div>"
        )
        st.divider()

    st.markdown("### 🏎️ Drivers")

    # Driver roster — visual reference with team colours
    roster_html = '<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:12px">'
    for drv in all_drivers:
        color = color_map.get(drv, "#888")
        roster_html += (
            f'<div style="background:#1A1A2E;border:1px solid {color}55;border-radius:6px;'
            f'padding:4px 7px;display:flex;align-items:center;gap:5px">'
            f'<span style="display:inline-block;width:3px;height:14px;background:{color};border-radius:2px"></span>'
            f'<span style="font-size:11px;font-weight:700;color:#E8E8F0;letter-spacing:0.5px">{drv}</span>'
            f'</div>'
        )
    roster_html += '</div>'
    st.html(roster_html)

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

# ── Session header card ───────────────────────────────────────────────────────

from app.jolpica import country_flag as _country_flag

_header_row = filtered_meetings.loc[filtered_meetings["label"] == selected_meeting]
_circuit_name = _header_row["meeting_name"].values[0] if not _header_row.empty else selected_country
_location = _header_row["location"].values[0] if not _header_row.empty else ""
_flag = _country_flag(selected_country)

_SESSION_BADGE = {
    "Race":              ("#E8002D", "#fff"),
    "Sprint":            ("#E8002D", "#fff"),
    "Qualifying":        ("#FF8700", "#000"),
    "Sprint Qualifying": ("#FF8700", "#000"),
    "Sprint Shootout":   ("#FF8700", "#000"),
    "Practice":          ("#0067FF", "#fff"),
}
_badge_bg, _badge_fg = next(
    (v for k, v in _SESSION_BADGE.items() if selected_session_type.startswith(k)),
    ("#444", "#fff"),
)

_live_chip = (
    '<span class="live-pulse" style="display:inline-block;background:#E8002D;color:#fff;'
    'padding:4px 12px;border-radius:6px;font-size:11px;font-weight:700;letter-spacing:1px">'
    '● LIVE</span>'
) if live else ""

st.html(
    f"""<div style="background:#15151E;border:1px solid #2E2E42;border-radius:10px;
                    padding:14px 20px;margin:4px 0 18px;display:flex;align-items:center;
                    gap:16px;box-shadow:0 2px 10px rgba(0,0,0,0.4)">
      <div style="font-size:38px;line-height:1;flex-shrink:0">{_flag}</div>
      <div style="flex:1;min-width:0">
        <div style="font-size:11px;color:#6B6B7B;letter-spacing:2px;text-transform:uppercase;
                    margin-bottom:3px">{selected_year}</div>
        <div style="font-size:19px;font-weight:700;color:#E8E8F0;line-height:1.2;
                    white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{_circuit_name}</div>
        <div style="font-size:12px;color:#8E8EA8;margin-top:2px">{_location}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0">
        <span style="background:{_badge_bg};color:{_badge_fg};padding:5px 14px;border-radius:6px;
                     font-size:11px;font-weight:700;letter-spacing:1px">
          {selected_session_type.upper()}
        </span>
        {_live_chip}
      </div>
    </div>"""
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

# ── Race control banner ───────────────────────────────────────────────────────

try:
    from app.fastf1_fallback import get_race_control_fastf1 as _get_rc
    _rc = _get_rc(selected_year, selected_country, selected_session_type)
    if _rc is not None and not _rc.empty:
        _RC_ICON = {
            "GREEN":          ("🟢", "#22c55e", "#000"),
            "YELLOW":         ("🟡", "#fbbf24", "#000"),
            "DOUBLE YELLOW":  ("🟡", "#f59e0b", "#000"),
            "RED":            ("🔴", "#ef4444", "#fff"),
            "CHEQUERED":      ("🏁", "#f1f5f9", "#000"),
            "BLUE":           ("🔵", "#3b82f6", "#fff"),
            "BLACK AND WHITE": ("⬛", "#94a3b8", "#000"),
            "":               ("📻", "#374151", "#fff"),
        }
        _rc = _rc.copy()
        _rc["Flag"] = _rc["Flag"].fillna("").str.upper()
        pills = ""
        for _, _row in _rc.iterrows():
            _flag = str(_row.get("Flag", "")).upper()
            _msg = str(_row.get("Message", ""))[:60]
            _icon, _bg, _fg = _RC_ICON.get(_flag, ("📻", "#374151", "#fff"))
            # Highlight safety car and red flag rows
            if "SAFETY CAR" in _msg.upper():
                _bg, _fg = "#f59e0b", "#000"
            elif "VIRTUAL SAFETY CAR" in _msg.upper():
                _bg, _fg = "#94a3b8", "#000"
            pills += (
                f'<span style="display:inline-block;background:{_bg};color:{_fg};'
                f'padding:3px 10px;border-radius:10px;font-size:11px;font-weight:600;'
                f'white-space:nowrap;margin-right:6px" title="{_msg}">'
                f'{_icon} {_msg}</span>'
            )
        st.html(
            f'<div style="overflow-x:auto;white-space:nowrap;padding:6px 2px 10px;'
            f'border-bottom:1px solid #2E2E42;margin-bottom:8px">'
            f'<span style="font-size:10px;color:#6B6B7B;letter-spacing:1.5px;'
            f'text-transform:uppercase;margin-right:12px;vertical-align:middle">Race Control</span>'
            f'{pills}</div>'
        )
except Exception:
    pass

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
