"""
Strategy Simulator — projects 0/1/2-stop race finish times for selected drivers.

Uses linear tyre degradation rates derived from actual stint data (same model as
the Tyre Deg chart). For each driver the simulator evaluates three strategies:
  - No stop  (run to end on current compound)
  - 1 stop   (optimal split point, best compound pairing)
  - 2 stops  (two equal-ish stints + one short final)

Output: table per driver — strategy, projected total time, estimated finish gap.
"""

import numpy as np
import pandas as pd
import streamlit as st
from app.charts.base import F1Chart, RACE_SESSIONS
from app.data_loader import OpenF1Unavailable, fetch_laps, fetch_laps_live, fetch_stints, fetch_stints_live
from app.fastf1_fallback import get_laps_fastf1, get_stints_fastf1
from app.data_processor import process_lap_data, process_stints

# Default deg rates (s/lap) used when too few laps exist to fit a regression
_DEFAULT_DEG = {"SOFT": 0.080, "MEDIUM": 0.045, "HARD": 0.025, "INTERMEDIATE": 0.060, "WET": 0.050, "UNKNOWN": 0.050}
# Base lap-time offsets relative to SOFT for a fresh tyre (seconds)
_COMPOUND_OFFSET = {"SOFT": 0.0, "MEDIUM": 0.5, "HARD": 1.0, "INTERMEDIATE": 3.0, "WET": 8.0, "UNKNOWN": 1.0}

COMPOUND_COLORS = {
    "SOFT": "#e8002d", "MEDIUM": "#ffd700", "HARD": "#ebebeb",
    "INTERMEDIATE": "#39b54a", "WET": "#0067ff", "UNKNOWN": "#888888",
}
COMPOUND_ABBR = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W", "UNKNOWN": "?"}
COMPOUND_TEXT = {"SOFT": "#fff", "MEDIUM": "#000", "HARD": "#000", "INTERMEDIATE": "#fff", "WET": "#fff", "UNKNOWN": "#fff"}


def _stint_time(laps: int, base: float, deg: float) -> float:
    """Total time for a stint of `laps` laps starting from lap 1 of that tyre."""
    return sum(base + deg * (i - 1) for i in range(1, laps + 1))


def _best_compounds(available: list[str]) -> list[str]:
    """Return up to 2 best dry compounds from those seen in the session."""
    order = ["SOFT", "MEDIUM", "HARD"]
    dry = [c for c in order if c in available]
    return dry if dry else available[:2]


def _simulate(driver: str, laps_done: int, total_laps: int,
              base_time: float, deg_map: dict, pit_loss: float,
              available_compounds: list[str]) -> list[dict]:
    """Return list of strategy dicts for 0/1/2 stops."""
    remaining = total_laps - laps_done
    if remaining <= 0:
        return []

    results = []
    dry = _best_compounds(available_compounds)
    c1 = dry[0] if dry else "MEDIUM"
    c2 = dry[1] if len(dry) > 1 else c1

    # ── 0-stop ──────────────────────────────────────────────────────────
    deg0 = deg_map.get(c1, _DEFAULT_DEG.get(c1, 0.05))
    t0 = _stint_time(remaining, base_time, deg0)
    results.append({
        "Stops": 0,
        "Strategy": c1,
        "Time (s)": t0,
    })

    # ── 1-stop — try all split points, pick minimum total time ──────────
    best_1stop = None
    for split in range(max(1, remaining // 3), min(remaining, 2 * remaining // 3) + 1):
        for ca, cb in [(c1, c2), (c2, c1)]:
            if ca == cb and len(dry) < 2:
                continue
            dega = deg_map.get(ca, _DEFAULT_DEG.get(ca, 0.05))
            degb = deg_map.get(cb, _DEFAULT_DEG.get(cb, 0.05))
            offset_b = _COMPOUND_OFFSET.get(cb, 1.0) - _COMPOUND_OFFSET.get(ca, 0.0)
            ta = _stint_time(split, base_time, dega)
            tb = _stint_time(remaining - split, base_time + offset_b, degb)
            total = ta + pit_loss + tb
            if best_1stop is None or total < best_1stop["Time (s)"]:
                best_1stop = {
                    "Stops": 1,
                    "Strategy": f"{COMPOUND_ABBR.get(ca,'?')}→{COMPOUND_ABBR.get(cb,'?')}",
                    "_ca": ca, "_cb": cb,
                    "Time (s)": total,
                }
    if best_1stop:
        results.append(best_1stop)

    # ── 2-stop — equal thirds, best compound order ───────────────────────
    if remaining >= 9:
        third = remaining // 3
        combos = [(c1, c2, c1), (c2, c1, c2), (c1, c1, c2), (c2, c2, c1)]
        best_2stop = None
        for ca, cb, cc in combos:
            s1, s2, s3 = third, third, remaining - 2 * third
            dega = deg_map.get(ca, _DEFAULT_DEG.get(ca, 0.05))
            degb = deg_map.get(cb, _DEFAULT_DEG.get(cb, 0.05))
            degc = deg_map.get(cc, _DEFAULT_DEG.get(cc, 0.05))
            ob = _COMPOUND_OFFSET.get(cb, 1.0) - _COMPOUND_OFFSET.get(ca, 0.0)
            oc = _COMPOUND_OFFSET.get(cc, 1.0) - _COMPOUND_OFFSET.get(ca, 0.0)
            ta = _stint_time(s1, base_time, dega)
            tb = _stint_time(s2, base_time + ob, degb)
            tc = _stint_time(s3, base_time + oc, degc)
            total = ta + pit_loss + tb + pit_loss + tc
            if best_2stop is None or total < best_2stop["Time (s)"]:
                best_2stop = {
                    "Stops": 2,
                    "Strategy": f"{COMPOUND_ABBR.get(ca,'?')}→{COMPOUND_ABBR.get(cb,'?')}→{COMPOUND_ABBR.get(cc,'?')}",
                    "Time (s)": total,
                }
        if best_2stop:
            results.append(best_2stop)

    return results


class StrategySimulatorChart(F1Chart):
    tab_label = "🎯 Strategy Sim"
    session_types = RACE_SESSIONS
    unavailable_message = "Strategy simulator is only available for Race and Sprint sessions."

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

        # ── Load data ─────────────────────────────────────────────────────
        if fastf1_mode:
            lap_df = get_laps_fastf1(year, country, session_type)
            stints_raw = get_stints_fastf1(year, country, session_type)
        else:
            try:
                lap_fn = fetch_laps_live if is_live else fetch_laps
                stint_fn = fetch_stints_live if is_live else fetch_stints
                lap_df = lap_fn(session_key)
                stints_raw = stint_fn(session_key)
            except OpenF1Unavailable:
                lap_df = get_laps_fastf1(year, country, session_type)
                stints_raw = get_stints_fastf1(year, country, session_type)

        laps = process_lap_data(lap_df)
        stints = process_stints(stints_raw)

        if laps.empty or stints.empty:
            st.warning("Not enough data for strategy simulation.")
            return

        laps["driver_number"] = laps["driver_number"].astype(str)
        stints["driver_number"] = stints["driver_number"].astype(str)
        laps = laps.merge(driver_info, on="driver_number", how="left")
        stints = stints.merge(driver_info, on="driver_number", how="left")
        laps = laps[laps["name_acronym"].isin(selected_drivers)]
        stints = stints[stints["name_acronym"].isin(selected_drivers)]

        # ── User inputs ───────────────────────────────────────────────────
        col1, col2 = st.columns(2)
        with col1:
            pit_loss = st.number_input(
                "Pit loss (s)", min_value=10.0, max_value=60.0, value=22.0, step=0.5,
                help="Total time lost per pit stop including pit lane transit."
            )
        with col2:
            laps_done_default = int(laps["lap_number"].max()) if not laps.empty else 0
            total_laps = st.number_input(
                "Total race laps", min_value=1, max_value=100,
                value=max(laps_done_default + 10, 60), step=1,
            )

        laps_done = int(laps["lap_number"].max()) if not laps.empty else 0
        remaining = total_laps - laps_done
        if remaining <= 0:
            st.info("Race complete — no laps remaining to simulate.")
            return

        st.caption(
            f"Laps completed: **{laps_done}** · Remaining: **{remaining}** · "
            f"Simulating from current lap to end."
        )

        # ── Build degradation model (same as Tyre Deg chart) ─────────────
        rows_combined = []
        for _, stint in stints.iterrows():
            mask = (
                (laps["name_acronym"] == stint["name_acronym"]) &
                (laps["lap_number"] >= stint["lap_start"]) &
                (laps["lap_number"] <= stint["lap_end"])
            )
            stint_laps = laps[mask].copy()
            stint_laps["compound"] = stint["compound"]
            stint_laps["stint_lap"] = stint_laps["lap_number"] - stint["lap_start"] + 1
            rows_combined.append(stint_laps)

        if not rows_combined:
            st.warning("Could not match laps to stints.")
            return

        combined = pd.concat(rows_combined, ignore_index=True)

        # Deg rates per compound (pooled across all drivers for stability)
        deg_map: dict = {}
        base_map: dict = {}  # driver → current base lap time
        available_compounds = set()

        for compound, grp in combined.groupby("compound"):
            compound_upper = str(compound).upper()
            available_compounds.add(compound_upper)
            grp = grp.sort_values("stint_lap")
            median_t = grp["lap_duration"].median()
            grp = grp[grp["lap_duration"] <= median_t * 1.08]
            if len(grp) >= 4:
                coeffs = np.polyfit(grp["stint_lap"].values, grp["lap_duration"].values, 1)
                deg_map[compound_upper] = float(coeffs[0])

        # Per-driver base lap time = median of their recent clean laps
        for driver in selected_drivers:
            drv_laps = combined[combined["name_acronym"] == driver]["lap_duration"]
            if not drv_laps.empty:
                median_t = float(drv_laps.median())
                base_map[driver] = median_t

        # ── Simulate & render ─────────────────────────────────────────────
        all_results = []
        for driver in selected_drivers:
            base = base_map.get(driver)
            if base is None:
                continue
            sims = _simulate(
                driver, laps_done, total_laps,
                base, deg_map, pit_loss, list(available_compounds)
            )
            for s in sims:
                s["Driver"] = driver
                all_results.append(s)

        if not all_results:
            st.warning("Insufficient lap data to run simulation.")
            return

        results_df = pd.DataFrame(all_results)

        # Rank by projected time within each stop strategy
        results_df["_rank"] = results_df.groupby("Stops")["Time (s)"].rank()

        rows_html = ""
        prev_driver = None
        for driver in selected_drivers:
            drv_rows = results_df[results_df["Driver"] == driver].sort_values("Stops")
            if drv_rows.empty:
                continue
            color = color_map.get(driver, "#888")
            best_time = drv_rows["Time (s)"].min()

            for i, (_, r) in enumerate(drv_rows.iterrows()):
                t = r["Time (s)"]
                delta = t - best_time
                delta_str = "BEST" if delta < 0.1 else f"+{delta:.1f}s"
                delta_color = "#22c55e" if delta < 0.1 else "#8E8EA8"
                stops = int(r["Stops"])
                strategy = r["Strategy"]

                # Colour each compound letter in the strategy string
                def _colour_strategy(s):
                    rev = {"S": "SOFT", "M": "MEDIUM", "H": "HARD", "I": "INTERMEDIATE", "W": "WET"}
                    parts = s.split("→")
                    out = []
                    for p in parts:
                        cmp = rev.get(p, "UNKNOWN")
                        bg = COMPOUND_COLORS.get(cmp, "#888")
                        fg = COMPOUND_TEXT.get(cmp, "#fff")
                        out.append(
                            f'<span style="background:{bg};color:{fg};padding:1px 5px;'
                            f'border-radius:3px;font-size:10px;font-weight:700">{p}</span>'
                        )
                    return '<span style="color:#6B6B7B;font-size:10px;margin:0 2px">→</span>'.join(out)

                strat_html = _colour_strategy(strategy)

                # Driver cell only on first row
                if i == 0:
                    driver_cell = (
                        f'<td rowspan="{len(drv_rows)}" style="padding:6px 10px;'
                        f'vertical-align:middle;border-bottom:1px solid #2E2E42">'
                        f'<span style="display:inline-block;width:3px;height:14px;background:{color};'
                        f'border-radius:2px;margin-right:6px;vertical-align:middle"></span>'
                        f'<strong style="color:{color}">{driver}</strong></td>'
                    )
                else:
                    driver_cell = ""

                m = int(t // 60)
                sec = t - m * 60
                time_str = f"{m}:{sec:05.1f}"

                rows_html += (
                    f'<tr>'
                    f'{driver_cell}'
                    f'<td style="padding:5px 10px;color:#6B6B7B;text-align:center">{stops}</td>'
                    f'<td style="padding:5px 10px">{strat_html}</td>'
                    f'<td style="padding:5px 10px;font-variant-numeric:tabular-nums;color:#E8E8F0">{time_str}</td>'
                    f'<td style="padding:5px 10px;font-weight:700;color:{delta_color}">{delta_str}</td>'
                    f'</tr>'
                )

        st.html(
            '<style>'
            '.sim-tbl{width:100%;border-collapse:collapse;font-size:12px}'
            '.sim-tbl th{font-size:10px;letter-spacing:1px;text-transform:uppercase;'
            'color:#6B6B7B;padding:6px 10px;text-align:left;border-bottom:1px solid #2E2E42}'
            '.sim-tbl td{border-bottom:1px solid #1e1e2e}'
            '.sim-tbl tr:hover td{background:#252538}'
            '</style>'
            '<table class="sim-tbl"><thead><tr>'
            '<th>Driver</th><th>Stops</th><th>Strategy</th>'
            '<th>Proj. Time</th><th>vs Best</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>'
        )
        st.caption(
            f"Projected from lap {laps_done} to end of race ({total_laps} laps). "
            f"Pit loss: {pit_loss:.1f}s. Deg rates from session data; "
            "defaults used where insufficient laps available."
        )
