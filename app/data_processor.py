import pandas as pd

# Fallback colour palette for when team colours aren't available (e.g. early season FastF1 data)
# 20 visually distinct colours
_FALLBACK_PALETTE = [
    "#e8002d", "#ff8700", "#ffd700", "#00d2be", "#0067ff",
    "#dc0000", "#ff8181", "#b6babd", "#358c75", "#5e8fac",
    "#c92d4b", "#f596c8", "#1e3d61", "#6596ff", "#99274f",
    "#ff5f00", "#00e0dd", "#469bff", "#9b0000", "#ff1e00",
]


def process_lap_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df[df['lap_duration'].notna()]
    df = df.sort_values(['driver_number', 'lap_number'])
    return df


def process_stints(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.sort_values(by=["driver_number", "stint_number"])
    df["compound"] = df["compound"].fillna("Unknown")
    df["lap_count"] = df["lap_end"] - df["lap_start"] + 1
    return df


def process_pit_stops(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df[df["pit_duration"].notna()]
    df = df.sort_values(by=["driver_number", "lap_number"])
    return df


def build_driver_color_map(driver_df: pd.DataFrame) -> dict:
    """
    Build a dict mapping driver acronym -> hex colour string.

    Uses team_colour from the data where available. Falls back to a
    distinct palette for drivers with missing/invalid colours so that
    all drivers are visually distinguishable.
    """
    if driver_df.empty:
        return {}

    driver_df = driver_df.copy()
    driver_df["driver_number"] = driver_df["driver_number"].astype(str)

    color_map = {}
    palette_index = 0

    for _, row in driver_df.iterrows():
        acronym = str(row["name_acronym"])
        raw_colour = row.get("team_colour", None)

        # Determine if the colour is valid and usable
        colour = None
        if pd.notna(raw_colour) and raw_colour not in (None, "nan", "", "AAAAAA", "#AAAAAA"):
            raw_str = str(raw_colour).strip()
            colour = raw_str if raw_str.startswith("#") else f"#{raw_str}"

        if not colour:
            # Assign from fallback palette, cycling if needed
            colour = _FALLBACK_PALETTE[palette_index % len(_FALLBACK_PALETTE)]
            palette_index += 1

        color_map[acronym] = colour

    return color_map
