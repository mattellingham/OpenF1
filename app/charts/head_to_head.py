import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.data_loader import OpenF1Unavailable, fetch_laps, fetch_laps_live
from app.fastf1_fallback import get_laps_fastf1
from app.data_processor import process_lap_data


class HeadToHeadChart(F1Chart):
    tab_label = "⚔️ Head to Head"
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

        if len(selected_drivers) < 2:
            st.info("Select at least two drivers above to use Head to Head comparison.")
            return

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
            st.warning("No lap data available.")
            return

        processed_df["driver_number"] = processed_df["driver_number"].astype(str)
        processed_df = processed_df.merge(driver_info, on="driver_number", how="left")
        processed_df = processed_df[processed_df["name_acronym"].isin(selected_drivers)]

        # Use the fastest driver across all laps as the baseline
        median_times = processed_df.groupby("name_acronym")["lap_duration"].median()
        baseline_driver = median_times.idxmin()

        baseline = processed_df[processed_df["name_acronym"] == baseline_driver][
            ["lap_number", "lap_duration"]
        ].rename(columns={"lap_duration": "baseline_time"})

        st.markdown(f"**Baseline:** {baseline_driver} (fastest median lap time)")

        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            subplot_titles=("Lap Times", f"Delta to {baseline_driver} (seconds)"),
            vertical_spacing=0.12,
            row_heights=[0.6, 0.4],
        )

        for driver in selected_drivers:
            d = processed_df[processed_df["name_acronym"] == driver].sort_values("lap_number")
            color = color_map.get(driver, "#888")

            # Top: raw lap times
            fig.add_trace(go.Scatter(
                x=d["lap_number"], y=d["lap_duration"],
                mode="lines+markers", name=driver,
                marker=dict(color=color, size=4),
                line=dict(color=color),
                hovertemplate=f"<b>{driver}</b> Lap %{{x}}: %{{y:.3f}}s<extra></extra>",
            ), row=1, col=1)

            # Bottom: delta to baseline
            merged = d.merge(baseline, on="lap_number", how="inner")
            merged["delta"] = merged["lap_duration"] - merged["baseline_time"]

            if driver != baseline_driver:
                fig.add_trace(go.Scatter(
                    x=merged["lap_number"], y=merged["delta"],
                    mode="lines+markers", name=driver,
                    marker=dict(color=color, size=4),
                    line=dict(color=color),
                    showlegend=False,
                    hovertemplate=f"<b>{driver}</b> Lap %{{x}}: %{{y:+.3f}}s<extra></extra>",
                ), row=2, col=1)

        # Zero line on delta chart
        fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=2, col=1)

        fig.update_layout(
            height=600,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.05, xanchor="left", x=0),
            margin=dict(t=60),
        )
        fig.update_xaxes(title_text="Lap", row=2, col=1)
        fig.update_yaxes(title_text="Lap Time (s)", row=1, col=1)
        fig.update_yaxes(title_text="Delta (s)", row=2, col=1)

        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        if source == "FastF1":
            st.caption("Data source: FastF1")
