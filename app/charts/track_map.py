"""
Track Map chart.

Renders the circuit layout from FastF1 telemetry, coloured by speed.
For sessions with telemetry available — first load is slow (~30s),
subsequent loads return from cache instantly.
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.fastf1_fallback import get_telemetry_fastf1


class TrackMapChart(F1Chart):
    tab_label = "🗺️ Track Map"
    session_types = ALL_SESSIONS
    unavailable_message = "Track map data is not available for this session."

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]

        st.caption(
            "Track layout from fastest lap telemetry. "
            "First load may take ~30s — cached afterwards."
        )

        tel = get_telemetry_fastf1(year, country, session_type)

        if tel is None or tel.empty:
            st.warning(
                "Track map telemetry not available for this session. "
                "This may be because the session hasn't been completed yet, "
                "or telemetry data isn't available for this year/circuit."
            )
            return

        x = tel["X"].values
        y = tel["Y"].values
        speed = tel["Speed"].values

        # Smooth slightly to reduce GPS noise
        from scipy.ndimage import uniform_filter1d
        try:
            x = uniform_filter1d(x, size=5)
            y = uniform_filter1d(y, size=5)
        except ImportError:
            pass  # scipy not available, use raw coordinates

        # Normalise axes so the track fits nicely
        x_range = x.max() - x.min()
        y_range = y.max() - y.min()
        aspect = y_range / x_range if x_range > 0 else 1

        height = max(350, min(600, int(500 * aspect)))

        # Build coloured speed segments
        min_spd = speed.min()
        max_spd = speed.max()
        spd_range = max_spd - min_spd if max_spd > min_spd else 1

        fig = go.Figure()

        # Add speed-coloured trace using continuous colorscale
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode="lines",
            line=dict(
                color=speed,
                colorscale="RdYlGn",
                width=6,
                cmin=min_spd,
                cmax=max_spd,
            ),
            hovertemplate="Speed: %{text:.0f} km/h<extra></extra>",
            text=speed,
            showlegend=False,
        ))

        # Colour bar for speed
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(
                colorscale="RdYlGn",
                cmin=min_spd,
                cmax=max_spd,
                colorbar=dict(
                    title=dict(text="Speed (km/h)", side="right"),
                    thickness=12,
                    len=0.8,
                    x=1.02,
                ),
                color=[min_spd],
                showscale=True,
                size=1,
            ),
            showlegend=False,
            hoverinfo="skip",
        ))

        # Mark start/finish
        fig.add_trace(go.Scatter(
            x=[x[0]], y=[y[0]],
            mode="markers+text",
            marker=dict(color="#E8002D", size=12, symbol="square"),
            text=["S/F"],
            textposition="top center",
            textfont=dict(size=10, color="#E8002D"),
            showlegend=False,
            hovertemplate="Start / Finish<extra></extra>",
        ))

        fig.update_layout(
            height=height,
            xaxis=dict(
                visible=False,
                scaleanchor="y",
                scaleratio=1,
            ),
            yaxis=dict(visible=False),
            plot_bgcolor="rgba(10,10,20,1)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20, l=20, r=60),
            hovermode="closest",
        )

        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption(
            f"Fastest lap telemetry — {country} {year} {session_type}. "
            "Green = high speed, Red = low speed. Data source: FastF1"
        )
