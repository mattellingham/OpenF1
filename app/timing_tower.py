"""
Live Timing Tower — shown above tabs during active sessions.

Columns: P · Driver · Gap · Interval · Tyre · Pits · Last Lap
Position changes are tracked in session_state and shown with ▲/▼ arrows.
Fastest lap highlighted in purple.
"""
import pandas as pd
import streamlit as st
from app.data_loader import (
    fetch_intervals_live, fetch_stints_live,
    fetch_laps_live, fetch_pit_stop_live,
)

_COMPOUND_COLORS = {
    "SOFT":         "#e8002d",
    "MEDIUM":       "#ffd700",
    "HARD":         "#ebebeb",
    "INTERMEDIATE": "#39b54a",
    "WET":          "#0067ff",
    "UNKNOWN":      "#888888",
}
_COMPOUND_TEXT = {
    "SOFT": "#fff", "MEDIUM": "#000", "HARD": "#000",
    "INTERMEDIATE": "#fff", "WET": "#fff", "UNKNOWN": "#fff",
}
_COMPOUND_ABBR = {
    "SOFT": "S", "MEDIUM": "M", "HARD": "H",
    "INTERMEDIATE": "I", "WET": "W", "UNKNOWN": "?",
}


def _fmt_gap(v) -> str:
    try:
        f = float(v)
        return "LEADER" if f <= 0 else f"+{f:.3f}s"
    except Exception:
        return str(v) if pd.notna(v) else "—"


def _fmt_laptime(secs) -> str:
    try:
        s = float(secs)
        m = int(s // 60)
        return f"{m}:{s - m * 60:06.3f}"
    except Exception:
        return "—"


def render_timing_tower(context: dict) -> None:
    session_key = context["session_key"]
    driver_info = context["driver_info"].copy()
    color_map = context["color_map"]

    # ── Fetch all live data ────────────────────────────────────────────────
    try:
        intervals_raw = fetch_intervals_live(session_key)
    except Exception:
        intervals_raw = pd.DataFrame()

    try:
        stints_raw = fetch_stints_live(session_key)
    except Exception:
        stints_raw = pd.DataFrame()

    try:
        laps_raw = fetch_laps_live(session_key)
    except Exception:
        laps_raw = pd.DataFrame()

    try:
        pits_raw = fetch_pit_stop_live(session_key)
    except Exception:
        pits_raw = pd.DataFrame()

    if intervals_raw.empty:
        st.info("Waiting for live timing data…")
        return

    # ── Latest interval snapshot per driver ───────────────────────────────
    intervals = (
        intervals_raw.sort_values("date")
        .groupby("driver_number").last()
        .reset_index()
    )
    intervals["driver_number"] = intervals["driver_number"].astype(str)

    # Sort by gap_to_leader (lapped cars get large value, leader = 0)
    def _gap_key(v):
        try:
            return float(v)
        except Exception:
            return 9999.0

    intervals["_gap_sort"] = intervals["gap_to_leader"].apply(_gap_key)
    intervals = intervals.sort_values("_gap_sort").reset_index(drop=True)
    intervals["position"] = range(1, len(intervals) + 1)

    # ── Pit counts ────────────────────────────────────────────────────────
    pit_counts: dict = {}
    if not pits_raw.empty and "driver_number" in pits_raw.columns:
        pits_raw["driver_number"] = pits_raw["driver_number"].astype(str)
        pit_counts = pits_raw.groupby("driver_number").size().to_dict()

    # ── Current stint per driver ──────────────────────────────────────────
    current_stints: dict = {}
    if not stints_raw.empty:
        stints_raw["driver_number"] = stints_raw["driver_number"].astype(str)
        for drv, grp in stints_raw.groupby("driver_number"):
            current_stints[str(drv)] = grp.loc[grp["lap_end"].idxmax()]

    # ── Latest & fastest lap ──────────────────────────────────────────────
    latest_laps: dict = {}
    fastest_lap_driver: str | None = None
    if not laps_raw.empty and "lap_duration" in laps_raw.columns:
        laps_raw["driver_number"] = laps_raw["driver_number"].astype(str)
        laps_raw = laps_raw[laps_raw["lap_duration"].notna()]
        for drv, grp in laps_raw.groupby("driver_number"):
            latest_laps[str(drv)] = grp.loc[grp["lap_number"].idxmax()]
        if not laps_raw.empty:
            fastest_lap_driver = str(
                laps_raw.loc[laps_raw["lap_duration"].idxmin(), "driver_number"]
            )

    # ── Position change tracking ──────────────────────────────────────────
    prev_positions: dict = st.session_state.get("_tt_prev_positions", {})
    new_positions = {
        str(row["driver_number"]): int(row["position"])
        for _, row in intervals.iterrows()
    }

    # ── Driver number → acronym map ───────────────────────────────────────
    driver_info["driver_number"] = driver_info["driver_number"].astype(str)
    drv_map = driver_info.set_index("driver_number")["name_acronym"].to_dict()

    # ── Build HTML rows ───────────────────────────────────────────────────
    rows = ""
    for _, r in intervals.iterrows():
        drv_num = str(r["driver_number"])
        drv = drv_map.get(drv_num, drv_num)
        pos = int(r["position"])
        color = color_map.get(drv, "#888")

        gap = _fmt_gap(r.get("gap_to_leader", 0))
        intv = _fmt_gap(r.get("interval_to_position_ahead", 0))
        gap_color = "#6B6B7B" if gap == "LEADER" else "#8E8EA8"
        intv_color = "#6B6B7B" if intv == "LEADER" else "#8E8EA8"

        # ▲/▼ position change
        prev_pos = prev_positions.get(drv_num)
        if prev_pos is not None and prev_pos != pos:
            arrow = (
                '<span style="color:#22c55e;font-size:9px;margin-left:3px">▲</span>'
                if prev_pos > pos else
                '<span style="color:#ef4444;font-size:9px;margin-left:3px">▼</span>'
            )
        else:
            arrow = ""

        # Tyre compound badge
        compound_cell = "—"
        if drv_num in current_stints:
            s = current_stints[drv_num]
            cmp = str(s.get("compound", "UNKNOWN")).upper()
            bg = _COMPOUND_COLORS.get(cmp, "#888")
            fg = _COMPOUND_TEXT.get(cmp, "#fff")
            abbr = _COMPOUND_ABBR.get(cmp, "?")
            lap_start = int(s.get("lap_start", 0))
            cur_lap = int(latest_laps[drv_num]["lap_number"]) if drv_num in latest_laps else 0
            laps_on = max(0, cur_lap - lap_start + 1)
            compound_cell = (
                f'<span style="background:{bg};color:{fg};padding:1px 5px;'
                f'border-radius:3px;font-size:10px;font-weight:700">{abbr}</span>'
                f'<span style="color:#6B6B7B;font-size:10px;margin-left:4px">{laps_on}L</span>'
            )

        # Pit count
        pits = pit_counts.get(drv_num, 0)

        # Last lap time (purple if overall fastest)
        last_lap_cell = "—"
        if drv_num in latest_laps:
            dur = latest_laps[drv_num].get("lap_duration")
            if pd.notna(dur):
                lap_color = "#a855f7" if drv_num == fastest_lap_driver else "#E8E8F0"
                fl_dot = (
                    '<span style="color:#a855f7;font-size:9px;margin-right:4px">●</span>'
                    if drv_num == fastest_lap_driver else ""
                )
                last_lap_cell = (
                    f'{fl_dot}<span style="color:{lap_color};'
                    f'font-variant-numeric:tabular-nums">{_fmt_laptime(dur)}</span>'
                )

        rows += (
            f'<tr>'
            f'<td style="padding:5px 10px;color:#6B6B7B">{pos}{arrow}</td>'
            f'<td style="padding:5px 10px">'
            f'  <span style="display:inline-block;width:3px;height:14px;background:{color};'
            f'  border-radius:2px;margin-right:6px;vertical-align:middle"></span>'
            f'  <strong style="color:{color}">{drv}</strong></td>'
            f'<td style="padding:5px 10px;color:{gap_color};'
            f'font-variant-numeric:tabular-nums">{gap}</td>'
            f'<td style="padding:5px 10px;color:{intv_color};'
            f'font-variant-numeric:tabular-nums">{intv}</td>'
            f'<td style="padding:5px 10px">{compound_cell}</td>'
            f'<td style="padding:5px 10px;color:#8E8EA8;text-align:center">{pits}</td>'
            f'<td style="padding:5px 10px">{last_lap_cell}</td>'
            f'</tr>'
        )

    st.html(
        '<style>'
        '.tt-tbl{width:100%;border-collapse:collapse;font-size:12px}'
        '.tt-tbl th{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
        'color:#6B6B7B;padding:5px 10px;text-align:left;border-bottom:1px solid #2E2E42}'
        '.tt-tbl td{border-bottom:1px solid #1e1e2e}'
        '.tt-tbl tr:hover td{background:#252538}'
        '</style>'
        '<table class="tt-tbl"><thead><tr>'
        '<th>P</th><th>Driver</th><th>Gap</th><th>Interval</th>'
        '<th>Tyre</th><th>Pits</th><th>Last Lap</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
    )

    # Persist positions for next refresh cycle
    st.session_state["_tt_prev_positions"] = new_positions
