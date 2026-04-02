import streamlit as st
import plotly.graph_objects as go
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.fastf1_fallback import get_speed_trap_fastf1


class SpeedTrapChart(F1Chart):
    tab_label = "⚡ Speed Trap"
    session_types = ALL_SESSIONS
    unavailable_message = "Speed trap data is not available for this session type."

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]
        driver_info = context["driver_info"]
        color_map = context["color_map"]
        selected_drivers = context["selected_drivers"]

        df = get_speed_trap_fastf1(year, country, session_type)

        if df.empty:
            st.warning("No speed trap data available for this session.")
            return

        df["driver_number"] = df["driver_number"].astype(str)
        df = df.merge(driver_info, on="driver_number", how="left")
        df = df[df["name_acronym"].isin(selected_drivers)]

        if df.empty:
            st.info("No data for selected drivers.")
            return

        df = df.sort_values("top_speed", ascending=True)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df["top_speed"],
            y=df["name_acronym"],
            orientation="h",
            marker=dict(
                color=[color_map.get(d, "#888") for d in df["name_acronym"]],
                line=dict(color="rgba(0,0,0,0.2)", width=1),
            ),
            hovertemplate="<b>%{y}</b><br>Top speed: %{x:.1f} km/h<extra></extra>",
        ))

        x_min = df["top_speed"].min() * 0.97

        fig.update_layout(
            xaxis=dict(title="Top Speed (km/h)", range=[x_min, df["top_speed"].max() * 1.01]),
            yaxis=dict(title=""),
            height=max(350, len(df) * 28 + 80),
            margin=dict(l=60, t=56, r=60, b=40),
        )

        # Annotate speed values at end of bars
        for _, row in df.iterrows():
            fig.add_annotation(
                x=row["top_speed"],
                y=row["name_acronym"],
                text=f"<b>{row['top_speed']:.1f}</b>",
                showarrow=False,
                xanchor="left",
                xshift=6,
                font=dict(size=11, color="#E8E8F0"),
            )

        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("Data source: FastF1 · Speed trap (DRS detection line)")
