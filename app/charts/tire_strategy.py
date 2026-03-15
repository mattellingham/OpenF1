import streamlit as st
import plotly.graph_objects as go
from app.charts.base import F1Chart, ALL_SESSIONS
from app.data_loader import OpenF1Unavailable, fetch_stints, fetch_stints_live
from app.fastf1_fallback import get_stints_fastf1
from app.data_processor import process_stints

COMPOUND_COLORS = {
    "SOFT": "#e8002d",
    "MEDIUM": "#ffd700",
    "HARD": "#ebebeb",
    "INTERMEDIATE": "#39b54a",
    "WET": "#0067ff",
    "UNKNOWN": "#888888",
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

        fig = go.Figure()
        for _, row in stints_df.iterrows():
            compound = str(row["compound"]).upper()
            acronym = row["name_acronym"]
            fig.add_trace(go.Bar(
                x=[row["lap_count"]], y=[acronym],
                base=row["lap_start"], orientation="h",
                marker=dict(
                    color=COMPOUND_COLORS.get(compound, "#888"),
                    line=dict(color="rgba(0,0,0,0.3)", width=1),
                ),
                hovertemplate=(
                    f"<b>{acronym}</b><br>"
                    f"Compound: {compound}<br>"
                    f"Laps: {row['lap_start']}–{row['lap_end']} ({row['lap_count']} laps)"
                    "<extra></extra>"
                ),
                name="", showlegend=False,
            ))

        # Compound legend
        seen = stints_df["compound"].str.upper().unique()
        for compound in seen:
            fig.add_trace(go.Bar(
                x=[0], y=[""], name=compound,
                marker=dict(color=COMPOUND_COLORS.get(compound, "#888")),
                showlegend=True,
            ))

        # Coloured driver labels
        for acronym in stints_df["name_acronym"].unique():
            fig.add_annotation(
                x=-2, y=acronym, xref="x", yref="y",
                text=f"<b>{acronym}</b>", showarrow=False,
                font=dict(color=color_map.get(acronym, "#aaa"), size=11),
                align="right",
            )

        fig.update_layout(
            xaxis_title="Lap Number",
            barmode="stack", height=max(400, len(stints_df["name_acronym"].unique()) * 28),
            margin=dict(l=80, t=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig.update_yaxes(showticklabels=False)
        st.plotly_chart(fig, use_container_width=True)
        if source == "FastF1":
            st.caption("Data source: FastF1")
