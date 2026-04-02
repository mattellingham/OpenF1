import streamlit as st
import plotly.graph_objects as go
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.data_loader import OpenF1Unavailable, fetch_stints, fetch_stints_live
from app.fastf1_fallback import get_stints_fastf1
from app.data_processor import process_stints

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


class TireStrategyChart(F1Chart):
    tab_label = "🛞 Tire Strategy"
    session_types = ALL_SESSIONS

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

        if fastf1_mode:
            stints = get_stints_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                fn = fetch_stints_live if is_live else fetch_stints
                stints = fn(session_key)
                source = "Local"
            except OpenF1Unavailable:
                stints = get_stints_fastf1(year, country, session_type)
                source = "FastF1"

        stints_df = process_stints(stints)
        if stints_df.empty:
            st.warning("No tire strategy data available.")
            return

        stints_df["driver_number"] = stints_df["driver_number"].astype(str)
        stints_df = stints_df.merge(driver_info, on="driver_number", how="left")
        stints_df = stints_df[stints_df["name_acronym"].isin(selected_drivers)]

        if stints_df.empty:
            st.info("No data for selected drivers.")
            return

        view = st.radio(
            "View",
            ["Compact bars", "Gantt chart"],
            horizontal=True,
            key="tire_strategy_view",
        )

        if view == "Compact bars":
            self._render_compact(stints_df, color_map)
            if source == "FastF1":
                st.caption("Data source: FastF1")
            return

        fig = go.Figure()
        seen_compounds = set()

        for _, row in stints_df.iterrows():
            compound = str(row["compound"]).upper()
            acronym = row["name_acronym"]
            comp_color = COMPOUND_COLORS.get(compound, "#888")
            first_of_compound = compound not in seen_compounds
            seen_compounds.add(compound)

            fig.add_trace(go.Bar(
                x=[row["lap_count"]],
                y=[acronym],
                base=row["lap_start"],
                orientation="h",
                name=compound,
                legendgroup=compound,
                showlegend=first_of_compound,
                marker=dict(
                    color=comp_color,
                    line=dict(color="rgba(0,0,0,0.3)", width=1),
                ),
                hovertemplate=(
                    f"<b>{acronym}</b><br>"
                    f"Compound: {compound}<br>"
                    f"Laps: {row['lap_start']}–{row['lap_end']} ({row['lap_count']} laps)"
                    "<extra></extra>"
                ),
            ))

        # Coloured driver labels
        for acronym in stints_df["name_acronym"].unique():
            fig.add_annotation(
                x=-2, y=acronym, xref="x", yref="y",
                text=f"<b>{acronym}</b>", showarrow=False,
                font=dict(color=color_map.get(acronym, "#aaa"), size=11),
                align="right",
            )

        num_drivers = len(stints_df["name_acronym"].unique())
        fig.update_layout(
            xaxis=dict(title="Lap Number", rangemode="tozero"),
            barmode="stack",
            height=max(400, num_drivers * 30 + 120),
            margin=dict(l=80, t=60, r=20, b=40),
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1.02,
                xanchor="left", x=0,
            ),
        )
        fig.update_yaxes(showticklabels=False)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        if source == "FastF1":
            st.caption("Data source: FastF1")

    def _render_compact(self, stints_df, color_map):
        """Horizontal stint bars — one row per driver, blocks proportional to stint length."""
        total_laps = int(stints_df["lap_end"].max())
        drivers = stints_df["name_acronym"].unique().tolist()

        rows_html = ""
        for driver in drivers:
            drv_color = color_map.get(driver, "#888")
            drv_stints = stints_df[stints_df["name_acronym"] == driver].sort_values("lap_start")
            blocks = ""
            for _, s in drv_stints.iterrows():
                compound = str(s["compound"]).upper()
                bg = COMPOUND_COLORS.get(compound, "#888")
                fg = COMPOUND_TEXT.get(compound, "#fff")
                abbr = COMPOUND_ABBR.get(compound, "?")
                laps = int(s["lap_count"])
                flex = max(laps, 1)
                blocks += (
                    f'<div style="flex:{flex};background:{bg};color:{fg};'
                    f'border-radius:3px;padding:3px 5px;font-size:10px;font-weight:700;'
                    f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;'
                    f'min-width:18px;text-align:center" title="{compound} · {laps} laps">'
                    f'{abbr} <span style="font-weight:400;opacity:0.85">{laps}</span></div>'
                )
            rows_html += (
                f'<tr>'
                f'<td style="padding:3px 10px 3px 0;font-size:11px;font-weight:700;'
                f'color:{drv_color};white-space:nowrap;vertical-align:middle">{driver}</td>'
                f'<td style="width:100%;padding:2px 0">'
                f'<div style="display:flex;gap:2px">{blocks}</div></td>'
                f'</tr>'
            )

        compound_legend = ""
        for name, bg in COMPOUND_COLORS.items():
            if name == "UNKNOWN":
                continue
            fg = COMPOUND_TEXT[name]
            abbr = COMPOUND_ABBR[name]
            compound_legend += (
                f'<span style="display:inline-flex;align-items:center;gap:4px;margin-right:10px">'
                f'<span style="background:{bg};color:{fg};font-size:10px;font-weight:700;'
                f'padding:1px 6px;border-radius:3px">{abbr}</span>'
                f'<span style="font-size:10px;color:#8E8EA8">{name.capitalize()}</span></span>'
            )

        st.html(
            f'<div style="overflow-x:auto">'
            f'<table style="width:100%;border-collapse:collapse">{rows_html}</table>'
            f'</div>'
            f'<div style="margin-top:10px">{compound_legend}</div>'
        )
