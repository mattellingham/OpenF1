"""
Base class for all F1 dashboard chart modules.

To add a new chart:
1. Create a new file in app/charts/
2. Define a class that inherits from F1Chart
3. Set title, tab_label, and session_types
4. Implement render(context)
5. Add the class to REGISTRY in app/charts/__init__.py

That's it — main.py picks it up automatically.
"""

from abc import ABC, abstractmethod


# All possible session types
ALL_SESSIONS = [
    "Race", "Qualifying", "Practice 1", "Practice 2", "Practice 3",
    "Sprint", "Sprint Qualifying", "Sprint Shootout",
]

RACE_SESSIONS = ["Race", "Sprint"]
TIMED_SESSIONS = ["Race", "Sprint", "Qualifying", "Sprint Qualifying", "Sprint Shootout"]


class F1Chart(ABC):
    # Display name shown in the tab
    tab_label: str = ""

    # Which session types this chart is valid for.
    # Use ALL_SESSIONS, RACE_SESSIONS, TIMED_SESSIONS, or a custom list.
    session_types: list[str] = ALL_SESSIONS

    # Shown to users when the chart is not available for the current session
    unavailable_message: str = "This chart is not available for this session type."

    def is_available(self, session_type: str) -> bool:
        """Return True if this chart supports the given session type."""
        # Normalise — strip any trailing whitespace or date suffixes
        for s in self.session_types:
            if session_type.strip().startswith(s):
                return True
        return False

    @abstractmethod
    def render(self, context: dict) -> None:
        """
        Render the chart into the current Streamlit context.

        context keys:
            session_key     str   — local API session identifier
            session_type    str   — e.g. "Race", "Qualifying"
            country         str   — e.g. "Japan"
            year            int
            driver_info     pd.DataFrame  — driver_number, name_acronym
            color_map       dict  — name_acronym -> hex colour
            selected_drivers list[str]  — filtered acronyms from multiselect
            fastf1_mode     bool  — True when using FastF1 fallback
            is_live         bool
        """
        pass
