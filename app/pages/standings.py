"""
Championship standings page.

Driver and constructor standings side by side, with bar chart visualisation
and points progression chart.
"""

import streamlit as st
import plotly.graph_objects as go
from app.jolpica import (
    get_driver_standings,
    get_constructor_standings,
    get_schedule,
    get_race_results,
    team_color,
    country_flag,
)
from app.charts.base import PLOTLY_CONFIG
from app.data_processor import pos_badge as _pos_badge


def _render_driver_standings(standings: list):
    if not standings:
        st.warning("Driver standings not available.")
        return

    max_pts = float(standings[0].get("points", 1) or 1)

    html = """
    <style>
    .std-tbl {width:100%;border-collapse:collapse;font-size:12px;}
    .std-tbl th {font-size:10px;letter-spacing:1px;text-transform:uppercase;
                 color:#6B6B7B;padding:6px 8px;text-align:left;
                 border-bottom:1px solid #2E2E42;}
    .std-tbl td {padding:5px 8px;border-bottom:1px solid #1e1e2e;}
    .std-tbl tr:hover td {background:#252538;}
    .team-bar {display:inline-block;width:3px;height:16px;border-radius:2px;
               margin-right:6px;vertical-align:middle;}
    .pts-bar-wrap {width:80px;height:6px;background:#1e1e2e;border-radius:3px;
                   display:inline-block;vertical-align:middle;margin-left:6px;}
    .pts-bar {height:100%;border-radius:3px;}
    .pts-val {font-weight:700;color:#E8002D;}
    </style>
    <table class="std-tbl">
    <thead><tr>
      <th>P</th><th>Driver</th><th>Team</th><th colspan="2">Points</th><th>Wins</th>
    </tr></thead><tbody>
    """
    for s in standings:
        pos = int(s.get("position", 99))
        driver = s.get("Driver", {})
        constructors = s.get("Constructors", [{}])
        constructor = constructors[-1] if constructors else {}
        pts = float(s.get("points", 0) or 0)
        wins = s.get("wins", "0")
        color = team_color(constructor.get("constructorId", ""))
        pct = int((pts / max_pts) * 100)

        html += f"""
        <tr>
          <td>{_pos_badge(pos)}</td>
          <td>
            <span class="team-bar" style="background:{color}"></span>
            <strong>{driver.get('familyName','')}</strong>
            <span style="color:#6B6B7B;font-size:10px;margin-left:3px">
              {driver.get('givenName','')[:1]}.
            </span>
          </td>
          <td style="color:#6B6B7B;font-size:11px">{constructor.get('name','')}</td>
          <td class="pts-val">{int(pts)}</td>
          <td>
            <div class="pts-bar-wrap">
              <div class="pts-bar" style="width:{pct}%;background:{color}"></div>
            </div>
          </td>
          <td style="color:#aaa">{wins}</td>
        </tr>"""
    html += "</tbody></table>"
    st.html(html)


def _render_constructor_standings(standings: list):
    if not standings:
        st.warning("Constructor standings not available.")
        return

    max_pts = float(standings[0].get("points", 1) or 1)

    html = """
    <style>
    .std-tbl {width:100%;border-collapse:collapse;font-size:12px;}
    .std-tbl th {font-size:10px;letter-spacing:1px;text-transform:uppercase;
                 color:#6B6B7B;padding:6px 8px;text-align:left;
                 border-bottom:1px solid #2E2E42;}
    .std-tbl td {padding:5px 8px;border-bottom:1px solid #1e1e2e;}
    .std-tbl tr:hover td {background:#252538;}
    .pts-val {font-weight:700;color:#E8002D;}
    </style>
    <table class="std-tbl">
    <thead><tr>
      <th>P</th><th>Constructor</th><th colspan="2">Points</th><th>Wins</th>
    </tr></thead><tbody>
    """
    for s in standings:
        pos = int(s.get("position", 99))
        constructor = s.get("Constructor", {})
        pts = float(s.get("points", 0) or 0)
        wins = s.get("wins", "0")
        color = team_color(constructor.get("constructorId", ""))
        pct = int((pts / max_pts) * 100)
        name = constructor.get("name", "")

        html += f"""
        <tr>
          <td>{_pos_badge(pos)}</td>
          <td>
            <span style="display:inline-block;width:3px;height:16px;border-radius:2px;
                         background:{color};margin-right:6px;vertical-align:middle"></span>
            <strong>{name}</strong>
          </td>
          <td class="pts-val">{int(pts)}</td>
          <td>
            <div style="width:100px;height:6px;background:#1e1e2e;border-radius:3px;
                        display:inline-block;vertical-align:middle;">
              <div style="width:{pct}%;height:100%;border-radius:3px;background:{color}"></div>
            </div>
          </td>
          <td style="color:#aaa">{wins}</td>
        </tr>"""
    html += "</tbody></table>"
    st.html(html)


def _render_points_progression(year: int, driver_standings: list):
    """Plot points progression across the season for the top 5 drivers."""
    st.markdown("#### Points Progression")

    races = get_schedule(year)
    if not races:
        st.info("No schedule data available for progression chart.")
        return

    # Get top 5 drivers from current standings
    top5 = [
        s.get("Driver", {}).get("driverId", "")
        for s in driver_standings[:5]
    ]
    driver_names = {
        s.get("Driver", {}).get("driverId", ""): s.get("Driver", {}).get("familyName", "")
        for s in driver_standings[:5]
    }
    driver_colors = {
        s.get("Driver", {}).get("driverId", ""): team_color(
            (s.get("Constructors") or [{}])[-1].get("constructorId", "")
        )
        for s in driver_standings[:5]
    }

    # Build cumulative points per driver per round
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    completed = []
    for r in races:
        try:
            rd = datetime.fromisoformat(
                f"{r['date']}T{r.get('time','12:00:00Z')}".replace("Z", "+00:00")
            )
            if rd <= now:
                completed.append(int(r["round"]))
        except Exception:
            pass

    if not completed:
        st.info("No completed races yet this season.")
        return

    # Cache-bust to avoid loading too many rounds on first render
    # Load max 10 most recent completed rounds
    rounds_to_load = completed[-10:]

    cumulative = {did: [] for did in top5}
    running = {did: 0.0 for did in top5}
    round_labels = []

    progress = st.progress(0, text="Loading race results for progression chart...")
    for i, rnd in enumerate(rounds_to_load):
        progress.progress((i + 1) / len(rounds_to_load), text=f"Loading round {rnd}...")
        race = get_race_results(year, rnd)
        if race:
            round_labels.append(f"R{rnd}")
            for res in race.get("Results", []):
                did = res.get("Driver", {}).get("driverId", "")
                if did in running:
                    running[did] += float(res.get("points", 0) or 0)
            for did in top5:
                cumulative[did].append(running[did])
    progress.empty()

    if not round_labels:
        st.info("Not enough data for progression chart yet.")
        return

    fig = go.Figure()
    for did in top5:
        if not cumulative[did]:
            continue
        fig.add_trace(go.Scatter(
            x=round_labels,
            y=cumulative[did],
            mode="lines+markers",
            name=driver_names.get(did, did),
            line=dict(color=driver_colors.get(did, "#888"), width=2),
            marker=dict(size=5),
            hovertemplate=f"<b>{driver_names.get(did,did)}</b><br>%{{x}}: %{{y:.0f}} pts<extra></extra>",
        ))

    fig.update_layout(
        height=350,
        hovermode="x unified",
        xaxis_title="Round",
        yaxis_title="Points",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    st.caption("Top 5 drivers only. Last 10 completed rounds shown.")


def render(year: int):
    with st.spinner("Loading standings..."):
        driver_standings = get_driver_standings(year)
        constructor_standings = get_constructor_standings(year)

    drv_col, con_col = st.columns(2)

    with drv_col:
        st.markdown("#### 🏎️ Driver Championship")
        _render_driver_standings(driver_standings)

    with con_col:
        st.markdown("#### 🏭 Constructor Championship")
        _render_constructor_standings(constructor_standings)

    st.divider()
    _render_points_progression(year, driver_standings)
