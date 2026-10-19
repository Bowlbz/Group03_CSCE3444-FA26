"""
MainScreenUI - the App Controller from the architecture diagram.

It handles the events in the design:
    launch()               -> UC-01 View Current Weather
    on_refresh_clicked()   -> UC-02 Refresh Information (Update button)
    on_location_selected() -> UC-03 Choose Location (UNT campus or current location)
and coordinates WeatherAPIClient, RecommendationProgram and AlertSystem.

The display_* / show_error methods build what the browser frontend
(static/app.js) draws on the Main, Hourly and Alerts screens.
"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import List, Optional

from .alert_system import AlertSystem
from .campuses import DEFAULT_CAMPUS_ID, get_campus
from .models import Recommendation, WeatherAlert, WeatherData
from .recommendation_program import RecommendationProgram
from .weather_api_client import NoConnectionError, WeatherAPIClient, WeatherAPIError


class MainScreenUI:
    def __init__(
        self,
        api_client: Optional[WeatherAPIClient] = None,
        recommendation_program: Optional[RecommendationProgram] = None,
        alert_system: Optional[AlertSystem] = None,
    ):
        self._api_client = api_client or WeatherAPIClient()
        self._recommendation_program = recommendation_program or RecommendationProgram()
        self._alert_system = alert_system or AlertSystem()

        self._current_weather: Optional[WeatherData] = None
        self._last_updated: Optional[datetime] = None
        self._is_loading = False
        self._lock = threading.Lock()
        self._place_names: dict = {}  # cache of lat/lon -> "City, ST"

    # ------------------------------------------------------------------ #
    # Events
    # ------------------------------------------------------------------ #
    def launch(self, location: Optional[dict] = None) -> dict:
        """UC-01: app opened (for the saved campus / current location)."""
        return self._load(is_refresh=False, location=location)

    def on_refresh_clicked(self, location: Optional[dict] = None) -> dict:
        """UC-02: Update button tapped."""
        return self._load(is_refresh=True, location=location)

    def on_location_selected(self, location: dict) -> dict:
        """UC-03: user picked a UNT campus or 'Use my current location'."""
        return self._load(is_refresh=False, location=location)

    # ------------------------------------------------------------------ #
    # Location handling
    # ------------------------------------------------------------------ #
    def _select_location(self, location: Optional[dict]) -> dict:
        """
        location is either {"campus": "<campus id>"} or
        {"latitude": <float>, "longitude": <float>} for the device's position.
        Returns the place info sent back to the frontend.
        """
        location = location or {}
        if "latitude" in location and "longitude" in location:
            lat = round(float(location["latitude"]), 4)
            lon = round(float(location["longitude"]), 4)
            key = (round(lat, 2), round(lon, 2))
            if key not in self._place_names:
                self._place_names[key] = self._api_client.describe_point(lat, lon)
            city = self._place_names[key]
            place = {
                "id": "current",
                "name": f"Current location ({city})" if city else "Current location",
                "short": city or "My location",
                "is_current": True,
                "latitude": lat,
                "longitude": lon,
            }
        else:
            campus = get_campus(location.get("campus")) or get_campus(DEFAULT_CAMPUS_ID)
            place = dict(campus, is_current=False)

        self._api_client.set_location(place["short"], place["latitude"], place["longitude"])
        return place

    # ------------------------------------------------------------------ #
    # Display helpers (what the frontend renders)
    # ------------------------------------------------------------------ #
    def display_weather(self, data: WeatherData) -> dict:
        return data.to_dict()

    def display_recommendations(self, recs: List[Recommendation]) -> list:
        return [r.to_dict() for r in recs]

    def display_alerts(self, alerts: List[WeatherAlert]) -> list:
        return [a.to_dict() for a in alerts]

    def show_error(self, error_type: str, message: str) -> dict:
        return {
            "ok": False,
            "error_type": error_type,
            "message": message,
            "last_updated": self._last_updated.isoformat() if self._last_updated else None,
        }

    # ------------------------------------------------------------------ #
    def _load(self, is_refresh: bool, location: Optional[dict] = None) -> dict:
        with self._lock:
            self._is_loading = True
            try:
                # Sequence diagram UC-01 step 3: checkConnection()
                if not self._api_client.check_connection():
                    return self.show_error("no_connection", "No internet connection.")

                place = self._select_location(location)

                # fetchCurrentWeather() -> WeatherData
                try:
                    data = self._api_client.fetch_current_weather()
                except NoConnectionError:
                    return self.show_error("no_connection", "No internet connection.")
                except WeatherAPIError:
                    msg = (
                        "Could not reach weather service."
                        if is_refresh
                        else "Weather data unavailable."
                    )
                    return self.show_error("api_error", msg)

                # Official NWS alerts (optional - forecast still shows if this fails)
                try:
                    api_alerts = self._api_client.fetch_alerts()
                    alerts_checked = True
                except WeatherAPIError:
                    api_alerts = []
                    alerts_checked = False

                # generate(WeatherData) / evaluate(WeatherData, apiAlerts)
                recommendations = self._recommendation_program.generate(data)
                self._alert_system.evaluate(data, api_alerts)
                alerts = self._alert_system.get_active_alerts()

                # lastUpdated = now()
                self._current_weather = data
                self._last_updated = data.retrieved_at

                return {
                    "ok": True,
                    "location": place,
                    "weather": self.display_weather(data),
                    "recommendations": self.display_recommendations(recommendations),
                    "alerts": self.display_alerts(alerts),
                    "alerts_checked": alerts_checked,
                    "last_updated": self._last_updated.isoformat(),
                }
            finally:
                self._is_loading = False
