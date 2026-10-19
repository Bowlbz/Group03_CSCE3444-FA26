# Mean Green Weather (Flask)

CSCE 3444 Software Engineering, Team #03.

Live weather for UNT students, faculty and staff. The app opens straight to
current conditions (no login or search) for the Denton main campus, or for
whichever UNT campus or current location the user last picked. It also shows
plain-language recommendations, hazard alerts, an hourly forecast, a
7-day forecast, and an **Update** button with a "Last updated" time.

Data sources (both free, no API key):
- Forecast: [Open-Meteo](https://open-meteo.com)
- Severe weather alerts: [National Weather Service API](https://www.weather.gov/documentation/services-web-api)

## Run it (VS Code)

```bash
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5000**. Your machine needs internet access.

## Project layout → Software Design Document

```
weather-flask-app/
├── app.py                         # Flask routes: /, /api/launch (UC-01), /api/refresh (UC-02), /api/location (UC-03)
├── backend/                       # "Application Logic / Backend (Python)"
│   ├── main_screen_ui.py          # MainScreenUI - app controller
│   ├── weather_api_client.py      # WeatherAPIClient
│   ├── models.py                  # WeatherData, HourlyForecast, Recommendation, WeatherAlert
│   ├── recommendation_program.py  # RecommendationProgram
│   ├── alert_system.py            # AlertSystem
│   └── campuses.py                # UNT campus list for the location picker
├── static/                        # "User Interface / Frontend"
│   ├── app.js                     # Main Screen, Hourly Forecast View, Recommendations Panel,
│   │                              # Alert Banner / Alert Details, error messages
│   └── style.css
└── templates/
    └── index.html
```

| Class diagram | Code |
|---|---|
| MainScreenUI: `launch()`, `onRefreshClicked()`, `displayWeather()`, `displayRecommendations()`, `displayAlerts()`, `showError()` | `backend/main_screen_ui.py` (same methods, Python naming) |
| WeatherAPIClient: `checkConnection()`, `fetchCurrentWeather()`, `fetchHourlyForecast()`, `fetchDailyForecast()`, `fetchAlerts()`, `parseResponse()`; `location = "Denton, TX"`, `timeoutSeconds` | `backend/weather_api_client.py` |
| WeatherData (+ `getSummary()`), HourlyForecast, DailyForecast, Recommendation, WeatherAlert | `backend/models.py` |
| RecommendationProgram: `generate()`, `needsUmbrella()`, `suggestClothing()`; umbrella / cold / heat thresholds | `backend/recommendation_program.py` |
| AlertSystem: `evaluate(data, apiAlerts)`, `triggerAlert()`, `getActiveAlerts()`, `clearExpired()` | `backend/alert_system.py` |

### Use cases

- **UC-01 View Current Weather:** the page loads, shows a loading
  indicator and calls `GET /api/launch`. Then `MainScreenUI.launch()` runs
  `check_connection()`, `fetch_current_weather()`, `fetch_alerts()`,
  `RecommendationProgram.generate()` and `AlertSystem.evaluate()`, and returns
  everything with the "Last updated" time. On API error, timeout or no
  connection, the app shows a clear message and the user can tap Update.
- **UC-02 Refresh Information:** the Update button sends `POST /api/refresh`
  and is disabled with a spinning icon while it loads. Recommendations and
  alerts are recalculated and "Last updated" is set to now. If the update
  fails, the old data stays on screen with an "Update failed … Showing data
  from <time>" message, and the button is re-enabled.

- **UC-03 Choose Location:** tap the location button in the header (e.g.
  "Denton, TX ▾") to open the picker. It offers **Use my current location**
  (browser geolocation; the city name comes from the National Weather
  Service) or one of these:
  - UNT campuses: Denton Main Campus, Discovery Park, Frisco Landing,
    Inspire Park
  - UNT System: UNT Dallas, UNT Dallas College of Law, UNT Health Fort Worth

  This calls `GET /api/location?campus=<id>` or `?lat=..&lon=..`, which runs
  `MainScreenUI.on_location_selected()` → `WeatherAPIClient.set_location()`.
  The browser remembers the choice for next time. If location access is
  blocked, the app shows a message and falls back to the Denton main campus.
  To add or edit campuses, change `backend/campuses.py`.

### Screens (Section 4 wireframes)

- `#now`: Main Screen with the alert banner, current conditions,
  recommendations, the next 4 hours and "See hourly >".
- `#hourly`: Hourly Forecast table (Time / Temp / Conditions / Rain). Day
  buttons at the top switch between **Next 24 hrs**, **Today**,
  **Tomorrow**, **Wed**, **Thu** and so on (`#hourly/2026-10-21`).
- `#week`: 7-Day Forecast for Today, Tomorrow and the next 5 days, with
  conditions, rain chance and a high/low bar. Tap a day to see its hours.
  The main screen also has a **This week** card with the next 3 days.
- `#alerts`: Alert Details with severity, issued/expires times, description,
  What to do, and Other active alerts.

### No database (Section 5)

All weather data is held in memory as objects while the app runs. The only
thing saved is the user's location choice, in the browser's localStorage.

## Tuning

- Recommendation thresholds: `RecommendationProgram(umbrella_threshold=40, cold_threshold=50, heat_threshold=90)`
- Forecast-based alert thresholds: `AlertSystem(heat_index_threshold=105, freeze_threshold=32, high_wind_threshold=30)`
- Campuses and the default campus: `backend/campuses.py`
- Number of forecast days: `WeatherAPIClient(days_ahead=7)` (Open-Meteo allows up to 16)
