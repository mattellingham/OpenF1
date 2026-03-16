"""
Base class for all F1 dashboard chart modules.

To add a new chart:
1. Create a new file in app/charts/
2. Define a class that inherits from F1Chart
3. Set tab_label and session_types
4. Implement render(context)
5. Add the class to REGISTRY in app/charts/__init__.py
"""

from abc import ABC, abstractmethod

ALL_SESSIONS = [
    "Race", "Qualifying", "Practice 1", "Practice 2", "Practice 3",
    "Sprint", "Sprint Qualifying", "Sprint Shootout",
]
RACE_SESSIONS = ["Race", "Sprint"]
TIMED_SESSIONS = ["Race", "Sprint", "Qualifying", "Sprint Qualifying", "Sprint Shootout"]

# Shared Plotly config — used by all charts for consistent toolbar behaviour
PLOTLY_CONFIG = dict(
    displayModeBar=True,
    modeBarButtonsToRemove=["select2d", "lasso2d"],
    displaylogo=False,
    toImageButtonOptions={"format": "png"},
)


class F1Chart(ABC):
    tab_label: str = ""
    session_types: list[str] = ALL_SESSIONS
    unavailable_message: str = "This chart is not available for this session type."

    def is_available(self, session_type: str) -> bool:
        for s in self.session_types:
            if session_type.strip().startswith(s):
                return True
        return False

    @abstractmethod
    def render(self, context: dict) -> None:
        """
        Render the chart into the current Streamlit tab.

        context keys:
            session_key     str
            session_type    str    e.g. "Race", "Qualifying"
            country         str    e.g. "Japan"
            year            int
            driver_info     pd.DataFrame  — driver_number, name_acronym
            color_map       dict   — name_acronym -> hex colour
            selected_drivers list[str]
            fastf1_mode     bool
            is_live         bool
        """
        pass
