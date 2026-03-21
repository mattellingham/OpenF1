"""
Session Results chart.

Shows the finishing classification for the selected session —
race results with podium for Race/Sprint, or lap times classification
for Practice/Qualifying.
"""

import math
import streamlit as st
import plotly.graph_objects as go
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.fastf1_fallback import get_results_fastf1
from app.data_processor import pos_badge as _pos_badge_html


TYRE_COLORS = {
    "SOFT": "#E8002D", "MEDIUM": "#FFD700", "HARD": "#EBEBEB",
    "INTERMEDIATE": "#39B54A", "WET": "#0067FF",
}


class ResultsChart(F1Chart):
    tab_label = "🏆 Results"
    session_types = ALL_SESSIONS

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]
        color_map = context["color_map"]

        results = get_results_fastf1(year, country, session_type)

        if results is None or results.empty:
            st.warning(
                "Results not available for this session. "
                "The session may not have taken place yet, or data is unavailable."
            )
            return

        is_race = any(t in session_type for t in ["Race", "Sprint"])

        # ── Podium for Race/Sprint ────────────────────────────────────────────
        if is_race and len(results) >= 3:
            self._render_podium(results, color_map)
            st.divider()

        # ── Full results table ────────────────────────────────────────────────
        self._render_table(results, color_map, is_race)
        st.caption("Data source: FastF1")

    def _render_podium(self, results, color_map):
        top3 = results[results["Position"].isin([1, 2, 3])].sort_values("Position")
        if len(top3) < 3:
            return

        def driver_info(row):
            abbr = row.get("Abbreviation", "")
            team = row.get("TeamName", "")
            time = ""
            if hasattr(row.get("Time"), "total_seconds"):
                secs = row["Time"].total_seconds()
                h, remainder = divmod(int(secs), 3600)
                m, s = divmod(remainder, 60)
                time = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
            elif row.get("Status") and row["Status"] != "Finished":
                time = str(row["Status"])
            return abbr, team, time

        p1 = top3.iloc[0]
        p2 = top3.iloc[1]
        p3 = top3.iloc[2]

        col2, col1, col3 = st.columns([1, 1.2, 1])

        for col, row, label, height, border_color in [
            (col2, p2, "P2", 60, "#999"),
            (col1, p1, "P1", 80, "#FFD700"),
            (col3, p3, "P3", 48, "#7A4A1A"),
        ]:
            abbr, team, time = driver_info(row)
            drv_color = color_map.get(abbr, "#888")
            with col:
                st.markdown(
                    f"""<div style="text-align:center;margin-bottom:8px">
                      <div style="height:{height}px;background:linear-gradient(to top,#1e1e2e,#252538);
                                  border-top:3px solid {border_color};border-radius:5px 5px 0 0;
                                  display:flex;align-items:flex-end;justify-content:center;
                                  padding-bottom:6px;font-size:22px;font-weight:900;
                                  color:rgba(255,255,255,0.1)">{label}</div>
                      <div style="font-weight:700;font-size:14px;margin-top:6px;
                                  color:{drv_color}">{abbr}</div>
                      <div style="font-size:10px;color:#6B6B7B;margin-top:2px">{team}</div>
                      <div style="font-size:11px;color:#B8B8C8;margin-top:2px">{time}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

    def _render_table(self, results, color_map, is_race: bool):
        rows_html = []
        for _, row in results.iterrows():
            pos = row.get("Position", row.get("ClassifiedPosition", "—"))
            abbr = row.get("Abbreviation", "")
            full_name = row.get("FullName", abbr)
            team = row.get("TeamName", "")
            color = color_map.get(abbr, "#888")
            points = row.get("Points", "")
            status = row.get("Status", "")
            grid = row.get("GridPosition", "")

            if is_race:
                time_val = row.get("Time")
                if hasattr(time_val, "total_seconds"):
                    try:
                        secs = time_val.total_seconds()
                        if math.isnan(secs):
                            raise ValueError
                        h, remainder = divmod(int(secs), 3600)
                        m, s = divmod(remainder, 60)
                        time_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                    except (ValueError, OverflowError):
                        time_str = str(status) if status and status != "Finished" else "—"
                else:
                    time_str = str(status) if status and status != "Finished" else "—"
            else:
                # Practice/qualifying — show best lap time
                time_str = "—"
                for col in ["Q3", "Q2", "Q1", "BestLapTime"]:
                    v = row.get(col)
                    if v and str(v) not in ("NaT", "nan", "None", ""):
                        if hasattr(v, "total_seconds"):
                            try:
                                secs = v.total_seconds()
                                if math.isnan(secs):
                                    continue
                                m2, s2 = divmod(secs, 60)
                                time_str = f"{int(m2)}:{s2:06.3f}"
                            except (ValueError, OverflowError):
                                time_str = str(v)
                        else:
                            time_str = str(v)
                        break

            fl = row.get("FastestLap") == True or str(row.get("FastestLapRank", "")) == "1"
            fl_badge = '<span style="background:rgba(192,96,200,0.2);color:#C060C8;border:1px solid #C060C8;padding:1px 4px;border-radius:3px;font-size:9px;font-weight:700;margin-left:4px">FL</span>' if fl else ""
            fl_bg = "background:rgba(192,96,200,0.08);" if fl else ""

            pts_cell = f'<td style="font-weight:700;color:#E8002D">{int(points) if points else ""}</td>' if is_race else ""
            grid_cell = f'<td style="color:#6B6B7B">{int(grid) if grid else ""}</td>' if is_race else ""

            rows_html.append(f"""
            <tr style="{fl_bg}">
              <td>{_pos_badge_html(pos)}</td>
              <td>
                <span style="display:inline-block;width:3px;height:16px;border-radius:2px;
                             background:{color};margin-right:6px;vertical-align:middle"></span>
                <strong>{abbr}</strong>
                <span style="color:#6B6B7B;font-size:10px;margin-left:3px">{full_name}</span>
                {fl_badge}
              </td>
              <td style="color:#6B6B7B;font-size:11px">{team}</td>
              {grid_cell}
              <td style="font-variant-numeric:tabular-nums">{time_str}</td>
              {pts_cell}
            </tr>""")

        grid_header = "<th>Grid</th>" if is_race else ""
        pts_header = "<th>Pts</th>" if is_race else ""
        time_header = "Time / Status" if is_race else "Best Time"

        html = f"""
        <style>
        .res-tbl {{width:100%;border-collapse:collapse;font-size:12px;}}
        .res-tbl th {{font-size:10px;letter-spacing:1px;text-transform:uppercase;
                     color:#6B6B7B;padding:6px 8px;text-align:left;
                     border-bottom:1px solid #2E2E42;}}
        .res-tbl td {{padding:6px 8px;border-bottom:1px solid #1e1e2e;}}
        .res-tbl tr:hover td {{background:#252538;}}
        </style>
        <table class="res-tbl">
        <thead><tr>
          <th>P</th><th>Driver</th><th>Team</th>{grid_header}<th>{time_header}</th>{pts_header}
        </tr></thead><tbody>
        {"".join(rows_html)}
        </tbody></table>"""
        st.html(html)
