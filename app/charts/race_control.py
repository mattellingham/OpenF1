import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from app.charts.base import F1Chart, ALL_SESSIONS
from app.fastf1_fallback import _load_session

FLAG_COLORS = {
    "GREEN": "#22c55e",
    "YELLOW": "#fbbf24",
    "DOUBLE YELLOW": "#f59e0b",
    "RED": "#ef4444",
    "CHEQUERED": "#ffffff",
    "BLUE": "#3b82f6",
    "BLACK AND WHITE": "#94a3b8",
    "CLEAR": "#22c55e",
    "": "#94a3b8",
}


class RaceControlChart(F1Chart):
    tab_label = "📻 Race Control"
    session_types = ALL_SESSIONS

    def render(self, context: dict) -> None:
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]

        try:
            session = _load_session(year, country, session_type)
            rc = session.race_control_messages
        except Exception as e:
            st.warning(f"Race control data not available: {e}")
            return

        if rc is None or rc.empty:
            st.warning("No race control messages available for this session.")
            return

        rc = rc.copy()
        rc["minutes"] = rc["Time"].dt.total_seconds() / 60
        rc["Flag"] = rc["Flag"].fillna("").str.upper()
        rc["Category"] = rc["Category"].fillna("").str.upper()

        # ── Timeline chart ────────────────────────────────────────────────────
        fig = go.Figure()

        # Add a horizontal baseline
        fig.add_hline(y=0, line_color="rgba(255,255,255,0.1)")

        for _, row in rc.iterrows():
            flag = str(row.get("Flag", "")).upper()
            color = FLAG_COLORS.get(flag, "#94a3b8")
            msg = str(row.get("Message", ""))
            category = str(row.get("Category", ""))

            fig.add_trace(go.Scatter(
                x=[row["minutes"]], y=[0],
                mode="markers",
                marker=dict(color=color, size=14, symbol="circle",
                            line=dict(color="rgba(0,0,0,0.5)", width=1)),
                name=flag if flag else category,
                showlegend=False,
                hovertemplate=(
                    f"<b>{row['minutes']:.1f} min</b><br>"
                    f"{msg}<extra></extra>"
                ),
            ))

        fig.update_layout(
            height=160,
            margin=dict(t=10, b=10, l=20, r=20),
            yaxis=dict(visible=False, range=[-1, 1]),
            xaxis_title="Session time (minutes)",
            hovermode="closest",
            plot_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Message log table ─────────────────────────────────────────────────
        st.markdown("#### Message Log")

        # Format for display
        display = rc[["minutes", "Category", "Flag", "Message"]].copy()
        display["minutes"] = display["minutes"].apply(lambda x: f"{x:.1f} min")
        display.columns = ["Time", "Category", "Flag", "Message"]
        display = display.sort_values("Time", ascending=False).reset_index(drop=True)

        # Colour-code flag column
        def flag_badge(flag):
            color = FLAG_COLORS.get(str(flag).upper(), "#94a3b8")
            if not flag:
                return ""
            return f'<span style="background:{color};color:#000;padding:2px 8px;border-radius:10px;font-size:0.8em;font-weight:bold">{flag}</span>'

        display["Flag"] = display["Flag"].apply(flag_badge)

        st.write(
            display.to_html(escape=False, index=False),
            unsafe_allow_html=True,
        )
        st.caption("Data source: FastF1")
