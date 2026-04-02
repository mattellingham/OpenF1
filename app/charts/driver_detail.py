import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.data_loader import OpenF1Unavailable, fetch_laps, fetch_laps_live, fetch_stints, fetch_stints_live, fetch_pit_stop, fetch_pit_stop_live
from app.fastf1_fallback import get_laps_fastf1, get_stints_fastf1, get_pit_stops_fastf1
from app.data_processor import process_lap_data, process_stints, process_pit_stops

COMPOUND_COLORS = {
    "SOFT":         "#e8002d",
    "MEDIUM":       "#ffd700",
    "HARD":         "#ebebeb",
    "INTERMEDIATE": "#39b54a",
    "WET":          "#0067ff",
    "UNKNOWN":      "#888888",
}
COMPOUND_TEXT = {
    "SOFT": "#fff", "MEDIUM": "#000", "HARD": "#000",
    "INTERMEDIATE": "#fff", "WET": "#fff", "UNKNOWN": "#fff",
}
COMPOUND_ABBR = {
    "SOFT": "S", "MEDIUM": "M", "HARD": "H",
    "INTERMEDIATE": "I", "WET": "W", "UNKNOWN": "?",
}


def _fmt_time(secs) -> str:
    """Convert seconds float to M:SS.mmm string."""
    try:
        s = float(secs)
        m = int(s // 60)
        rem = s - m * 60
        return f"{m}:{rem:06.3f}"
    except Exception:
        return "—"


def _pit_color(duration) -> str:
    try:
        d = float(duration)
        if d < 22:
            return "#22c55e"
        if d < 26:
            return "#fbbf24"
        return "#ef4444"
    except Exception:
        return "#888888"


class DriverDetailChart(F1Chart):
    tab_label = "🧑‍✈️ Driver Detail"
    session_types = ALL_SESSIONS

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]
        driver_info = context["driver_info"]
        color_map = context["color_map"]
        selected_drivers = context["selected_drivers"]
        fastf1_mode = context["fastf1_mode"]
        session_key = context["session_key"]
        is_live = context["is_live"]

        # ── Load data ─────────────────────────────────────────────────────────
        if fastf1_mode:
            lap_df = get_laps_fastf1(year, country, session_type)
            stints_raw = get_stints_fastf1(year, country, session_type)
            pits_raw = get_pit_stops_fastf1(year, country, session_type)
        else:
            try:
                lap_fn = fetch_laps_live if is_live else fetch_laps
                stint_fn = fetch_stints_live if is_live else fetch_stints
                pit_fn = fetch_pit_stop_live if is_live else fetch_pit_stop
                lap_df = lap_fn(session_key)
                stints_raw = stint_fn(session_key)
                pits_raw = pit_fn(session_key)
            except OpenF1Unavailable:
                lap_df = get_laps_fastf1(year, country, session_type)
                stints_raw = get_stints_fastf1(year, country, session_type)
                pits_raw = get_pit_stops_fastf1(year, country, session_type)

        laps = process_lap_data(lap_df)
        stints = process_stints(stints_raw)
        pits = process_pit_stops(pits_raw)

        if laps.empty:
            st.warning("No lap data available.")
            return

        for df in (laps, stints, pits):
            if not df.empty:
                df["driver_number"] = df["driver_number"].astype(str)

        laps = laps.merge(driver_info, on="driver_number", how="left")
        if not stints.empty:
            stints = stints.merge(driver_info, on="driver_number", how="left")
        if not pits.empty:
            pits = pits.merge(driver_info, on="driver_number", how="left")

        for driver in selected_drivers:
            drv_color = color_map.get(driver, "#888")
            drv_laps = laps[laps["name_acronym"] == driver].sort_values("lap_number")
            drv_stints = stints[stints["name_acronym"] == driver] if not stints.empty else pd.DataFrame()
            drv_pits = pits[pits["name_acronym"] == driver] if not pits.empty else pd.DataFrame()

            with st.expander(
                f"**{driver}**  ·  {len(drv_laps)} laps  ·  "
                + (f"{len(drv_pits)} stop{'s' if len(drv_pits) != 1 else ''}" if not drv_pits.empty else "—"),
                expanded=False,
            ):
                # ── Lap time summary ─────────────────────────────────────────
                if not drv_laps.empty:
                    valid = drv_laps["lap_duration"].dropna()
                    best = valid.min()
                    avg = valid.mean()
                    last = drv_laps.iloc[-1]["lap_duration"]

                    st.html(
                        '<div style="display:flex;gap:16px;margin-bottom:12px">'
                        + _stat_card("Best Lap", _fmt_time(best), drv_color)
                        + _stat_card("Avg Lap", _fmt_time(avg), "#8E8EA8")
                        + _stat_card("Last Lap", _fmt_time(last), "#8E8EA8")
                        + '</div>'
                    )

                # ── Stint bar ────────────────────────────────────────────────
                if not drv_stints.empty:
                    st.markdown("**Stint summary**")
                    total_laps = int(drv_stints["lap_end"].max())
                    bar_html = '<div style="display:flex;width:100%;height:28px;border-radius:4px;overflow:hidden;margin-bottom:10px">'
                    for _, s in drv_stints.sort_values("lap_start").iterrows():
                        compound = str(s.get("compound", "UNKNOWN")).upper()
                        bg = COMPOUND_COLORS.get(compound, "#888")
                        fg = COMPOUND_TEXT.get(compound, "#fff")
                        abbr = COMPOUND_ABBR.get(compound, "?")
                        laps_on = int(s.get("lap_count", 0))
                        pct = (laps_on / total_laps * 100) if total_laps else 0
                        bar_html += (
                            f'<div style="width:{pct:.1f}%;background:{bg};display:flex;align-items:center;'
                            f'justify-content:center;font-size:10px;font-weight:700;color:{fg};'
                            f'white-space:nowrap;overflow:hidden" title="{compound} — {laps_on} laps">'
                            f'{abbr} {laps_on}</div>'
                        )
                    bar_html += '</div>'
                    st.html(bar_html)

                # ── Pit stop log ─────────────────────────────────────────────
                if not drv_pits.empty:
                    st.markdown("**Pit stops**")
                    stops_html = ""
                    for i, (_, p) in enumerate(drv_pits.sort_values("lap_number").iterrows(), 1):
                        dur = p.get("pit_duration", None)
                        dur_str = f"{float(dur):.1f}s" if pd.notna(dur) else "—"
                        dur_color = _pit_color(dur) if pd.notna(dur) else "#888"
                        stops_html += (
                            f'<tr>'
                            f'<td style="padding:4px 10px;color:#6B6B7B">Stop {i}</td>'
                            f'<td style="padding:4px 10px;color:#8E8EA8">Lap {int(p["lap_number"])}</td>'
                            f'<td style="padding:4px 10px;font-weight:700;color:{dur_color};'
                            f'font-variant-numeric:tabular-nums">{dur_str}</td>'
                            f'</tr>'
                        )
                    st.html(
                        '<style>.pit-tbl{border-collapse:collapse;font-size:12px}'
                        '.pit-tbl td{border-bottom:1px solid #1e1e2e}</style>'
                        '<table class="pit-tbl"><tbody>'
                        + stops_html +
                        '</tbody></table>'
                    )

                # ── Lap time sparkline ────────────────────────────────────────
                if not drv_laps.empty and len(drv_laps) >= 2:
                    best_lap_num = drv_laps.loc[drv_laps["lap_duration"].idxmin(), "lap_number"]
                    marker_colors = [
                        "#a855f7" if int(row["lap_number"]) == int(best_lap_num) else drv_color
                        for _, row in drv_laps.iterrows()
                    ]
                    marker_sizes = [
                        8 if int(row["lap_number"]) == int(best_lap_num) else 3
                        for _, row in drv_laps.iterrows()
                    ]
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=drv_laps["lap_number"],
                        y=drv_laps["lap_duration"],
                        mode="lines+markers",
                        line=dict(color=drv_color, width=1.5),
                        marker=dict(color=marker_colors, size=marker_sizes),
                        hovertemplate="Lap %{x}: %{y:.3f}s<extra></extra>",
                        showlegend=False,
                    ))
                    fig.update_layout(
                        height=180,
                        margin=dict(t=8, b=8, l=8, r=8),
                        xaxis_title=None,
                        yaxis_title=None,
                        xaxis=dict(showgrid=False),
                    )
                    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
                    st.caption("Lap times · purple = fastest lap")


def _stat_card(label: str, value: str, color: str) -> str:
    return (
        f'<div style="background:#1A1A2E;border-radius:8px;padding:10px 16px;min-width:100px">'
        f'<div style="font-size:10px;color:#6B6B7B;letter-spacing:1px;text-transform:uppercase;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:15px;font-weight:700;color:{color};font-variant-numeric:tabular-nums">{value}</div>'
        f'</div>'
    )
