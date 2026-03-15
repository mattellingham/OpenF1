"""
Chart registry — add new charts here to make them appear in the dashboard.
Order determines tab order.
"""

from app.charts.lap_times import LapTimesChart
from app.charts.tire_strategy import TireStrategyChart
from app.charts.pit_stops import PitStopsChart
from app.charts.position_tracker import PositionTrackerChart
from app.charts.head_to_head import HeadToHeadChart
from app.charts.tyre_degradation import TyreDegradationChart
from app.charts.weather import WeatherChart
from app.charts.race_control import RaceControlChart

REGISTRY = [
    LapTimesChart(),
    TireStrategyChart(),
    PitStopsChart(),
    PositionTrackerChart(),
    HeadToHeadChart(),
    TyreDegradationChart(),
    WeatherChart(),
    RaceControlChart(),
]
