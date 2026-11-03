"""
Mean Green Weather - application logic / backend.

Each module maps to a class from Section 1 (Class Diagram) of the
Software Design Document:

    models.py                 -> WeatherData, HourlyForecast, DailyForecast, Recommendation, WeatherAlert
    weather_api_client.py     -> WeatherAPIClient
    recommendation_program.py -> RecommendationProgram
    alert_system.py           -> AlertSystem
    main_screen_ui.py         -> MainScreenUI (app controller)
    campuses.py               -> UNT campus list for the location picker
"""

from .models import DailyForecast, HourlyForecast, Recommendation, WeatherAlert, WeatherData
from .weather_api_client import NoConnectionError, WeatherAPIClient, WeatherAPIError
from .recommendation_program import RecommendationProgram
from .alert_system import AlertSystem
from .main_screen_ui import MainScreenUI
from .campuses import CAMPUSES, DEFAULT_CAMPUS_ID, campus_groups, get_campus

__all__ = [
    "DailyForecast",
    "HourlyForecast",
    "Recommendation",
    "WeatherAlert",
    "WeatherData",
    "WeatherAPIClient",
    "WeatherAPIError",
    "NoConnectionError",
    "RecommendationProgram",
    "AlertSystem",
    "MainScreenUI",
    "CAMPUSES",
    "DEFAULT_CAMPUS_ID",
    "campus_groups",
    "get_campus",
]
