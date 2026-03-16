import streamlit as st
import plotly.express as px
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.data_loader import OpenF1Unavailable, fetch_pit_stop, fetch_pit_stop_live
from app.fastf1_fallback import get_pit_stops_fastf1
from app.data_processor import process_pit_stops


class PitStopsChart(F1Chart):
    tab_label = "⏱️ Pit Stops"
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
            pit_stop = get_pit_stops_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                fn = fetch_pit_stop_live if is_live else fetch_pit_stop
                pit_stop = fn(session_key)
                source = "Local"
            except OpenF1Unavailable:
                pit_stop = get_pit_stops_fastf1(year, country, session_type)
                source = "FastF1"

        pit_stop_df = process_pit_stops(pit_stop)
        if pit_stop_df.empty:
            st.warning("No pit stop data available for this session.")
            return

        pit_stop_df["driver_number"] = pit_stop_df["driver_number"].astype(str)
        pit_stop_df = pit_stop_df.merge(driver_info, on="driver_number", how="left")
        pit_stop_df = pit_stop_df[pit_stop_df["name_acronym"].isin(selected_drivers)]

        if pit_stop_df.empty:
            st.info("No data for selected drivers.")
            return

        fig = px.bar(
            pit_stop_df, x="lap_number", y="pit_duration",
            color="name_acronym", color_discrete_map=color_map,
            custom_data=["name_acronym", "driver_number", "lap_number", "pit_duration"],
            labels={"lap_number": "Lap", "pit_duration": "Pit duration (s)"},
        )
        fig.update_traces(
            hovertemplate=(
                "<b>%{customdata[0]}: %{customdata[1]}</b><br>"
                "Lap: %{customdata[2]}<br>"
                "Duration: %{customdata[3]:.2f}s<extra></extra>"
            )
        )
        fig.update_layout(
            hovermode="closest", barmode="group", height=450,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=40),
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        if source == "FastF1":
            st.caption("Data source: FastF1")
