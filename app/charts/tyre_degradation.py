import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.data_loader import OpenF1Unavailable, fetch_laps, fetch_laps_live, fetch_stints, fetch_stints_live
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
                lap_fn = fetch_laps_live if is_live else fetch_laps
                stints_fn = fetch_stints_live if is_live else fetch_stints
                lap_df = lap_fn(session_key)
                stints_raw = stints_fn(session_key)
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
        # Project trend this many laps beyond the last data point
        projection_laps = 8

        fig = go.Figure()
        summary_rows = []

        for (driver, compound), group in combined.groupby(["name_acronym", "compound"]):
            group = group.sort_values("stint_lap")

            # Filter SC/VSC laps: remove laps >8% above the stint median
            median_time = group["lap_duration"].median()
            group = group[group["lap_duration"] <= median_time * 1.08]

            if len(group) < min_laps:
                continue

            x = group["stint_lap"].values
            y = group["lap_duration"].values
            compound_upper = str(compound).upper()
            color = color_map.get(driver, "#888")

            # Scatter — actual laps
            fig.add_trace(go.Scatter(
                x=x, y=y, mode="markers", name=driver,
                marker=dict(color=color, size=5, opacity=0.55),
                showlegend=False,
                hovertemplate=f"<b>{driver}</b> {compound}<br>Stint lap %{{x}}: %{{y:.3f}}s<extra></extra>",
            ))

            # Regression
            coeffs = np.polyfit(x, y, 1)
            deg_per_lap = coeffs[0]

            # Solid trend over actual data
            trend_x = np.linspace(x.min(), x.max(), 50)
            trend_y = np.polyval(coeffs, trend_x)
            fig.add_trace(go.Scatter(
                x=trend_x, y=trend_y, mode="lines",
                name=f"{driver} ({compound_upper})",
                line=dict(color=color, width=2),
                showlegend=True,
                hovertemplate=(
                    f"<b>{driver} – {compound_upper}</b><br>"
                    f"Deg: {deg_per_lap:+.3f}s/lap<extra></extra>"
                ),
            ))

            # Dashed projection forward
            proj_x = np.linspace(x.max(), x.max() + projection_laps, 20)
            proj_y = np.polyval(coeffs, proj_x)
            fig.add_trace(go.Scatter(
                x=proj_x, y=proj_y, mode="lines",
                line=dict(color=color, width=1.5, dash="dash"),
                showlegend=False,
                hovertemplate=(
                    f"<b>{driver} – {compound_upper} (projected)</b><br>"
                    f"Lap %{{x:.0f}}: %{{y:.3f}}s<extra></extra>"
                ),
            ))

            # Summary data
            base_time = float(np.polyval(coeffs, x.min()))
            laps_to_1s_loss = abs(1.0 / deg_per_lap) if deg_per_lap > 0.001 else None
            summary_rows.append({
                "Driver": driver,
                "Compound": compound_upper,
                "Deg (s/lap)": f"{deg_per_lap:+.3f}",
                "Laps to +1s": f"~{laps_to_1s_loss:.0f}" if laps_to_1s_loss else "Stable",
                "_deg": deg_per_lap,
                "_color": color,
            })

        if not fig.data:
            st.warning("Not enough laps per stint to calculate degradation trends (minimum 4 laps required).")
            return

        fig.update_layout(
            xaxis_title="Laps into stint",
            yaxis_title="Lap Time (s)",
            height=500,
            hovermode="closest",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=40),
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption(
            "Solid line = measured trend · Dashed = projection. "
            "SC/VSC laps excluded (>8% above stint median). "
            + (f"Data source: {source}" if source == "FastF1" else "")
        )

        # ── Degradation summary table ─────────────────────────────────────────
        if summary_rows:
            st.divider()
            st.markdown("#### Degradation Summary")
            rows_html = ""
            for r in sorted(summary_rows, key=lambda x: x["_deg"], reverse=True):
                color = r["_color"]
                deg_val = r["_deg"]
                deg_color = "#ef4444" if deg_val > 0.05 else "#fbbf24" if deg_val > 0.02 else "#22c55e"
                rows_html += (
                    f'<tr>'
                    f'<td style="padding:5px 10px">'
                    f'  <span style="display:inline-block;width:3px;height:14px;background:{color};'
                    f'  border-radius:2px;margin-right:6px;vertical-align:middle"></span>'
                    f'  <strong style="color:{color}">{r["Driver"]}</strong>'
                    f'</td>'
                    f'<td style="padding:5px 10px;color:#8E8EA8">{r["Compound"]}</td>'
                    f'<td style="padding:5px 10px;font-weight:700;color:{deg_color};'
                    f'font-variant-numeric:tabular-nums">{r["Deg (s/lap)"]}</td>'
                    f'<td style="padding:5px 10px;color:#8E8EA8">{r["Laps to +1s"]}</td>'
                    f'</tr>'
                )
            st.html(
                '<style>.deg-tbl{width:100%;border-collapse:collapse;font-size:12px}'
                '.deg-tbl th{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
                'color:#6B6B7B;padding:6px 10px;text-align:left;border-bottom:1px solid #2E2E42}'
                '.deg-tbl td{border-bottom:1px solid #1e1e2e}'
                '.deg-tbl tr:hover td{background:#252538}</style>'
                '<table class="deg-tbl"><thead><tr>'
                '<th>Driver</th><th>Compound</th><th>Deg Rate</th><th>Laps to +1s</th>'
                f'</tr></thead><tbody>{rows_html}</tbody></table>'
            )
