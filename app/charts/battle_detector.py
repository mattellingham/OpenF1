import pandas as pd
import streamlit as st
from app.charts.base import F1Chart, RACE_SESSIONS
from app.fastf1_fallback import get_gaps_fastf1
from app.data_loader import OpenF1Unavailable, fetch_intervals, fetch_intervals_live

_BATTLE_THRESHOLD = 1.5  # seconds


def _intensity(interval: float) -> tuple[str, str]:
    """Return (background, text) hex colours based on gap size."""
    if interval < 0.5:
        return "#ef4444", "#fff"   # red — very close
    if interval < 1.0:
        return "#f97316", "#000"   # orange
    return "#fbbf24", "#000"       # yellow — within DRS window edge


class BattleDetectorChart(F1Chart):
    tab_label = "🔥 Battles"
    session_types = RACE_SESSIONS
    unavailable_message = "Battle detection is only available for Race and Sprint sessions."

    def render(self, context: dict) -> None:
        session_key = context["session_key"]
        session_type = context["session_type"]
        country = context["country"]
        year = context["year"]
        driver_info = context["driver_info"]
        color_map = context["color_map"]
        fastf1_mode = context["fastf1_mode"]
        is_live = context["is_live"]

        gaps = pd.DataFrame()
        if not fastf1_mode:
            try:
                fn = fetch_intervals_live if is_live else fetch_intervals
                raw = fn(session_key)
                if not raw.empty and {"driver_number", "gap_to_leader", "interval_to_position_ahead"}.issubset(raw.columns):
                    latest = raw.sort_values("date").groupby("driver_number").last().reset_index()
                    gaps = latest[["driver_number", "gap_to_leader", "interval_to_position_ahead"]].rename(
                        columns={"interval_to_position_ahead": "interval"}
                    )
                    gaps["position"] = range(1, len(gaps) + 1)
            except Exception:
                pass

        if gaps.empty:
            gaps = get_gaps_fastf1(year, country, session_type)

        if gaps.empty:
            st.warning("Gap data not available for this session.")
            return

        gaps["driver_number"] = gaps["driver_number"].astype(str)
        gaps = gaps.merge(driver_info, on="driver_number", how="left")
        gaps = gaps.sort_values("position").reset_index(drop=True)

        # Find battles: interval to car ahead < threshold (skip P1 — no car ahead)
        battles = gaps[
            (gaps["position"] > 1) &
            (gaps["interval"].notna()) &
            (gaps["interval"] < _BATTLE_THRESHOLD)
        ].copy()

        if battles.empty:
            st.info(f"No battles detected — no driver pairs within {_BATTLE_THRESHOLD}s of each other.")
            return

        battles = battles.sort_values("interval")

        # Build the car-ahead name for each battle
        pos_to_acronym = gaps.set_index("position")["name_acronym"].to_dict()

        rows = ""
        for _, r in battles.iterrows():
            pos = int(r["position"])
            chaser = r.get("name_acronym", "")
            leader = pos_to_acronym.get(pos - 1, "?")
            interval = float(r["interval"])
            bg, fg = _intensity(interval)
            chaser_color = color_map.get(chaser, "#888")
            leader_color = color_map.get(leader, "#888")
            drs = "DRS" if interval < 1.0 else ""
            drs_badge = (
                f'<span style="background:#22d3ee;color:#000;font-size:9px;font-weight:700;'
                f'padding:1px 5px;border-radius:3px;margin-left:6px">{drs}</span>'
            ) if drs else ""

            rows += (
                f'<tr>'
                f'<td style="padding:8px 12px">'
                f'  <div style="display:flex;align-items:center;gap:8px">'
                f'    <span style="font-size:11px;font-weight:700;color:{leader_color}">{leader}</span>'
                f'    <span style="color:#6B6B7B;font-size:10px">P{pos - 1}</span>'
                f'  </div>'
                f'  <div style="font-size:9px;color:#6B6B7B;margin-top:2px">ahead</div>'
                f'</td>'
                f'<td style="padding:8px 12px">'
                f'  <div style="display:flex;align-items:center;gap:8px">'
                f'    <span style="font-size:11px;font-weight:700;color:{chaser_color}">{chaser}</span>'
                f'    <span style="color:#6B6B7B;font-size:10px">P{pos}</span>'
                f'  </div>'
                f'  <div style="font-size:9px;color:#6B6B7B;margin-top:2px">chasing</div>'
                f'</td>'
                f'<td style="padding:8px 12px;text-align:center">'
                f'  <span style="background:{bg};color:{fg};font-size:13px;font-weight:900;'
                f'  padding:4px 12px;border-radius:6px;font-variant-numeric:tabular-nums">'
                f'  {interval:.3f}s</span>'
                f'  {drs_badge}'
                f'</td>'
                f'</tr>'
            )

        st.html(
            '<style>.btl-tbl{width:100%;border-collapse:collapse;font-size:12px}'
            '.btl-tbl th{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
            'color:#6B6B7B;padding:6px 12px;text-align:left;border-bottom:1px solid #2E2E42}'
            '.btl-tbl td{border-bottom:1px solid #1e1e2e}'
            '.btl-tbl tr:hover td{background:#252538}</style>'
            '<table class="btl-tbl"><thead><tr>'
            '<th>Ahead</th><th>Chasing</th><th>Gap</th>'
            f'</tr></thead><tbody>{rows}</tbody></table>'
        )

        st.caption(
            f"Showing gaps < {_BATTLE_THRESHOLD}s · "
            f"🔴 < 0.5s &nbsp; 🟠 < 1.0s &nbsp; 🟡 < 1.5s &nbsp; "
            f"<span style='background:#22d3ee;color:#000;padding:1px 5px;border-radius:3px;font-size:9px;font-weight:700'>DRS</span> = within DRS zone",
            unsafe_allow_html=True,
        )
