import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.fastf1_fallback import get_weather_fastf1


class WeatherChart(F1Chart):
    tab_label = "🌤️ Weather"
    session_types = ALL_SESSIONS

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]

        weather = get_weather_fastf1(year, country, session_type)

        if weather is None or weather.empty:
            st.warning("No weather data available for this session.")
            return

        weather = weather.copy()
        weather["minutes"] = weather["Time"].dt.total_seconds() / 60

        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            subplot_titles=("Temperature (°C)", "Rainfall", "Wind Speed (km/h)"),
            vertical_spacing=0.08,
            row_heights=[0.45, 0.25, 0.30],
        )

        fig.add_trace(go.Scatter(
            x=weather["minutes"], y=weather["TrackTemp"],
            mode="lines", name="Track Temp",
            line=dict(color="#e8002d", width=2),
            hovertemplate="Track: %{y:.1f}°C<extra></extra>",
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=weather["minutes"], y=weather["AirTemp"],
            mode="lines", name="Air Temp",
            line=dict(color="#60a5fa", width=2),
            hovertemplate="Air: %{y:.1f}°C<extra></extra>",
        ), row=1, col=1)

        fig.add_trace(go.Bar(
            x=weather["minutes"], y=weather["Rainfall"].astype(float),
            name="Rainfall", marker_color="#3b82f6",
            hovertemplate="Rainfall: %{y}<extra></extra>",
        ), row=2, col=1)

        fig.add_trace(go.Scatter(
            x=weather["minutes"], y=weather["WindSpeed"],
            mode="lines", name="Wind Speed",
            line=dict(color="#a78bfa", width=1.5),
            fill="tozeroy", fillcolor="rgba(167,139,250,0.15)",
            hovertemplate="Wind: %{y:.1f} km/h<extra></extra>",
        ), row=3, col=1)

        fig.update_layout(
            height=550, hovermode="x unified",
            legend=dict(orientation="h", yanchor="top", y=-0.08, xanchor="left", x=0),
            margin=dict(t=80, r=20, b=60),
        )
        fig.update_xaxes(title_text="Session time (minutes)", row=3, col=1)
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption("Data source: FastF1")
