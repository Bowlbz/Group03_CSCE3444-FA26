"""
WeatherAPIClient - talks to the External Weather API over HTTPS and
parses the JSON into WeatherData / HourlyForecast / WeatherAlert objects.

Forecast data: Open-Meteo (free, no API key).
Severe weather alerts: National Weather Service API (free, no API key).
"""

from __future__ import annotations

import re
import socket
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlparse

import requests

from .models import (
    DailyForecast,
    HourlyForecast,
    WeatherAlert,
    WeatherData,
    describe_weather_code,
)

# UNT main campus, Denton, TX
DENTON_LATITUDE = 33.2107
DENTON_LONGITUDE = -97.1477

COMPASS_POINTS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# The National Weather Service asks every app to identify itself.
NWS_HEADERS = {
    "User-Agent": "MeanGreenWeather (UNT CSCE 3444 class project)",
    "Accept": "application/geo+json",
}
NWS_POINTS_URL = "https://api.weather.gov/points/{lat:.4f},{lon:.4f}"


class WeatherAPIError(Exception):
    """The weather service returned an error, timed out, or sent unreadable data."""


class NoConnectionError(WeatherAPIError):
    """There is no Internet connection."""


def _wind_direction(degrees: Optional[float]) -> str:
    if degrees is None:
        return ""
    return COMPASS_POINTS[int(round(degrees / 45.0)) % 8]


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class WeatherAPIClient:
    def __init__(
        self,
        base_url: str = "https://api.open-meteo.com/v1/forecast",
        api_key: Optional[str] = None,
        location: str = "Denton, TX",
        latitude: float = DENTON_LATITUDE,
        longitude: float = DENTON_LONGITUDE,
        timeout_seconds: int = 8,
        alerts_url: str = "https://api.weather.gov/alerts/active",
        days_ahead: int = 7,
    ):
        self._base_url = base_url
        self._api_key = api_key  # Open-Meteo needs no key; kept to match the design
        self._location = location
        self._latitude = latitude
        self._longitude = longitude
        self._timeout_seconds = timeout_seconds
        self._alerts_url = alerts_url
        self._days_ahead = days_ahead

    @property
    def location(self) -> str:
        return self._location

    def set_location(self, name: str, latitude: float, longitude: float) -> None:
        """UC-03: switch to a UNT campus or the user's current location."""
        self._location = name
        self._latitude = latitude
        self._longitude = longitude

    def describe_point(self, latitude: float, longitude: float) -> Optional[str]:
        """'Plano, TX' for a lat/lon (US only, via NWS). None if unknown."""
        try:
            resp = requests.get(
                NWS_POINTS_URL.format(lat=latitude, lon=longitude),
                headers=NWS_HEADERS,
                timeout=self._timeout_seconds,
            )
            resp.raise_for_status()
            rel = resp.json()["properties"]["relativeLocation"]["properties"]
            return f"{rel['city']}, {rel['state']}"
        except (requests.RequestException, ValueError, KeyError, TypeError):
            return None

    # ------------------------------------------------------------------ #
    # Public methods (class diagram)
    # ------------------------------------------------------------------ #
    def check_connection(self) -> bool:
        """UC-01 step 3: is the Internet / weather service reachable?"""
        host = urlparse(self._base_url).hostname or "api.open-meteo.com"
        try:
            with socket.create_connection((host, 443), timeout=3):
                return True
        except OSError:
            return False

    def fetch_current_weather(self) -> WeatherData:
        """GET current conditions + hourly forecast for the selected location."""
        params = {
            "latitude": self._latitude,
            "longitude": self._longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "is_day",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_direction_10m",
                ]
            ),
            "hourly": "temperature_2m,precipitation_probability,weather_code",
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "wind_speed_10m_max",
                ]
            ),
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",  # local time of the selected location
            "forecast_days": self._days_ahead,  # today + the next 6 days
        }
        if self._api_key:
            params["apikey"] = self._api_key

        try:
            resp = requests.get(self._base_url, params=params, timeout=self._timeout_seconds)
            resp.raise_for_status()
            payload = resp.json()
        except requests.Timeout as exc:
            raise WeatherAPIError("The weather service took too long to respond.") from exc
        except requests.ConnectionError as exc:
            raise NoConnectionError("Could not connect to the weather service.") from exc
        except (requests.RequestException, ValueError) as exc:
            raise WeatherAPIError("The weather service returned an error.") from exc

        return self._parse_response(payload)

    def fetch_hourly_forecast(self) -> List[HourlyForecast]:
        return self.fetch_current_weather().hourly_forecast

    def fetch_daily_forecast(self) -> List[DailyForecast]:
        return self.fetch_current_weather().daily_forecast

    def fetch_alerts(self) -> List[WeatherAlert]:
        """Active National Weather Service alerts for the selected location."""
        try:
            resp = requests.get(
                self._alerts_url,
                params={"point": f"{self._latitude:.4f},{self._longitude:.4f}"},
                headers=NWS_HEADERS,
                timeout=self._timeout_seconds,
            )
            resp.raise_for_status()
            features = resp.json().get("features", [])
        except (requests.RequestException, ValueError) as exc:
            raise WeatherAPIError("Could not check weather alerts.") from exc

        alerts = []
        for feature in features:
            props = feature.get("properties") or {}
            alerts.append(
                WeatherAlert(
                    type=props.get("event") or "Weather Alert",
                    severity=props.get("severity") or "Unknown",
                    headline=props.get("headline") or "",
                    description=(props.get("description") or "").strip(),
                    expires_at=_parse_iso(props.get("ends") or props.get("expires")),
                    issued_at=_parse_iso(props.get("onset") or props.get("effective") or props.get("sent")),
                    instructions=self._split_instructions(props.get("instruction")),
                )
            )
        return alerts

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #
    def _parse_response(self, data: dict) -> WeatherData:
        """UC-01 step 6: JSON -> WeatherData (+ HourlyForecast and DailyForecast lists)."""
        try:
            tz = timezone(timedelta(seconds=int(data.get("utc_offset_seconds", 0))))
            current = data["current"]
            hourly = data["hourly"]
            daily = data["daily"]

            now_hour = datetime.fromisoformat(current["time"]).replace(minute=0, tzinfo=tz)

            forecasts: List[HourlyForecast] = []
            for i, stamp in enumerate(hourly["time"]):
                when = datetime.fromisoformat(stamp).replace(tzinfo=tz)
                if when < now_hour:
                    continue
                code = int(hourly["weather_code"][i] or 0)
                forecasts.append(
                    HourlyForecast(
                        time=when,
                        temperature=float(hourly["temperature_2m"][i] or 0),
                        conditions=describe_weather_code(code),
                        precipitation_chance=int(hourly["precipitation_probability"][i] or 0),
                        weather_code=code,
                    )
                )

            days: List[DailyForecast] = []
            for i, day in enumerate(daily["time"]):
                day_code = int((daily.get("weather_code") or [0] * len(daily["time"]))[i] or 0)
                rain = (daily.get("precipitation_probability_max") or [None] * len(daily["time"]))[i]
                wind = (daily.get("wind_speed_10m_max") or [None] * len(daily["time"]))[i]
                days.append(
                    DailyForecast(
                        date=day,
                        high_temp=float(daily["temperature_2m_max"][i] or 0),
                        low_temp=float(daily["temperature_2m_min"][i] or 0),
                        conditions=describe_weather_code(day_code),
                        precipitation_chance=int(rain or 0),
                        weather_code=day_code,
                        wind_speed_max=float(wind or 0),
                    )
                )

            code = int(current.get("weather_code") or 0)
            return WeatherData(
                current_temp=float(current["temperature_2m"]),
                feels_like=float(current["apparent_temperature"]),
                conditions=describe_weather_code(code),
                precipitation_chance=forecasts[0].precipitation_chance if forecasts else 0,
                wind_speed=float(current.get("wind_speed_10m") or 0),
                humidity=int(current.get("relative_humidity_2m") or 0),
                retrieved_at=datetime.now(tz),
                hourly_forecast=forecasts,
                daily_forecast=days,
                wind_direction=_wind_direction(current.get("wind_direction_10m")),
                high_temp=daily["temperature_2m_max"][0],
                low_temp=daily["temperature_2m_min"][0],
                weather_code=code,
                is_day=current.get("is_day", 1) == 1,
                location=self._location,
                timezone=data.get("timezone") or "America/Chicago",
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise WeatherAPIError("The weather service sent data the app could not read.") from exc

    @staticmethod
    def _split_instructions(text: Optional[str]) -> List[str]:
        if not text:
            return []
        flat = " ".join(text.split())
        sentences = re.split(r"(?<=[.!])\s+", flat)
        return [s for s in sentences if s][:5]
