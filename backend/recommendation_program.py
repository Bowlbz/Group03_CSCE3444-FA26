"""
RecommendationProgram - turns WeatherData into plain-language advice
for UNT students (e.g. "Bring an umbrella").
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from .models import THUNDERSTORM_CODES, HourlyForecast, Recommendation, WeatherData


def hour_label(dt: datetime) -> str:
    """'3 PM' (works on Windows, unlike strftime('%-I'))."""
    return f"{dt.hour % 12 or 12} {'AM' if dt.hour < 12 else 'PM'}"


class RecommendationProgram:
    def __init__(
        self,
        umbrella_threshold: int = 40,  # % rain chance
        cold_threshold: float = 50.0,  # °F feels-like
        heat_threshold: float = 90.0,  # °F feels-like
        lookahead_hours: int = 12,
        windy_threshold: float = 20.0,  # mph
    ):
        self._umbrella_threshold = umbrella_threshold
        self._cold_threshold = cold_threshold
        self._heat_threshold = heat_threshold
        self._lookahead_hours = lookahead_hours
        self._windy_threshold = windy_threshold

    # ------------------------------------------------------------------ #
    def generate(self, data: WeatherData) -> List[Recommendation]:
        recs: List[Recommendation] = []

        if self.needs_umbrella(data):
            hour = self._first_rainy_hour(data)
            if hour is None or hour is data.hourly_forecast[0]:
                pct = hour.precipitation_chance if hour else data.precipitation_chance
                msg = f"Bring an umbrella – {pct}% chance of rain right now"
            else:
                msg = (
                    f"Bring an umbrella – {hour.precipitation_chance}% chance of rain "
                    f"from {hour_label(hour.time)}"
                )
            recs.append(Recommendation(msg, "rain", 1))

        if any(h.weather_code in THUNDERSTORM_CODES for h in self._upcoming(data)):
            recs.append(
                Recommendation(
                    "Thunderstorms possible – plan indoor routes between classes",
                    "safety",
                    1,
                )
            )

        recs.append(Recommendation(self.suggest_clothing(data), "clothing", 2))

        if data.wind_speed >= self._windy_threshold:
            recs.append(
                Recommendation(
                    f"Windy ({round(data.wind_speed)} mph) – hold on to papers and loose items",
                    "wind",
                    3,
                )
            )

        return sorted(recs, key=lambda r: r.priority)

    def needs_umbrella(self, data: WeatherData) -> bool:
        return self._first_rainy_hour(data) is not None or (
            data.precipitation_chance >= self._umbrella_threshold
        )

    def suggest_clothing(self, data: WeatherData) -> str:
        feels = data.feels_like
        temps = [h.temperature for h in self._upcoming(data)] or [data.current_temp]
        if feels >= self._heat_threshold:
            return "Wear light clothing, stay hydrated"
        if feels <= 32:
            return "Bundle up – heavy coat, gloves and a hat"
        if feels <= self._cold_threshold:
            return "Wear a jacket or a warm layer"
        if max(temps) - min(temps) >= 15:
            return (
                f"Dress in layers – {round(min(temps))}° to {round(max(temps))}° "
                f"over the next {self._lookahead_hours} hours"
            )
        return "Comfortable weather – regular clothes are fine"

    # ------------------------------------------------------------------ #
    def _upcoming(self, data: WeatherData) -> List[HourlyForecast]:
        return data.hourly_forecast[: self._lookahead_hours]

    def _first_rainy_hour(self, data: WeatherData) -> Optional[HourlyForecast]:
        for h in self._upcoming(data):
            if h.precipitation_chance >= self._umbrella_threshold:
                return h
        return None
