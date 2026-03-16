import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.data_loader import OpenF1Unavailable, fetch_laps, fetch_laps_live
from app.fastf1_fallback import get_laps_fastf1
from app.data_processor import process_lap_data


def _format_lap_time(seconds):
    minutes = int(seconds // 60)
    sec = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{minutes:02}:{sec:02}.{millis:03}"


def _format_mmss(seconds):
    return f"{int(seconds // 60):02}:{int(seconds % 60):02}"


class LapTimesChart(F1Chart):
    tab_label = "📈 Lap Times"
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
            lap_df = get_laps_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                fn = fetch_laps_live if is_live else fetch_laps
                lap_df = fn(session_key)
                source = "Local"
            except OpenF1Unavailable:
                lap_df = get_laps_fastf1(year, country, session_type)
                source = "FastF1"

        processed_df = process_lap_data(lap_df)
        if processed_df.empty:
            st.warning("No lap time data available for this session.")
            return

        processed_df["driver_number"] = processed_df["driver_number"].astype(str)
        processed_df = processed_df.merge(driver_info, on="driver_number", how="left")
        processed_df = processed_df[processed_df["name_acronym"].isin(selected_drivers)]

        if processed_df.empty:
            st.info("No data for selected drivers.")
            return

        processed_df["formatted_lap_time"] = processed_df["lap_duration"].apply(_format_lap_time)
        processed_df["is_pit_out_lap"] = processed_df["is_pit_out_lap"].fillna(False).astype(bool)

        fig = go.Figure()
        for driver in processed_df["name_acronym"].unique():
            d = processed_df[processed_df["name_acronym"] == driver].sort_values("lap_number")
            hover = [
                f"<b>{row['name_acronym']}</b><br>Lap {row['lap_number']}<br>{row['formatted_lap_time']}"
                + ("<br>🔧 PIT OUT" if row["is_pit_out_lap"] else "")
                for _, row in d.iterrows()
            ]
            fig.add_trace(go.Scatter(
                x=d["lap_number"], y=d["lap_duration"],
                mode="lines+markers", name=driver,
                marker=dict(color=color_map.get(driver, "#888")),
                line=dict(color=color_map.get(driver, "#888")),
                hoverinfo="text", hovertext=hover,
            ))

        tick_vals = sorted(processed_df["lap_duration"].dropna().unique())
        tick_vals = sorted(set([round(v, 0) for v in tick_vals if 60 <= v <= 300]))[::5]

        fig.update_layout(
            xaxis_title="Lap", yaxis_title="Lap Time",
            hovermode="closest", height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=40),
        )
        fig.update_yaxes(
            tickvals=tick_vals,
            ticktext=[_format_mmss(v) for v in tick_vals],
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        if source == "FastF1":
            st.caption("Data source: FastF1")
