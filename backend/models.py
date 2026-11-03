"""
Data classes from the class diagram.

All weather data is held in memory only (SDD Section 5: no database).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

# WMO weather codes used by Open-Meteo -> plain-language conditions.
WEATHER_CODES = {
    0: "Clear",
    1: "Mostly clear",
    2: "Partly cloudy",
    3: "Cloudy",
    45: "Fog",
    48: "Freezing fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Rain showers",
    81: "Rain showers",
    82: "Heavy rain showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorms",
    96: "Thunderstorms with hail",
    99: "Thunderstorms with hail",
}

THUNDERSTORM_CODES = {95, 96, 99}


def describe_weather_code(code: int) -> str:
    return WEATHER_CODES.get(code, "Unknown")


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


@dataclass
class HourlyForecast:
    time: datetime
    temperature: float
    conditions: str
    precipitation_chance: int
    weather_code: int = 0  # used by the UI to pick an icon

    def to_dict(self) -> dict:
        return {
            "time": _iso(self.time),
            "temperature": self.temperature,
            "conditions": self.conditions,
            "precipitation_chance": self.precipitation_chance,
            "weather_code": self.weather_code,
        }


@dataclass
class DailyForecast:
    """One day of the 7-day forecast (Today, Tomorrow, Wed, ...)."""

    date: str  # "2026-10-21", in the location's local time
    high_temp: float
    low_temp: float
    conditions: str
    precipitation_chance: int
    weather_code: int = 0
    wind_speed_max: float = 0.0

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "high_temp": self.high_temp,
            "low_temp": self.low_temp,
            "conditions": self.conditions,
            "precipitation_chance": self.precipitation_chance,
            "weather_code": self.weather_code,
            "wind_speed_max": self.wind_speed_max,
        }


@dataclass
class WeatherData:
    current_temp: float
    feels_like: float
    conditions: str
    precipitation_chance: int
    wind_speed: float
    humidity: int
    retrieved_at: datetime
    hourly_forecast: List[HourlyForecast] = field(default_factory=list)  # now through day 7
    daily_forecast: List[DailyForecast] = field(default_factory=list)  # today + next 6 days
    # Extra fields needed by the Main Screen wireframe (wind direction, High / Low, icon).
    wind_direction: str = ""
    high_temp: Optional[float] = None
    low_temp: Optional[float] = None
    weather_code: int = 0
    is_day: bool = True
    # Which place this data is for (campus or the user's current location).
    location: str = "Denton, TX"
    timezone: str = "America/Chicago"

    def get_summary(self) -> str:
        return (
            f"{round(self.current_temp)}°F, {self.conditions}, "
            f"feels like {round(self.feels_like)}°F"
        )

    def to_dict(self) -> dict:
        return {
            "current_temp": self.current_temp,
            "feels_like": self.feels_like,
            "conditions": self.conditions,
            "precipitation_chance": self.precipitation_chance,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "humidity": self.humidity,
            "high_temp": self.high_temp,
            "low_temp": self.low_temp,
            "weather_code": self.weather_code,
            "is_day": self.is_day,
            "location": self.location,
            "timezone": self.timezone,
            "retrieved_at": _iso(self.retrieved_at),
            "summary": self.get_summary(),
            "hourly_forecast": [h.to_dict() for h in self.hourly_forecast],
            "daily_forecast": [d.to_dict() for d in self.daily_forecast],
        }


@dataclass
class Recommendation:
    message: str
    category: str  # e.g. "rain", "clothing", "wind", "safety"
    priority: int  # 1 = most important

    def to_dict(self) -> dict:
        return {"message": self.message, "category": self.category, "priority": self.priority}


@dataclass
class WeatherAlert:
    type: str  # e.g. "Heat Advisory"
    severity: str  # Extreme / Severe / Moderate / Minor / Unknown
    headline: str
    description: str
    expires_at: Optional[datetime]
    # Extra fields needed by the Alert Details wireframe ("Issued ...", "What to do").
    issued_at: Optional[datetime] = None
    instructions: List[str] = field(default_factory=list)
    source: str = "National Weather Service"

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "severity": self.severity,
            "headline": self.headline,
            "description": self.description,
            "expires_at": _iso(self.expires_at),
            "issued_at": _iso(self.issued_at),
            "instructions": list(self.instructions),
            "source": self.source,
        }
