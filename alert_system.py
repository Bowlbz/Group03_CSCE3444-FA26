"""
AlertSystem - manages the active WeatherAlert objects for hazards.

evaluate(data, api_alerts) combines:
  * official National Weather Service alerts (api_alerts), and
  * forecast-based cautions the app derives itself from WeatherData
    (heat, freeze, thunderstorms, high wind) when NWS has not already
    issued an alert of that kind.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from .models import THUNDERSTORM_CODES, WeatherAlert, WeatherData

SEVERITY_RANK = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3, "Unknown": 4}
APP_SOURCE = "Mean Green Weather (based on forecast)"


class AlertSystem:
    def __init__(
        self,
        heat_index_threshold: float = 105.0,  # °F feels-like
        freeze_threshold: float = 32.0,  # °F
        high_wind_threshold: float = 30.0,  # mph
        lookahead_hours: int = 12,
        storm_lookahead_hours: int = 6,
    ):
        self._active_alerts: List[WeatherAlert] = []
        self._heat_index_threshold = heat_index_threshold
        self._freeze_threshold = freeze_threshold
        self._high_wind_threshold = high_wind_threshold
        self._lookahead_hours = lookahead_hours
        self._storm_lookahead_hours = storm_lookahead_hours

    # ------------------------------------------------------------------ #
    # Public methods (class diagram)
    # ------------------------------------------------------------------ #
    def evaluate(self, data: WeatherData, api_alerts: Optional[List[WeatherAlert]]) -> None:
        self._active_alerts = []
        for alert in api_alerts or []:
            self.trigger_alert(alert)

        official = " ".join(a.type.lower() for a in self._active_alerts)
        for keyword, alert in self._derive_alerts(data):
            if keyword not in official:
                self.trigger_alert(alert)

        self.clear_expired()

    def trigger_alert(self, alert: WeatherAlert) -> None:
        for existing in self._active_alerts:
            if existing.type == alert.type and existing.headline == alert.headline:
                return
        self._active_alerts.append(alert)

    def get_active_alerts(self) -> List[WeatherAlert]:
        self.clear_expired()
        return sorted(self._active_alerts, key=lambda a: SEVERITY_RANK.get(a.severity, 4))

    def clear_expired(self) -> None:
        now = datetime.now(timezone.utc)
        self._active_alerts = [
            a for a in self._active_alerts if a.expires_at is None or a.expires_at > now
        ]

    # ------------------------------------------------------------------ #
    # Forecast-based cautions
    # ------------------------------------------------------------------ #
    def _derive_alerts(self, data: WeatherData):
        hours = data.hourly_forecast[: self._lookahead_hours]
        now = data.retrieved_at
        place = data.location or "your area"

        def until(matching) -> datetime:
            return matching[-1].time + timedelta(hours=1) if matching else now + timedelta(hours=3)

        hot = [h for h in hours if h.temperature >= 100]
        if data.feels_like >= self._heat_index_threshold or hot:
            yield "heat", WeatherAlert(
                type="Heat Caution",
                severity="Moderate",
                headline=f"Dangerous heat expected near {place}",
                description=(
                    f"It feels like {round(data.feels_like)}°F right now"
                    + (f", with temperatures reaching {round(max(h.temperature for h in hot))}°F." if hot else ".")
                ),
                expires_at=until(hot),
                issued_at=now,
                instructions=[
                    "Drink plenty of water",
                    "Limit time outdoors between classes",
                    "Check on others who may be at risk",
                ],
                source=APP_SOURCE,
            )

        cold = [h for h in hours if h.temperature <= self._freeze_threshold]
        if cold:
            yield "freeze", WeatherAlert(
                type="Freeze Caution",
                severity="Minor",
                headline=f"Freezing temperatures expected near {place}",
                description=f"Temperatures drop to {round(min(h.temperature for h in cold))}°F.",
                expires_at=until(cold),
                issued_at=now,
                instructions=[
                    "Wear warm layers, gloves and a hat",
                    "Watch for icy sidewalks, steps and bridges",
                    "Allow extra time to get to class",
                ],
                source=APP_SOURCE,
            )

        storms = [
            h for h in data.hourly_forecast[: self._storm_lookahead_hours]
            if h.weather_code in THUNDERSTORM_CODES
        ]
        if storms:
            yield "thunderstorm", WeatherAlert(
                type="Thunderstorms Possible",
                severity="Moderate",
                headline=f"Thunderstorms in the forecast near {place}",
                description=f"Thunderstorms are forecast starting around {storms[0].time.strftime('%I:%M %p').lstrip('0')}.",
                expires_at=until(storms),
                issued_at=now,
                instructions=[
                    "Go indoors when you hear thunder",
                    "Plan indoor routes between buildings",
                    "Avoid open areas and tall isolated objects",
                ],
                source=APP_SOURCE,
            )

        if data.wind_speed >= self._high_wind_threshold:
            yield "wind", WeatherAlert(
                type="High Wind Caution",
                severity="Minor",
                headline=f"Strong winds near {place}",
                description=f"Winds around {round(data.wind_speed)} mph {data.wind_direction}.".strip(),
                expires_at=now + timedelta(hours=3),
                issued_at=now,
                instructions=[
                    "Secure loose items and papers",
                    "Use caution when biking or on a scooter",
                ],
                source=APP_SOURCE,
            )
