"""
Schedule & Results page.

Season calendar on the left, full race/qualifying results on the right.
Clicking a completed round loads its results.
"""

import streamlit as st
from datetime import datetime, timezone
from app.jolpica import (
    get_schedule,
    get_race_results,
    get_qualifying_results,
    team_color,
    country_flag,
)


def _fmt_date(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%-d %b")
    except Exception:
        return date_str


def _pos_badge(pos: int) -> str:
    colors = {1: ("#C8A000", "#000"), 2: ("#8A8A8A", "#000"), 3: ("#7A4A1A", "#fff")}
    bg, fg = colors.get(pos, ("#252538", "#aaa"))
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:22px;height:22px;border-radius:4px;font-size:11px;font-weight:700;'
        f'background:{bg};color:{fg}">{pos}</span>'
    )


def _render_race_results(race: dict):
    results = race.get("Results", [])
    if not results:
        st.warning("No results available.")
        return

    flag = country_flag(race.get("Circuit", {}).get("Location", {}).get("country", ""))
    st.markdown(
        f"**{flag} {race['raceName']}** "
        f"<span style='color:#888;font-size:0.85em'>{_fmt_date(race['date'])}</span>",
        unsafe_allow_html=True,
    )

    rows = []
    for x in results:
        pos = int(x.get("position", 99))
        driver = x.get("Driver", {})
        constructor = x.get("Constructor", {})
        fl = x.get("FastestLap", {}).get("rank") == "1"
        color = team_color(constructor.get("constructorId", ""))
        time_status = x.get("Time", {}).get("time") or x.get("status", "—")
        rows.append({
            "pos": pos,
            "pos_badge": _pos_badge(pos),
            "name": driver.get("familyName", ""),
            "first": driver.get("givenName", ""),
            "team": constructor.get("name", ""),
            "color": color,
            "laps": x.get("laps", "—"),
            "time": time_status + (" 🟣" if fl else ""),
            "pts": x.get("points", "0"),
            "fl": fl,
        })

    # Build HTML table matching the pitwall style
    html = """
    <style>
    .res-tbl {width:100%;border-collapse:collapse;font-size:12px;}
    .res-tbl th {font-size:10px;letter-spacing:1px;text-transform:uppercase;
                 color:#6B6B7B;padding:6px 8px;text-align:left;
                 border-bottom:1px solid #2E2E42;}
    .res-tbl td {padding:6px 8px;border-bottom:1px solid #1e1e2e;}
    .res-tbl tr:hover td {background:#252538;}
    .res-tbl tr.fl-row td {background:rgba(192,96,200,0.08);}
    .team-bar {display:inline-block;width:3px;height:16px;border-radius:2px;
               margin-right:6px;vertical-align:middle;}
    .fl-badge {background:rgba(192,96,200,0.2);color:#C060C8;border:1px solid #C060C8;
               padding:1px 4px;border-radius:3px;font-size:9px;font-weight:700;margin-left:4px;}
    .pts {font-weight:700;color:#E8002D;}
    </style>
    <table class="res-tbl">
    <thead><tr>
      <th>P</th><th>Driver</th><th>Team</th><th>Laps</th><th>Time / Status</th><th>Pts</th>
    </tr></thead><tbody>
    """
    for r in rows:
        fl_class = "fl-row" if r["fl"] else ""
        fl_badge = '<span class="fl-badge">FL</span>' if r["fl"] else ""
        html += f"""
        <tr class="{fl_class}">
          <td>{r['pos_badge']}</td>
          <td>
            <span class="team-bar" style="background:{r['color']}"></span>
            <strong>{r['name']}</strong>{fl_badge}
          </td>
          <td style="color:#6B6B7B">{r['team']}</td>
          <td style="color:#6B6B7B">{r['laps']}</td>
          <td style="font-variant-numeric:tabular-nums">{r['time']}</td>
          <td class="pts">{r['pts']}</td>
        </tr>"""
    html += "</tbody></table>"
    st.html(html)


def _render_qualifying_results(race: dict):
    results = race.get("QualifyingResults", [])
    if not results:
        st.warning("No qualifying results available.")
        return

    flag = country_flag(race.get("Circuit", {}).get("Location", {}).get("country", ""))
    st.markdown(
        f"**{flag} {race['raceName']} – Qualifying** "
        f"<span style='color:#888;font-size:0.85em'>{_fmt_date(race['date'])}</span>",
        unsafe_allow_html=True,
    )

    html = """
    <style>
    .res-tbl {width:100%;border-collapse:collapse;font-size:12px;}
    .res-tbl th {font-size:10px;letter-spacing:1px;text-transform:uppercase;
                 color:#6B6B7B;padding:6px 8px;text-align:left;
                 border-bottom:1px solid #2E2E42;}
    .res-tbl td {padding:6px 8px;border-bottom:1px solid #1e1e2e;}
    .res-tbl tr:hover td {background:#252538;}
    .team-bar {display:inline-block;width:3px;height:16px;border-radius:2px;
               margin-right:6px;vertical-align:middle;}
    </style>
    <table class="res-tbl">
    <thead><tr>
      <th>P</th><th>Driver</th><th>Team</th><th>Q1</th><th>Q2</th><th>Q3</th>
    </tr></thead><tbody>
    """
    for x in results:
        pos = int(x.get("position", 99))
        driver = x.get("Driver", {})
        constructor = x.get("Constructor", {})
        color = team_color(constructor.get("constructorId", ""))
        q1 = x.get("Q1", "—")
        q2 = x.get("Q2", "—")
        q3 = x.get("Q3", "—")
        html += f"""
        <tr>
          <td>{_pos_badge(pos)}</td>
          <td>
            <span class="team-bar" style="background:{color}"></span>
            <strong>{driver.get('familyName','')}</strong>
          </td>
          <td style="color:#6B6B7B">{constructor.get('name','')}</td>
          <td style="font-variant-numeric:tabular-nums;color:#aaa">{q1}</td>
          <td style="font-variant-numeric:tabular-nums;color:#aaa">{q2}</td>
          <td style="font-variant-numeric:tabular-nums;color:#aaa">{q3}</td>
        </tr>"""
    html += "</tbody></table>"
    st.html(html)


def render(year: int):
    races = get_schedule(year)
    if not races:
        st.error(f"Could not load the {year} calendar.")
        return

    now = datetime.now(timezone.utc)

    # Identify next and last race
    next_round = None
    last_round = None
    for r in races:
        date_str = r.get("date", "")
        time_str = r.get("time", "12:00:00Z")
        try:
            rd = datetime.fromisoformat(f"{date_str}T{time_str}".replace("Z", "+00:00"))
        except Exception:
            continue
        if rd > now and next_round is None:
            next_round = int(r.get("round") or r.get("Round") or 0)
        if rd <= now:
            last_round = int(r.get("round") or r.get("Round") or 0)

    # ── Layout ────────────────────────────────────────────────────────────────
    cal_col, res_col = st.columns([1, 1.4])

    with cal_col:
        st.markdown("#### 📅 Season Calendar")

        # Default selection: last completed race
        if "schedule_selected_round" not in st.session_state:
            st.session_state.schedule_selected_round = last_round

        for r in races:
            date_str = r.get("date", "")
            time_str = r.get("time", "12:00:00Z")
            try:
                rd = datetime.fromisoformat(f"{date_str}T{time_str}".replace("Z", "+00:00"))
                done = rd <= now
            except Exception:
                done = False

            rnum = int(r.get("round") or r.get("Round") or 0)
            flag = country_flag(r.get("Circuit", {}).get("Location", {}).get("country", ""))
            name = r.get("raceName", "")
            locality = r.get("Circuit", {}).get("Location", {}).get("locality", "")
            country = r.get("Circuit", {}).get("Location", {}).get("country", "")
            has_sprint = "Sprint" in r
            is_next = rnum == next_round
            is_sel = rnum == st.session_state.get("schedule_selected_round")

            # Style the row
            opacity = "1.0" if (is_sel or is_next or not done) else "0.45"
            border = "border-left:3px solid #E8002D;padding-left:9px;" if is_sel else "padding-left:12px;"
            bg = "background:rgba(232,0,45,0.06);border-radius:6px;" if is_sel else ""

            badges = ""
            if is_next:
                badges += '<span style="background:#E8002D;color:#fff;font-size:8px;font-weight:700;padding:1px 5px;border-radius:2px;margin-left:4px;letter-spacing:1px;">NEXT</span>'
            if has_sprint:
                badges += '<span style="color:#E8002D;font-size:9px;font-weight:700;margin-left:3px;">S</span>'

            row_html = f"""
            <div style="display:flex;align-items:center;gap:8px;padding:6px 4px;
                        opacity:{opacity};{border}{bg}margin-bottom:2px;">
              <span style="font-size:10px;color:#6B6B7B;min-width:20px;text-align:center">{rnum}</span>
              <span style="font-size:16px">{flag}</span>
              <div style="flex:1">
                <div style="font-weight:600;font-size:12px">{name}{badges}</div>
                <div style="font-size:10px;color:#6B6B7B">{locality}, {country}</div>
              </div>
              <div style="text-align:right;font-size:11px;color:#B8B8C8">{_fmt_date(date_str)}</div>
            </div>"""
            st.markdown(row_html, unsafe_allow_html=True)

            if done:
                if st.button(f"View results", key=f"res_{rnum}", use_container_width=False):
                    st.session_state.schedule_selected_round = rnum
                    st.session_state.schedule_result_type = "race"
                    st.rerun()

    with res_col:
        st.markdown("#### 🏆 Results")

        sel_round = st.session_state.get("schedule_selected_round")
        if sel_round is None:
            st.info("Select a completed race from the calendar to view results.")
            return

        result_type = st.pills(
            "Result type",
            ["Race", "Qualifying"],
            default="Race",
            key="schedule_result_type_pills",
        )

        if result_type == "Race":
            with st.spinner("Loading race results..."):
                race = get_race_results(year, sel_round)
            if race:
                _render_race_results(race)
            else:
                st.warning("Race results not yet available.")
        else:
            with st.spinner("Loading qualifying results..."):
                race = get_qualifying_results(year, sel_round)
            if race:
                _render_qualifying_results(race)
            else:
                st.warning("Qualifying results not yet available.")
