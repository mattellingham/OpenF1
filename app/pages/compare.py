"""
Session Comparison page.

Two independent session selectors; renders:
  1. Lap time overlay — fastest driver from each session on one chart
  2. Sector times table — best S1/S2/S3 per session with Δ column
  3. Stint bars — stacked side by side per session
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from app.charts.base import PLOTLY_CONFIG
from app.data_processor import build_driver_color_map
from app.fastf1_fallback import (
    get_laps_fastf1,
    get_stints_fastf1,
    get_sectors_fastf1,
    get_meetings_fastf1,
    get_sessions_fastf1,
)

_AVAILABLE_YEARS = list(range(2023, 2027))

_COMPOUND_COLORS = {
    "SOFT": "#e8002d", "MEDIUM": "#ffd700", "HARD": "#ebebeb",
    "INTERMEDIATE": "#39b54a", "WET": "#0067ff", "UNKNOWN": "#888888",
}
_COMPOUND_TEXT = {
    "SOFT": "#fff", "MEDIUM": "#000", "HARD": "#000",
    "INTERMEDIATE": "#fff", "WET": "#fff", "UNKNOWN": "#fff",
}
_COMPOUND_ABBR = {
    "SOFT": "S", "MEDIUM": "M", "HARD": "H",
    "INTERMEDIATE": "I", "WET": "W", "UNKNOWN": "?",
}


def _session_selector(prefix: str, label: str) -> tuple[int, str, str] | None:
    """Render year/country/session selectors and return (year, country, session_type)."""
    st.markdown(f"**{label}**")
    col_y, col_c, col_s = st.columns(3)

    with col_y:
        year = st.selectbox("Year", _AVAILABLE_YEARS,
                            index=len(_AVAILABLE_YEARS) - 1, key=f"{prefix}_year")
    meetings = get_meetings_fastf1(year)
    if meetings.empty:
        st.warning("No calendar data.")
        return None

    countries = sorted(meetings["country_name"].dropna().unique())
    with col_c:
        country = st.selectbox("Country", countries, key=f"{prefix}_country")

    sessions = get_sessions_fastf1(year, country)
    if sessions.empty:
        st.warning("No session data.")
        return None

    with col_s:
        session_label = st.selectbox("Session", sessions["label"], key=f"{prefix}_session")

    session_type = sessions.loc[sessions["label"] == session_label, "session_type"].values[0]
    return year, country, session_type


def _load_session(year: int, country: str, session_type: str) -> dict:
    """Load laps, stints, sectors for one session. Returns dict of DataFrames."""
    laps = get_laps_fastf1(year, country, session_type)
    stints = get_stints_fastf1(year, country, session_type)
    sectors = get_sectors_fastf1(year, country, session_type)
    return {"laps": laps, "stints": stints, "sectors": sectors,
            "year": year, "country": country, "session_type": session_type}


def _lap_time_overlay(sess_a: dict, sess_b: dict) -> None:
    st.markdown("#### Lap Times")

    fig = go.Figure()
    styles = [dict(width=2, dash="solid"), dict(width=2, dash="dash")]
    colors = ["#E8002D", "#0067FF"]

    for sess, style, color in zip([sess_a, sess_b], styles, colors):
        laps = sess["laps"]
        if laps.empty or "lap_duration" not in laps.columns:
            continue
        laps = laps[laps["lap_duration"].notna()].copy()
        laps["driver_number"] = laps["driver_number"].astype(str)

        # Fastest driver overall
        best_drv = (
            laps.groupby("driver_number")["lap_duration"].median().idxmin()
        )
        drv_laps = laps[laps["driver_number"] == best_drv].sort_values("lap_number")
        label = f"{sess['country']} {sess['year']} {sess['session_type']}"

        fig.add_trace(go.Scatter(
            x=drv_laps["lap_number"],
            y=drv_laps["lap_duration"],
            mode="lines+markers",
            name=label,
            line=style | {"color": color},
            marker=dict(color=color, size=3),
            hovertemplate=f"<b>{label}</b><br>Lap %{{x}}: %{{y:.3f}}s<extra></extra>",
        ))

    fig.update_layout(
        height=380,
        xaxis_title="Lap",
        yaxis_title="Lap Time (s)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=40),
    )
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    st.caption("Fastest driver from each session (by median lap time). Solid = Session A · Dashed = Session B")


def _sector_comparison(sess_a: dict, sess_b: dict) -> None:
    st.markdown("#### Best Sector Times")

    def _best_sectors(sectors: pd.DataFrame) -> dict | None:
        if sectors.empty:
            return None
        needed = {"duration_sector_1", "duration_sector_2", "duration_sector_3"}
        if not needed.issubset(sectors.columns):
            return None
        return {
            "S1": sectors["duration_sector_1"].dropna().min(),
            "S2": sectors["duration_sector_2"].dropna().min(),
            "S3": sectors["duration_sector_3"].dropna().min(),
        }

    def _fmt(v):
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return "—"
        s = float(v)
        return f"{int(s // 60)}:{s % 60:06.3f}" if s >= 60 else f"{s:.3f}s"

    best_a = _best_sectors(sess_a["sectors"])
    best_b = _best_sectors(sess_b["sectors"])

    label_a = f"{sess_a['country']} {sess_a['year']}"
    label_b = f"{sess_b['country']} {sess_b['year']}"

    if not best_a and not best_b:
        st.info("Sector time data not available for either session.")
        return

    rows = ""
    for sector in ["S1", "S2", "S3"]:
        va = best_a.get(sector) if best_a else None
        vb = best_b.get(sector) if best_b else None

        if va is not None and vb is not None:
            delta = vb - va
            delta_str = f"{delta:+.3f}s"
            delta_color = "#22c55e" if delta > 0 else "#ef4444"
            winner = "a" if va <= vb else "b"
        else:
            delta_str = "—"
            delta_color = "#8E8EA8"
            winner = None

        def _cell(v, is_winner):
            s = _fmt(v)
            weight = "font-weight:700" if is_winner else ""
            col = "#E8E8F0" if is_winner else "#8E8EA8"
            return f'<td style="padding:6px 12px;{weight};color:{col};font-variant-numeric:tabular-nums">{s}</td>'

        rows += (
            f'<tr>'
            f'<td style="padding:6px 12px;color:#6B6B7B;font-weight:700">{sector}</td>'
            + _cell(va, winner == "a")
            + _cell(vb, winner == "b")
            + f'<td style="padding:6px 12px;font-weight:700;color:{delta_color};'
            f'font-variant-numeric:tabular-nums">{delta_str}</td>'
            f'</tr>'
        )

    st.html(
        '<style>.cmp-tbl{border-collapse:collapse;font-size:12px;width:100%}'
        '.cmp-tbl th{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
        'color:#6B6B7B;padding:6px 12px;text-align:left;border-bottom:1px solid #2E2E42}'
        '.cmp-tbl td{border-bottom:1px solid #1e1e2e}'
        '</style>'
        '<table class="cmp-tbl"><thead><tr>'
        f'<th>Sector</th><th>{label_a}</th><th>{label_b}</th><th>Δ (B−A)</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
    )


def _stint_bars(sess: dict, label: str) -> None:
    stints = sess["stints"]
    laps = sess["laps"]
    if stints.empty or laps.empty:
        st.caption(f"{label} — no stint data.")
        return

    stints = stints.copy()
    stints["driver_number"] = stints["driver_number"].astype(str)
    laps = laps.copy()
    laps["driver_number"] = laps["driver_number"].astype(str)
    stints["compound"] = stints.get("compound", pd.Series("UNKNOWN", index=stints.index)).fillna("UNKNOWN")
    stints["lap_count"] = stints["lap_end"] - stints["lap_start"] + 1

    max_lap = int(laps["lap_number"].max()) if not laps.empty else int(stints["lap_end"].max())

    drivers = sorted(stints["driver_number"].unique())
    rows = ""
    for drv in drivers:
        drv_stints = stints[stints["driver_number"] == drv].sort_values("lap_start")
        bar = '<div style="display:flex;width:100%;height:20px;border-radius:3px;overflow:hidden">'
        for _, s in drv_stints.iterrows():
            cmp = str(s.get("compound", "UNKNOWN")).upper()
            bg = _COMPOUND_COLORS.get(cmp, "#888")
            fg = _COMPOUND_TEXT.get(cmp, "#fff")
            abbr = _COMPOUND_ABBR.get(cmp, "?")
            lc = int(s.get("lap_count", 0))
            pct = (lc / max_lap * 100) if max_lap else 0
            bar += (
                f'<div style="width:{pct:.1f}%;background:{bg};display:flex;align-items:center;'
                f'justify-content:center;font-size:9px;font-weight:700;color:{fg};'
                f'white-space:nowrap;overflow:hidden" title="{cmp} {lc}L">{abbr}</div>'
            )
        bar += '</div>'
        rows += (
            f'<tr>'
            f'<td style="padding:3px 8px;color:#8E8EA8;font-size:11px;white-space:nowrap">{drv}</td>'
            f'<td style="padding:3px 8px;width:100%">{bar}</td>'
            f'</tr>'
        )

    st.html(
        '<style>.sb-tbl{width:100%;border-collapse:collapse}'
        '.sb-tbl td{vertical-align:middle}</style>'
        f'<table class="sb-tbl"><tbody>{rows}</tbody></table>'
    )


def render(available_years: list[int]) -> None:
    global _AVAILABLE_YEARS
    _AVAILABLE_YEARS = available_years

    st.markdown("Compare two sessions side by side — lap times, sector bests, and tyre strategies.")
    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        sel_a = _session_selector("a", "Session A")
    with col_b:
        sel_b = _session_selector("b", "Session B")

    if not sel_a or not sel_b:
        return

    with st.spinner("Loading session data…"):
        sess_a = _load_session(*sel_a)
        sess_b = _load_session(*sel_b)

    if sess_a["laps"].empty and sess_b["laps"].empty:
        st.warning("No lap data available for either session.")
        return

    st.divider()
    _lap_time_overlay(sess_a, sess_b)

    st.divider()
    _sector_comparison(sess_a, sess_b)

    st.divider()
    st.markdown("#### Tyre Strategy")
    scol_a, scol_b = st.columns(2)
    with scol_a:
        label_a = f"{sel_a[1]} {sel_a[0]} {sel_a[2]}"
        st.caption(f"**{label_a}**")
        _stint_bars(sess_a, label_a)
    with scol_b:
        label_b = f"{sel_b[1]} {sel_b[0]} {sel_b[2]}"
        st.caption(f"**{label_b}**")
        _stint_bars(sess_b, label_b)
