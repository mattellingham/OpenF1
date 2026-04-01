import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from app.charts.base import F1Chart, ALL_SESSIONS, PLOTLY_CONFIG
from app.data_loader import OpenF1Unavailable, fetch_laps, fetch_laps_live
from app.fastf1_fallback import get_sectors_fastf1


def _fmt_sector(seconds: float) -> str:
    return f"{seconds:.3f}s"


class SectorTimesChart(F1Chart):
    tab_label = "⏱️ Sector Times"
    session_types = ALL_SESSIONS
    unavailable_message = "Sector time data is not available for this session type."

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
            df = get_sectors_fastf1(year, country, session_type)
            source = "FastF1"
        else:
            try:
                fn = fetch_laps_live if is_live else fetch_laps
                raw = fn(session_key)
                df = _extract_sectors_local(raw)
                source = "Local"
                if df.empty:
                    raise OpenF1Unavailable("No sector data in local API response")
            except OpenF1Unavailable:
                df = get_sectors_fastf1(year, country, session_type)
                source = "FastF1"

        if df.empty:
            st.warning("No sector time data available for this session.")
            return

        df["driver_number"] = df["driver_number"].astype(str)
        df = df.merge(driver_info, on="driver_number", how="left")
        df = df[df["name_acronym"].isin(selected_drivers)]

        if df.empty:
            st.info("No data for selected drivers.")
            return

        # Best sector per driver
        best = (
            df.groupby("name_acronym", as_index=False)
            .agg(
                s1=("sector_1", "min"),
                s2=("sector_2", "min"),
                s3=("sector_3", "min"),
            )
        )
        best["best_lap"] = best["s1"] + best["s2"] + best["s3"]
        best = best.sort_values("best_lap")

        # Toggle: best per sector vs. same lap
        view = st.radio(
            "Show",
            ["Best sector (independent)", "Best lap sectors (same lap)"],
            horizontal=True,
            key="sector_view",
        )

        if view == "Best lap sectors (same lap)":
            df["lap_total"] = df["sector_1"] + df["sector_2"] + df["sector_3"]
            idx = df.groupby("name_acronym")["lap_total"].idxmin()
            plot_df = df.loc[idx].set_index("name_acronym")
            plot_df = plot_df.loc[plot_df.index.isin(best["name_acronym"])]
            plot_df = plot_df.reindex(best["name_acronym"])
            s1_vals = plot_df["sector_1"].tolist()
            s2_vals = plot_df["sector_2"].tolist()
            s3_vals = plot_df["sector_3"].tolist()
            drivers = plot_df.index.tolist()
        else:
            drivers = best["name_acronym"].tolist()
            s1_vals = best["s1"].tolist()
            s2_vals = best["s2"].tolist()
            s3_vals = best["s3"].tolist()

        fig = go.Figure()

        sector_colors = ["#E8002D", "#FF8C00", "#FFD700"]
        sector_names = ["Sector 1", "Sector 2", "Sector 3"]

        for s_vals, s_name, s_color in zip(
            [s1_vals, s2_vals, s3_vals], sector_names, sector_colors
        ):
            hover = [
                f"<b>{d}</b><br>{s_name}: {_fmt_sector(v)}"
                for d, v in zip(drivers, s_vals)
            ]
            fig.add_trace(go.Bar(
                name=s_name,
                x=drivers,
                y=s_vals,
                marker_color=s_color,
                hoverinfo="text",
                hovertext=hover,
            ))

        fig.update_layout(
            barmode="stack",
            xaxis_title="Driver",
            yaxis_title="Time (s)",
            hovermode="closest",
            height=500,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            margin=dict(t=40),
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

        # Best sector table
        with st.expander("Best sector times"):
            display = best.copy()
            display["s1"] = display["s1"].apply(_fmt_sector)
            display["s2"] = display["s2"].apply(_fmt_sector)
            display["s3"] = display["s3"].apply(_fmt_sector)
            display["best_lap"] = display["best_lap"].apply(_fmt_sector)
            display = display.rename(columns={
                "name_acronym": "Driver",
                "s1": "Sector 1",
                "s2": "Sector 2",
                "s3": "Sector 3",
                "best_lap": "Best Lap (sum)",
            })
            st.dataframe(display.set_index("Driver"), use_container_width=True)

        if source == "FastF1":
            st.caption("Data source: FastF1")


def _extract_sectors_local(raw: pd.DataFrame) -> pd.DataFrame:
    """Extract sector columns from the local API laps response."""
    needed = {"driver_number", "duration_sector_1", "duration_sector_2", "duration_sector_3"}
    if raw.empty or not needed.issubset(raw.columns):
        return pd.DataFrame()
    df = raw[["driver_number", "duration_sector_1", "duration_sector_2", "duration_sector_3"]].copy()
    df = df.rename(columns={
        "duration_sector_1": "sector_1",
        "duration_sector_2": "sector_2",
        "duration_sector_3": "sector_3",
    })
    return df.dropna(subset=["sector_1", "sector_2", "sector_3"])
