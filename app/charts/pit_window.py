import pandas as pd
import streamlit as st
from app.charts.base import F1Chart, RACE_SESSIONS
from app.fastf1_fallback import get_gaps_fastf1, get_pit_stops_fastf1
from app.data_loader import OpenF1Unavailable, fetch_intervals, fetch_intervals_live, fetch_pit_stop


class PitWindowChart(F1Chart):
    tab_label = "🪟 Pit Window"
    session_types = RACE_SESSIONS
    unavailable_message = "Pit window calculator is only available for Race and Sprint sessions."

    def render(self, context: dict) -> None:
        session_key = context["session_key"]
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]
        driver_info = context["driver_info"]
        color_map = context["color_map"]
        selected_drivers = context["selected_drivers"]
        fastf1_mode = context["fastf1_mode"]
        is_live = context["is_live"]

        # ── Inputs ────────────────────────────────────────────────────────────
        col_loss, col_laps = st.columns(2)
        with col_loss:
            avg_pit_loss = self._estimate_pit_loss(
                session_key, year, country, session_type, fastf1_mode
            )
            pit_loss = st.number_input(
                "Pit loss (seconds)",
                min_value=10.0, max_value=60.0,
                value=float(max(10.0, min(60.0, avg_pit_loss))), step=0.5,
                help="Time lost from pit-in to rejoining (including time in pit lane).",
            )
        with col_laps:
            total_laps = st.number_input(
                "Total race laps",
                min_value=1, max_value=100, value=60, step=1,
            )

        # ── Gap data ──────────────────────────────────────────────────────────
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
            st.warning("Gap data not available — cannot calculate pit window.")
            return

        gaps["driver_number"] = gaps["driver_number"].astype(str)
        gaps = gaps.merge(driver_info, on="driver_number", how="left")
        gaps = gaps[gaps["name_acronym"].isin(selected_drivers)].sort_values("position")

        current_lap = int(gaps["current_lap"].max()) if "current_lap" in gaps.columns else "?"
        laps_remaining = (total_laps - current_lap) if isinstance(current_lap, int) else "?"
        st.caption(f"Current lap: **{current_lap}** · Laps remaining: **{laps_remaining}**")

        # ── Projection table ──────────────────────────────────────────────────
        pos_to_gap = gaps.set_index("position")["gap_to_leader"].to_dict()
        pos_to_acronym = gaps.set_index("position")["name_acronym"].to_dict()

        rows = ""
        for _, r in gaps.iterrows():
            pos = int(r["position"])
            drv = r.get("name_acronym", "")
            drv_color = color_map.get(drv, "#888")
            gap_to_leader = float(r.get("gap_to_leader", 0))
            interval = float(r.get("interval", 0))
            car_ahead = pos_to_acronym.get(pos - 1, "—")
            car_ahead_color = color_map.get(car_ahead, "#888")

            # After pitting: car_ahead has 'pit_loss' more seconds of running
            # Net gap change = pit_loss - interval (positive = stay behind, negative = undercut)
            rejoin_gap = pit_loss - interval if pos > 1 else pit_loss
            rejoin_gap_to_leader = gap_to_leader + pit_loss

            if pos == 1:
                result_text = "—"
                result_color = "#6B6B7B"
            elif rejoin_gap <= 0:
                result_text = f"✓ AHEAD by {abs(rejoin_gap):.1f}s"
                result_color = "#22c55e"
            else:
                result_text = f"Behind by {rejoin_gap:.1f}s"
                result_color = "#ef4444"

            car_ahead_cell = (
                f'<span style="color:{car_ahead_color};font-weight:700">{car_ahead}</span>'
                if pos > 1 else '<span style="color:#6B6B7B">— LEADER —</span>'
            )

            rows += (
                f'<tr>'
                f'<td style="padding:6px 10px;color:#6B6B7B">{pos}</td>'
                f'<td style="padding:6px 10px">'
                f'  <span style="display:inline-block;width:3px;height:14px;background:{drv_color};'
                f'  border-radius:2px;margin-right:6px;vertical-align:middle"></span>'
                f'  <strong style="color:{drv_color}">{drv}</strong>'
                f'</td>'
                f'<td style="padding:6px 10px;font-variant-numeric:tabular-nums;color:#8E8EA8">'
                f'  {("+" + f"{interval:.3f}s") if pos > 1 else "LEADER"}</td>'
                f'<td style="padding:6px 10px">{car_ahead_cell}</td>'
                f'<td style="padding:6px 10px;font-weight:700;color:{result_color}">{result_text}</td>'
                f'</tr>'
            )

        st.html(
            '<style>.pw-tbl{width:100%;border-collapse:collapse;font-size:12px}'
            '.pw-tbl th{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
            'color:#6B6B7B;padding:6px 10px;text-align:left;border-bottom:1px solid #2E2E42}'
            '.pw-tbl td{border-bottom:1px solid #1e1e2e}'
            '.pw-tbl tr:hover td{background:#252538}</style>'
            '<table class="pw-tbl"><thead><tr>'
            '<th>P</th><th>Driver</th><th>Interval Ahead</th><th>Car Ahead</th><th>Rejoin vs Car Ahead</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )
        st.caption(
            f"Projection based on pit loss of **{pit_loss:.1f}s**. "
            "Positive = rejoin behind car ahead, ✓ = undercut succeeds."
        )

    def _estimate_pit_loss(self, session_key, year, country, session_type, fastf1_mode) -> float:
        """Return estimated total pit loss from actual stops, or 22s default.

        OpenF1 pit_duration = stationary box time only → add ~18s transit.
        FastF1 pit_duration = PitOutTime - PitInTime = full lane time already.
        In both cases we discard outliers (>60s stationary / >80s full) that
        indicate safety car pitstops or damaged-car stops.
        """
        try:
            if not fastf1_mode:
                pits = fetch_pit_stop(session_key)
                if not pits.empty and "pit_duration" in pits.columns:
                    durations = pits["pit_duration"].dropna()
                    durations = durations[durations < 60]  # discard outliers
                    if not durations.empty:
                        return round(float(durations.mean()) + 18, 1)
            else:
                pits = get_pit_stops_fastf1(year, country, session_type)
                if not pits.empty and "pit_duration" in pits.columns:
                    durations = pits["pit_duration"].dropna()
                    durations = durations[durations < 80]  # full lane already included
                    if not durations.empty:
                        return round(float(durations.mean()), 1)
        except Exception:
            pass
        return 22.0
