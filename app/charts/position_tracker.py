import streamlit as st
import plotly.graph_objects as go
from app.charts.base import F1Chart, RACE_SESSIONS, PLOTLY_CONFIG
from app.fastf1_fallback import get_laps_fastf1
from app.data_loader import OpenF1Unavailable


class PositionTrackerChart(F1Chart):
    tab_label = "🏁 Race Position"
    session_types = RACE_SESSIONS
    unavailable_message = (
        "Race Position Tracker is only available for Race and Sprint sessions. "
        "Position data is not meaningful in practice or qualifying."
    )

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]
        driver_info = context["driver_info"]
        color_map = context["color_map"]
        selected_drivers = context["selected_drivers"]
        fastf1_mode = context["fastf1_mode"]

        # Position data comes from FastF1 laps regardless of mode,
        # as the local API position endpoint is high-frequency car position
        # data rather than race position.
        try:
            import fastf1
            from app.fastf1_fallback import _load_session, CACHE_DIR
            session = _load_session(year, country, session_type)
            laps = session.laps[["DriverNumber", "LapNumber", "Position"]].copy()
        except Exception as e:
            st.warning(f"Position data not available: {e}")
            return

        if laps.empty or "Position" not in laps.columns:
            st.warning("Position data not available for this session.")
            return

        laps = laps.rename(columns={"DriverNumber": "driver_number", "LapNumber": "lap_number"})
        laps["driver_number"] = laps["driver_number"].astype(str)
        laps = laps.merge(driver_info, on="driver_number", how="left")
        laps = laps[laps["name_acronym"].isin(selected_drivers)]
        laps = laps.dropna(subset=["Position"])

        if laps.empty:
            st.info("No position data for selected drivers.")
            return

        fig = go.Figure()
        for driver in laps["name_acronym"].unique():
            d = laps[laps["name_acronym"] == driver].sort_values("lap_number")
            fig.add_trace(go.Scatter(
                x=d["lap_number"], y=d["Position"],
                mode="lines+markers", name=driver,
                marker=dict(color=color_map.get(driver, "#888"), size=4),
                line=dict(color=color_map.get(driver, "#888"), width=2),
                hovertemplate=f"<b>{driver}</b><br>Lap %{{x}}<br>Position %{{y}}<extra></extra>",
            ))

        max_pos = int(laps["Position"].max())
        fig.update_layout(
            xaxis_title="Lap",
            yaxis=dict(
                title="Position",
                autorange="reversed",  # P1 at top
                tickmode="linear", tick0=1, dtick=1,
                range=[max_pos + 0.5, 0.5],
            ),
            hovermode="closest", height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=40),
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("Data source: FastF1")
