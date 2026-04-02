import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from app.charts.base import F1Chart, RACE_SESSIONS, PLOTLY_CONFIG
from app.fastf1_fallback import get_laps_fastf1, get_gaps_fastf1
from app.data_loader import OpenF1Unavailable, fetch_intervals, fetch_intervals_live


class PositionTrackerChart(F1Chart):
    tab_label = "🏁 Race Position"
    session_types = RACE_SESSIONS
    unavailable_message = (
        "Race Position Tracker is only available for Race and Sprint sessions. "
        "Position data is not meaningful in practice or qualifying."
    )

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]
        driver_info = context["driver_info"]
        color_map = context["color_map"]
        selected_drivers = context["selected_drivers"]
        fastf1_mode = context["fastf1_mode"]

        # Position data comes from FastF1 laps regardless of mode,
        # as the local API position endpoint is high-frequency car position
        # data rather than race position.
        try:
            import fastf1
            from app.fastf1_fallback import _load_session, CACHE_DIR
            session = _load_session(year, country, session_type)
            laps = session.laps[["DriverNumber", "LapNumber", "Position"]].copy()
        except Exception as e:
            st.warning(f"Position data not available: {e}")
            return

        if laps.empty or "Position" not in laps.columns:
            st.warning("Position data not available for this session.")
            return

        laps = laps.rename(columns={"DriverNumber": "driver_number", "LapNumber": "lap_number"})
        laps["driver_number"] = laps["driver_number"].astype(str)
        laps = laps.merge(driver_info, on="driver_number", how="left")
        laps = laps[laps["name_acronym"].isin(selected_drivers)]
        laps = laps.dropna(subset=["Position"])

        if laps.empty:
            st.info("No position data for selected drivers.")
            return

        fig = go.Figure()
        for driver in laps["name_acronym"].unique():
            d = laps[laps["name_acronym"] == driver].sort_values("lap_number")
            fig.add_trace(go.Scatter(
                x=d["lap_number"], y=d["Position"],
                mode="lines+markers", name=driver,
                marker=dict(color=color_map.get(driver, "#888"), size=4),
                line=dict(color=color_map.get(driver, "#888"), width=2),
                hovertemplate=f"<b>{driver}</b><br>Lap %{{x}}<br>Position %{{y}}<extra></extra>",
            ))

        max_pos = int(laps["Position"].max())
        fig.update_layout(
            xaxis_title="Lap",
            yaxis=dict(
                title="Position",
                autorange="reversed",  # P1 at top
                tickmode="linear", tick0=1, dtick=1,
                range=[max_pos + 0.5, 0.5],
            ),
            hovermode="closest", height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=40),
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("Data source: FastF1")

        # ── Gap & interval table (#28) ─────────────────────────────────────────
        st.divider()
        st.markdown("#### Gap & Intervals")
        self._render_gap_table(context, driver_info, color_map, selected_drivers)

    def _render_gap_table(self, context, driver_info, color_map, selected_drivers):
        fastf1_mode = context["fastf1_mode"]
        is_live = context["is_live"]
        session_key = context["session_key"]
        year = context["year"]
        country = context["country"]
        session_type = context["session_type"]

        gaps = pd.DataFrame()
        if not fastf1_mode:
            try:
                fn = fetch_intervals_live if is_live else fetch_intervals
                raw = fn(session_key)
                if not raw.empty and {"driver_number", "gap_to_leader", "interval_to_position_ahead"}.issubset(raw.columns):
                    latest = raw.sort_values("date").groupby("driver_number").last().reset_index()
                    gaps = latest[["driver_number", "gap_to_leader", "interval_to_position_ahead"]].rename(
                        columns={"interval_to_position_ahead": "interval"}
                    )
                    gaps["position"] = range(1, len(gaps) + 1)
            except Exception:
                pass

        if gaps.empty:
            gaps = get_gaps_fastf1(year, country, session_type)

        if gaps.empty:
            st.info("Gap data not available for this session.")
            return

        gaps["driver_number"] = gaps["driver_number"].astype(str)
        gaps = gaps.merge(driver_info, on="driver_number", how="left")
        gaps = gaps[gaps["name_acronym"].isin(selected_drivers)].sort_values("position")

        def _fmt_gap(v):
            try:
                f = float(v)
                if f <= 0:
                    return "— LEADER —"
                return f"+{f:.3f}s"
            except Exception:
                return str(v)

        rows = ""
        for _, r in gaps.iterrows():
            drv = r.get("name_acronym", "")
            color = color_map.get(drv, "#888")
            pos = int(r["position"]) if not pd.isna(r["position"]) else "—"
            gap = _fmt_gap(r.get("gap_to_leader", 0))
            intv = _fmt_gap(r.get("interval", 0))
            gap_color = "#8E8EA8" if gap == "— LEADER —" else "#E8E8F0"
            intv_color = "#8E8EA8" if intv == "— LEADER —" else "#E8E8F0"
            rows += (
                f'<tr>'
                f'<td style="padding:5px 10px;color:#6B6B7B">{pos}</td>'
                f'<td style="padding:5px 10px">'
                f'<span style="display:inline-block;width:3px;height:14px;background:{color};'
                f'border-radius:2px;margin-right:6px;vertical-align:middle"></span>'
                f'<strong style="color:{color}">{drv}</strong></td>'
                f'<td style="padding:5px 10px;color:{gap_color};font-variant-numeric:tabular-nums">{gap}</td>'
                f'<td style="padding:5px 10px;color:{intv_color};font-variant-numeric:tabular-nums">{intv}</td>'
                f'</tr>'
            )

        st.html(
            '<style>.gap-tbl{width:100%;border-collapse:collapse;font-size:12px}'
            '.gap-tbl th{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
            'color:#6B6B7B;padding:6px 10px;text-align:left;border-bottom:1px solid #2E2E42}'
            '.gap-tbl td{border-bottom:1px solid #1e1e2e}'
            '.gap-tbl tr:hover td{background:#252538}</style>'
            '<table class="gap-tbl"><thead><tr>'
            '<th>P</th><th>Driver</th><th>Gap to Leader</th><th>Interval</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )
