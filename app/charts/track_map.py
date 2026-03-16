"""
Track Map chart.

Renders the circuit layout coloured by speed using individual line segments.
First load is slow (~30s as FastF1 downloads telemetry), cached afterwards.
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.fastf1_fallback import get_telemetry_fastf1


def _speed_to_color(speed: float, min_spd: float, max_spd: float) -> str:
    """Map a speed value to a hex colour on a red→yellow→green scale."""
    t = (speed - min_spd) / (max_spd - min_spd + 1e-9)
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        r, g = 232, int(t * 2 * 215)
        b = 0
    else:
        r, g = int((1 - (t - 0.5) * 2) * 232), 200
        b = 0
    return f"#{r:02x}{g:02x}{b:02x}"


class TrackMapChart(F1Chart):
    tab_label = "🗺️ Track Map"
    session_types = ALL_SESSIONS
    unavailable_message = "Track map data is not available for this session."

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]

        st.caption(
            "Circuit layout coloured by speed on the fastest lap. "
            "First load may take ~30s — cached afterwards."
        )

        tel = get_telemetry_fastf1(year, country, session_type)

        if tel is None or tel.empty:
            st.warning(
                "Track map telemetry not available for this session. "
                "The session may not have taken place yet, or telemetry "
                "data isn't available for this circuit."
            )
            return

        x = tel["X"].values.astype(float)
        y = tel["Y"].values.astype(float)
        speed = tel["Speed"].values.astype(float)

        # Remove any NaN rows
        mask = ~(np.isnan(x) | np.isnan(y) | np.isnan(speed))
        x, y, speed = x[mask], y[mask], speed[mask]

        if len(x) < 10:
            st.warning("Not enough telemetry points to render the track map.")
            return

        min_spd, max_spd = speed.min(), speed.max()

        # Downsample for performance — keep every N-th point
        step = max(1, len(x) // 600)
        x, y, speed = x[::step], y[::step], speed[::step]

        # Draw as individual short segments, each coloured by speed
        fig = go.Figure()

        # Add all segments in one batch using None separators (much faster than
        # adding thousands of individual traces)
        seg_x, seg_y, seg_colors = [], [], []
        for i in range(len(x) - 1):
            color = _speed_to_color(speed[i], min_spd, max_spd)
            seg_x += [x[i], x[i + 1], None]
            seg_y += [y[i], y[i + 1], None]
            seg_colors.append(color)

        # Plotly doesn't support per-segment colour on a single Scatter trace,
        # so we use a workaround: draw the full path as grey background,
        # then overlay coloured marker dots
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode="lines",
            line=dict(color="#333344", width=8),
            showlegend=False,
            hoverinfo="skip",
        ))

        # Coloured dots on top — provides the speed colour effect
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode="markers",
            marker=dict(
                color=speed,
                colorscale="RdYlGn",
                cmin=min_spd,
                cmax=max_spd,
                size=5,
                colorbar=dict(
                    title=dict(text="km/h", side="right"),
                    thickness=12,
                    len=0.75,
                    x=1.02,
                    tickfont=dict(size=9),
                ),
                showscale=True,
            ),
            showlegend=False,
            hovertemplate="Speed: %{marker.color:.0f} km/h<extra></extra>",
        ))

        # Start/finish marker
        fig.add_trace(go.Scatter(
            x=[x[0]], y=[y[0]],
            mode="markers+text",
            marker=dict(color="#E8002D", size=14, symbol="square",
                        line=dict(color="#fff", width=1)),
            text=["S/F"],
            textposition="top center",
            textfont=dict(size=10, color="#E8002D"),
            showlegend=False,
            hovertemplate="Start / Finish<extra></extra>",
        ))

        # Maintain aspect ratio
        x_range = x.max() - x.min()
        y_range = y.max() - y.min()
        aspect = y_range / x_range if x_range > 0 else 1
        height = max(350, min(580, int(480 * aspect)))

        fig.update_layout(
            height=height,
            xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
            yaxis=dict(visible=False),
            plot_bgcolor="rgba(10,10,20,1)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=10, b=10, l=10, r=60),
            hovermode="closest",
        )

        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption(
            f"{country} {year} {session_type} — fastest lap. "
            "Green = high speed, Red = low speed. Data source: FastF1"
        )
