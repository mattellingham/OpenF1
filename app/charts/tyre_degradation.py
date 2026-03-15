import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from app.charts.base import F1Chart, ALL_SESSIONS
from app.data_loader import OpenF1Unavailable, fetch_laps, fetch_stints
from app.fastf1_fallback import get_laps_fastf1, get_stints_fastf1
from app.data_processor import process_lap_data, process_stints

COMPOUND_COLORS = {
    "SOFT": "#e8002d",
    "MEDIUM": "#ffd700",
    "HARD": "#ebebeb",
    "INTERMEDIATE": "#39b54a",
    "WET": "#0067ff",
    "UNKNOWN": "#888888",
}


class TyreDegradationChart(F1Chart):
    tab_label = "📉 Tyre Deg"
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

        if fastf1_mode:
            lap_df = get_laps_fastf1(year, country, session_type)
            stints_raw = get_stints_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                lap_df = fetch_laps(session_key)
                stints_raw = fetch_stints(session_key)
                source = "Local"
            except OpenF1Unavailable:
                lap_df = get_laps_fastf1(year, country, session_type)
                stints_raw = get_stints_fastf1(year, country, session_type)
                source = "FastF1"

        laps = process_lap_data(lap_df)
        stints = process_stints(stints_raw)

        if laps.empty or stints.empty:
            st.warning("Not enough data to calculate tyre degradation.")
            return

        laps["driver_number"] = laps["driver_number"].astype(str)
        stints["driver_number"] = stints["driver_number"].astype(str)
        laps = laps.merge(driver_info, on="driver_number", how="left")
        stints = stints.merge(driver_info, on="driver_number", how="left")

        laps = laps[laps["name_acronym"].isin(selected_drivers)]
        stints = stints[stints["name_acronym"].isin(selected_drivers)]

        # Merge compound info onto each lap
        rows = []
        for _, stint in stints.iterrows():
            mask = (
                (laps["name_acronym"] == stint["name_acronym"]) &
                (laps["lap_number"] >= stint["lap_start"]) &
                (laps["lap_number"] <= stint["lap_end"])
            )
            stint_laps = laps[mask].copy()
            stint_laps["compound"] = stint["compound"]
            stint_laps["stint_lap"] = stint_laps["lap_number"] - stint["lap_start"] + 1
            rows.append(stint_laps)

        if not rows:
            st.warning("Could not match laps to stints.")
            return

        combined = pd.concat(rows, ignore_index=True)

        # Minimum 4 laps per stint to fit a meaningful trend
        min_laps = 4
        fig = go.Figure()
        legend_compounds = set()

        for (driver, compound), group in combined.groupby(["name_acronym", "compound"]):
            group = group.sort_values("stint_lap")
            if len(group) < min_laps:
                continue

            x = group["stint_lap"].values
            y = group["lap_duration"].values
            compound_upper = str(compound).upper()
            color = color_map.get(driver, "#888")
            comp_color = COMPOUND_COLORS.get(compound_upper, "#888")

            # Scatter points
            fig.add_trace(go.Scatter(
                x=x, y=y, mode="markers", name=driver,
                marker=dict(color=color, size=5, opacity=0.5),
                showlegend=False,
                hovertemplate=f"<b>{driver}</b> {compound}<br>Stint lap %{{x}}: %{{y:.3f}}s<extra></extra>",
            ))

            # Linear degradation trend line
            if len(x) >= 2:
                coeffs = np.polyfit(x, y, 1)
                trend_x = np.linspace(x.min(), x.max(), 50)
                trend_y = np.polyval(coeffs, trend_x)
                deg_per_lap = coeffs[0]

                show_legend = compound_upper not in legend_compounds
                legend_compounds.add(compound_upper)

                fig.add_trace(go.Scatter(
                    x=trend_x, y=trend_y,
                    mode="lines",
                    name=compound_upper,
                    line=dict(color=comp_color, width=2, dash="solid"),
                    showlegend=show_legend,
                    hovertemplate=(
                        f"<b>{driver} – {compound_upper}</b><br>"
                        f"Deg rate: {deg_per_lap:+.3f}s/lap<extra></extra>"
                    ),
                ))

        if not fig.data:
            st.warning("Not enough laps per stint to calculate degradation trends (minimum 4 laps required).")
            return

        fig.update_layout(
            xaxis_title="Laps into stint",
            yaxis_title="Lap Time (s)",
            height=500,
            hovermode="closest",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=40),
        )
        st.plotly_chart(fig, use_container_width=True)
        st.caption(
            "Trend lines show degradation rate (seconds per lap into stint). "
            "Steeper = faster deg. " + (f"Data source: {source}" if source == "FastF1" else "")
        )
