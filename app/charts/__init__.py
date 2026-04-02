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
from app.charts.track_map import TrackMapChart
from app.charts.results import ResultsChart
from app.charts.sector_times import SectorTimesChart
from app.charts.speed_trap import SpeedTrapChart
from app.charts.battle_detector import BattleDetectorChart
from app.charts.pit_window import PitWindowChart
from app.charts.driver_detail import DriverDetailChart

REGISTRY = [
    LapTimesChart(),
    SectorTimesChart(),
    SpeedTrapChart(),
    TireStrategyChart(),
    PitStopsChart(),
    PositionTrackerChart(),
    BattleDetectorChart(),
    PitWindowChart(),
    HeadToHeadChart(),
    TyreDegradationChart(),
    DriverDetailChart(),
    WeatherChart(),
    RaceControlChart(),
    TrackMapChart(),
    ResultsChart(),
]
