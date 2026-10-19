/*
 * Mean Green Weather - frontend (User Interface box in the architecture diagram)
 *
 * Screens (Section 4 wireframes):
 *   #now     Screen 1 - Main Screen: alert banner, current conditions,
 *            recommendations, next-hours preview
 *   #hourly  Screen 2 - Hourly Forecast: next 24 hours
 *   #alerts  Screen 3 - Alert Details: severity, timing, what to do
 *
 * Events go to the MainScreenUI controller in the Flask backend:
 *   GET  /api/launch    UC-01 View Current Weather (app opens)
 *   POST /api/refresh   UC-02 Refresh Information (Update button)
 *   GET  /api/location  UC-03 Choose Location (UNT campus or current location)
 * Each call carries ?campus=<id> or ?lat=<lat>&lon=<lon>.
 */
(function () {
  'use strict';

  var STORAGE_KEY = 'mgw-location';

  var ICONS = {
    0: '☀️', 1: '🌤️', 2: '⛅', 3: '☁️', 45: '🌫️', 48: '🌫️',
    51: '🌦️', 53: '🌦️', 55: '🌧️', 56: '🌧️', 57: '🌧️',
    61: '🌦️', 63: '🌧️', 65: '🌧️', 66: '🌧️', 67: '🌧️',
    71: '🌨️', 73: '🌨️', 75: '❄️', 77: '❄️',
    80: '🌦️', 81: '🌧️', 82: '⛈️', 85: '🌨️', 86: '❄️',
    95: '⛈️', 96: '⛈️', 99: '⛈️'
  };
  var NIGHT_ICONS = { 0: '🌙', 1: '🌙', 2: '☁️' };

  var TITLES = {
    now: 'Mean Green Weather',
    hourly: 'Hourly Forecast',
    week: '7-Day Forecast',
    alerts: 'Weather Alerts'
  };

  var phoneEl = document.querySelector('.phone');
  var DEFAULT_CAMPUS = phoneEl.getAttribute('data-default-campus') || 'denton-main';

  // In-memory app state (no database - SDD Section 5)
  var state = {
    screen: 'now',
    hourlyDay: null,        // null = next 24 hours, or a date like "2026-10-21"
    // What the user chose: { type: 'campus', id } or { type: 'current', lat, lon }
    location: { type: 'campus', id: DEFAULT_CAMPUS },
    place: null,            // place info returned by the backend
    tz: 'America/Chicago',  // time zone of the selected place
    weather: null,          // WeatherData
    recommendations: [],    // Recommendation[]
    alerts: [],             // WeatherAlert[]
    alertsChecked: true,
    lastUpdated: null,      // ISO string
    isLoading: false,
    error: null,            // { type, message }
    selectedAlert: 0
  };
  var requestSeq = 0;       // ignore responses from an older location choice
  var pendingNotice = null; // message to show once the next load succeeds

  var screenEl = document.getElementById('screen');
  var scrollEl = document.getElementById('scroll');
  var titleEl = document.getElementById('screenTitle');
  var backLink = document.getElementById('backLink');
  var updateBtn = document.getElementById('updateBtn');
  var lastUpdatedEl = document.getElementById('lastUpdated');
  var tabs = document.querySelectorAll('.tab-bar a');
  var locationBtn = document.getElementById('locationBtn');
  var locationLabel = document.getElementById('locationLabel');
  var sheet = document.getElementById('locationSheet');
  var sheetBackdrop = document.getElementById('sheetBackdrop');
  var sheetClose = document.getElementById('sheetClose');
  var currentSub = document.getElementById('currentSub');
  var locOptions = document.querySelectorAll('.loc-option');

  // ------------------------------------------------------------------ //
  // Formatting helpers
  // ------------------------------------------------------------------ //
  function esc(str) {
    var div = document.createElement('div');
    div.textContent = str == null ? '' : String(str);
    return div.innerHTML;
  }

  function deg(v) { return v == null ? '--' : Math.round(v) + '°'; }

  function icon(code, isDay) {
    if (isDay === false && NIGHT_ICONS[code]) return NIGHT_ICONS[code];
    return ICONS[code] || '🌡️';
  }

  function fmtHour(iso) {   // "1 PM"
    return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', timeZone: state.tz });
  }

  function fmtTime(iso) {   // "12:48 PM"
    return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: state.tz });
  }

  function fmtStamp(iso) {  // "Oct 5, 2026 12:48 PM"
    var d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: state.tz }) +
      ' ' + fmtTime(iso);
  }

  // Daily dates are plain "YYYY-MM-DD" in the location's local time.
  function dayName(dateStr, long) {   // "Wed" / "Wednesday"
    return new Date(dateStr + 'T12:00:00Z').toLocaleDateString('en-US',
      { weekday: long ? 'long' : 'short', timeZone: 'UTC' });
  }

  function monthDay(dateStr) {        // "Oct 21"
    return new Date(dateStr + 'T12:00:00Z').toLocaleDateString('en-US',
      { month: 'short', day: 'numeric', timeZone: 'UTC' });
  }

  function dayLabel(dateStr, long) {  // "Today" / "Tomorrow" / "Wed"
    var days = state.weather ? state.weather.daily_forecast : [];
    if (days[0] && days[0].date === dateStr) return 'Today';
    if (days[1] && days[1].date === dateStr) return 'Tomorrow';
    return dayName(dateStr, long);
  }

  function hourDate(h) { return h.time.slice(0, 10); } // local date of an hourly entry

  function sevClass(alert) { return 'sev-' + String(alert.severity || 'unknown').toLowerCase(); }

  function placeShort() {
    if (state.place) return state.place.short;
    if (state.location.type === 'current') return 'My location';
    var opt = document.querySelector('.loc-option[data-campus="' + state.location.id + '"]');
    return opt ? opt.getAttribute('data-short') : 'Denton, TX';
  }

  // ------------------------------------------------------------------ //
  // Saved location choice (per browser; falls back to Denton if storage is blocked)
  // ------------------------------------------------------------------ //
  function saveLocation() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(
        state.location.type === 'current' ? { type: 'current' } : state.location));
    } catch (e) { /* storage unavailable - not critical */ }
  }

  function readSavedLocation() {
    try {
      var saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
      if (saved && saved.type === 'current') return saved;
      if (saved && saved.type === 'campus' &&
          document.querySelector('.loc-option[data-campus="' + saved.id + '"]')) return saved;
    } catch (e) { /* ignore */ }
    return null;
  }

  // ------------------------------------------------------------------ //
  // Talking to the backend (MainScreenUI controller)
  // ------------------------------------------------------------------ //
  function locationQuery() {
    if (state.location.type === 'current') {
      return 'lat=' + encodeURIComponent(state.location.lat) + '&lon=' + encodeURIComponent(state.location.lon);
    }
    return 'campus=' + encodeURIComponent(state.location.id);
  }

  var ENDPOINTS = {
    launch: { url: '/api/launch', method: 'GET' },
    refresh: { url: '/api/refresh', method: 'POST' },
    location: { url: '/api/location', method: 'GET' }
  };

  function requestWeather(kind) {
    if (navigator.onLine === false) {
      return Promise.reject({ error_type: 'no_connection', message: 'No internet connection.' });
    }
    var ep = ENDPOINTS[kind];
    return fetch(ep.url + '?' + locationQuery(), { method: ep.method, cache: 'no-store' })
      .catch(function () {
        throw {
          error_type: 'server_unreachable',
          message: 'Could not reach the Mean Green Weather server. Make sure "python app.py" is running.'
        };
      }).then(function (res) {
        return res.json().catch(function () {
          throw { error_type: 'api_error', message: 'Weather data unavailable.' };
        }).then(function (body) {
          if (!res.ok || !body.ok) throw body;
          return body;
        });
      });
  }

  function load(kind) {
    var seq = ++requestSeq;
    state.isLoading = true;
    setUpdateButton();
    if (!state.weather) render(); // loading indicator

    requestWeather(kind).then(function (body) {
      if (seq !== requestSeq) return;
      state.place = body.location;
      state.tz = (body.weather && body.weather.timezone) || state.tz;
      state.weather = body.weather;
      state.recommendations = body.recommendations || [];
      state.alerts = body.alerts || [];
      state.alertsChecked = body.alerts_checked !== false;
      state.lastUpdated = body.last_updated;
      state.selectedAlert = 0;
      state.error = pendingNotice;
      pendingNotice = null;
    }).catch(function (err) {
      if (seq !== requestSeq) return;
      // Keep any previous data on screen; just show the error.
      state.error = {
        type: (err && err.error_type) || 'api_error',
        message: (err && err.message) || 'Weather data unavailable.'
      };
    }).then(function () {
      if (seq !== requestSeq) return;
      state.isLoading = false;
      setUpdateButton();
      render();
    });
  }

  // ------------------------------------------------------------------ //
  // Choosing a location (UC-03)
  // ------------------------------------------------------------------ //
  function applyLocation(location) {
    state.location = location;
    state.place = null;
    // New place: clear the old place's data so it's never shown under the new name.
    state.weather = null;
    state.recommendations = [];
    state.alerts = [];
    state.lastUpdated = null;
    state.error = null;
    saveLocation();
    load('location');
  }

  function useCurrentLocation(onFail) {
    if (!navigator.geolocation) {
      onFail('Your browser does not support location. Pick a UNT campus instead.');
      return;
    }
    currentSub.textContent = 'Finding your location…';
    navigator.geolocation.getCurrentPosition(function (pos) {
      currentSub.textContent = "Uses your device's location";
      applyLocation({
        type: 'current',
        lat: pos.coords.latitude.toFixed(4),
        lon: pos.coords.longitude.toFixed(4)
      });
    }, function (err) {
      currentSub.textContent = "Uses your device's location";
      onFail(err && err.code === 1
        ? 'Location access is blocked. Allow location for this site in your browser, or pick a UNT campus.'
        : 'Could not find your location. Try again or pick a UNT campus.');
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 });
  }

  function showLocationError(message) {
    state.error = { type: 'location', message: message };
    render();
  }

  function openSheet() {
    locOptions.forEach(function (opt) {
      var selected = state.location.type === 'current'
        ? opt.hasAttribute('data-current')
        : opt.getAttribute('data-campus') === state.location.id;
      opt.classList.toggle('selected', selected);
      opt.setAttribute('aria-pressed', selected ? 'true' : 'false');
    });
    sheet.hidden = false;
    sheetBackdrop.hidden = false;
    locationBtn.setAttribute('aria-expanded', 'true');
    var sel = sheet.querySelector('.loc-option.selected') || locOptions[0];
    sel.focus();
  }

  function closeSheet() {
    sheet.hidden = true;
    sheetBackdrop.hidden = true;
    locationBtn.setAttribute('aria-expanded', 'false');
    locationBtn.focus();
  }

  // ------------------------------------------------------------------ //
  // UI pieces
  // ------------------------------------------------------------------ //
  function renderErrorBox() {
    if (!state.error) return '';
    var title;
    var msg = state.error.message;
    if (state.error.type === 'location') {
      title = 'Location unavailable';
    } else {
      title = state.error.type === 'no_connection' ? 'No connection' :
        (state.weather ? 'Update failed' : 'Weather unavailable');
      if (state.weather && state.lastUpdated) {
        msg += ' Showing data from ' + fmtTime(state.lastUpdated) + '.';
      }
      msg += ' Tap Update to try again.';
    }
    return '<div class="error-box" role="alert"><p class="error-title">' + esc(title) + '</p>' +
      '<p>' + esc(msg) + '</p></div>';
  }

  function renderAlertBanner() {
    if (!state.alerts.length) return '';
    var a = state.alerts[0];
    var until = a.expires_at ? ' until ' + fmtTime(a.expires_at) : '';
    var more = state.alerts.length > 1 ? ' (+' + (state.alerts.length - 1) + ' more)' : '';
    return '<a class="alert-banner ' + sevClass(a) + '" href="#alerts">' +
      '<strong>! ' + esc(a.type) + '</strong>' + esc(until) + esc(more) +
      ' <span class="details">Details &gt;</span></a>';
  }

  function renderCurrentConditions() {
    var w = state.weather;
    var wind = Math.round(w.wind_speed) + ' mph' + (w.wind_direction ? ' ' + w.wind_direction : '');
    return '<section class="card">' +
      '<h2 class="card-title">Current conditions</h2>' +
      '<div class="current-main">' +
      '  <div class="current-icon" aria-hidden="true">' + icon(w.weather_code, w.is_day) + '</div>' +
      '  <div class="current-temp">' + deg(w.current_temp) + 'F</div>' +
      '</div>' +
      '<p class="current-desc">' + esc(w.conditions) + ' · Feels like ' + deg(w.feels_like) + '</p>' +
      '<div class="stat-grid">' +
      '  <div>Rain chance: <b>' + w.precipitation_chance + '%</b></div>' +
      '  <div>Wind: <b>' + esc(wind) + '</b></div>' +
      '  <div>Humidity: <b>' + w.humidity + '%</b></div>' +
      '  <div>High / Low: <b>' + deg(w.high_temp) + ' / ' + deg(w.low_temp) + '</b></div>' +
      '</div>' +
      '</section>';
  }

  function renderRecommendationsPanel() {
    var items = state.recommendations.map(function (r) {
      return '<li>' + esc(r.message) + '</li>';
    }).join('');
    return '<section class="card">' +
      '<h2 class="card-title">Recommendations</h2>' +
      (items ? '<ul class="bullets">' + items + '</ul>' : '<p class="muted">No recommendations right now.</p>') +
      '</section>';
  }

  function renderNextHours() {
    var hours = state.weather.hourly_forecast.slice(1, 5); // the next 4 hours
    if (!hours.length) hours = state.weather.hourly_forecast.slice(0, 4);
    var cols = hours.map(function (h) {
      return '<div><div>' + esc(fmtHour(h.time)).replace(' ', '') + '</div>' +
        '<div class="hr-temp">' + deg(h.temperature) + '</div>' +
        '<div>' + h.precipitation_chance + '%</div></div>';
    }).join('');
    return '<section class="card">' +
      '<h2 class="card-title">Next hours</h2>' +
      '<div class="next-hours">' + cols + '</div>' +
      '<a class="card-link" href="#hourly">See hourly &gt;</a>' +
      '</section>';
  }

  function renderThisWeek() {
    var days = state.weather.daily_forecast.slice(0, 3);
    if (!days.length) return '';
    var rows = days.map(function (d) {
      return '<a class="mini-day" href="#hourly/' + esc(d.date) + '">' +
        '<span class="mini-name">' + esc(dayLabel(d.date)) + '</span>' +
        '<span class="mini-icon" aria-hidden="true">' + icon(d.weather_code) + '</span>' +
        '<span class="mini-rain">' + d.precipitation_chance + '%</span>' +
        '<span class="mini-temps"><b>' + deg(d.high_temp) + '</b> / ' + deg(d.low_temp) + '</span>' +
        '</a>';
    }).join('');
    return '<section class="card">' +
      '<h2 class="card-title">This week</h2>' + rows +
      '<a class="card-link" href="#week">See 7-day &gt;</a>' +
      '</section>';
  }

  // Screen 1 - Main Screen
  function renderMainScreen() {
    return renderAlertBanner() + renderErrorBox() + renderCurrentConditions() +
      renderRecommendationsPanel() + renderNextHours() + renderThisWeek();
  }

  // Day picker for the Hourly screen: Next 24 hrs | Today | Tomorrow | Wed | ...
  function renderDayChips() {
    var chips = '<a class="chip' + (state.hourlyDay ? '' : ' active') + '" href="#hourly">Next 24 hrs</a>';
    state.weather.daily_forecast.forEach(function (d) {
      var hasHours = state.weather.hourly_forecast.some(function (h) { return hourDate(h) === d.date; });
      if (!hasHours) return;
      chips += '<a class="chip' + (state.hourlyDay === d.date ? ' active' : '') + '" href="#hourly/' +
        esc(d.date) + '">' + esc(dayLabel(d.date)) + '</a>';
    });
    return '<nav class="day-chips" aria-label="Choose a day">' + chips + '</nav>';
  }

  function hoursForSelectedDay() {
    var all = state.weather.hourly_forecast;
    if (!state.hourlyDay) return all.slice(0, 24);
    return all.filter(function (h) { return hourDate(h) === state.hourlyDay; });
  }

  function renderDaySummary() {
    if (!state.hourlyDay) return '';
    var d = state.weather.daily_forecast.filter(function (x) { return x.date === state.hourlyDay; })[0];
    if (!d) return '';
    return '<p class="day-summary"><b>' + esc(dayLabel(d.date, true)) + ', ' + esc(monthDay(d.date)) + '</b> · ' +
      esc(d.conditions) + ' · High ' + deg(d.high_temp) + ' / Low ' + deg(d.low_temp) +
      ' · Rain ' + d.precipitation_chance + '%</p>';
  }

  // Screen 2 - Hourly Forecast View
  function renderHourlyForecastView() {
    var hours = hoursForSelectedDay();
    var rows = hours.map(function (h) {
      return '<tr>' +
        '<td>' + esc(fmtHour(h.time)) + '</td>' +
        '<td class="temp">' + deg(h.temperature) + '</td>' +
        '<td><span class="cond-icon" aria-hidden="true">' + icon(h.weather_code) + '</span>' + esc(h.conditions) + '</td>' +
        '<td class="rain">' + h.precipitation_chance + '%</td>' +
        '</tr>';
    }).join('');
    return renderErrorBox() + renderDayChips() + renderDaySummary() +
      '<section class="card hourly-card">' +
      (rows
        ? '<table class="hourly-table">' +
          '<thead><tr><th>TIME</th><th>TEMP</th><th>CONDITIONS</th><th class="rain">RAIN</th></tr></thead>' +
          '<tbody>' + rows + '</tbody></table>'
        : '<p class="muted" style="padding:10px 4px">No hourly forecast for this day.</p>') +
      '</section>';
  }

  // Screen - 7-Day Forecast: Today, Tomorrow, Wed, Thu, ...
  function renderWeekView() {
    var days = state.weather.daily_forecast;
    var lo = Math.min.apply(null, days.map(function (d) { return d.low_temp; }));
    var hi = Math.max.apply(null, days.map(function (d) { return d.high_temp; }));
    var span = Math.max(hi - lo, 1);
    var rows = days.map(function (d) {
      var left = ((d.low_temp - lo) / span) * 100;
      var width = Math.max(((d.high_temp - d.low_temp) / span) * 100, 4);
      return '<a class="week-row" href="#hourly/' + esc(d.date) + '">' +
        '<span class="week-day"><b>' + esc(dayLabel(d.date)) + '</b>' +
        '<span class="week-date">' + esc(monthDay(d.date)) + '</span></span>' +
        '<span class="week-icon" aria-hidden="true">' + icon(d.weather_code) + '</span>' +
        '<span class="week-mid"><span class="week-cond">' +
        esc(d.conditions.replace('Thunderstorms', 'T-storms')) + '</span>' +
        '<span class="week-rain">💧 ' + d.precipitation_chance + '%</span></span>' +
        '<span class="week-temps"><span class="week-lo">' + deg(d.low_temp) + '</span>' +
        '<span class="range" aria-hidden="true"><span style="left:' + left.toFixed(1) + '%;width:' +
        width.toFixed(1) + '%"></span></span>' +
        '<span class="week-hi">' + deg(d.high_temp) + '</span></span>' +
        '<span class="week-go" aria-hidden="true">&gt;</span>' +
        '</a>';
    }).join('');
    return renderErrorBox() +
      '<section class="card week-card">' + rows + '</section>' +
      '<p class="hint">Tap a day to see its hourly forecast.</p>';
  }

  // Screen 3 - Alert Details
  function renderAlertDetails() {
    var html = '';
    var where = placeShort();
    if (!state.alerts.length) {
      html += '<section class="card">' +
        '<h2 class="card-title">Active alerts</h2>' +
        '<p class="muted">No active weather alerts for ' + esc(where) + ' right now.</p>' +
        '</section>';
    } else {
      var idx = Math.min(state.selectedAlert, state.alerts.length - 1);
      var a = state.alerts[idx];
      var times = [];
      if (a.issued_at) times.push('Issued ' + fmtTime(a.issued_at));
      if (a.expires_at) times.push('Expires ' + fmtTime(a.expires_at));

      html += '<section class="card alert-detail ' + sevClass(a) + '">' +
        '<p class="severity">Severity: ' + esc(a.severity) + '</p>' +
        '<h2 class="alert-title">' + esc(a.type) + '</h2>' +
        (times.length ? '<p class="alert-times">' + esc(times.join(' · ')) + '</p>' : '') +
        '<p class="alert-desc">' + esc(a.description || a.headline) + '</p>' +
        '<p class="alert-source">Source: ' + esc(a.source) + '</p>' +
        '</section>';

      if (a.instructions && a.instructions.length) {
        html += '<section class="card"><h2 class="card-title">What to do</h2><ul class="bullets">' +
          a.instructions.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') +
          '</ul></section>';
      }

      var others = state.alerts.map(function (o, i) { return { alert: o, i: i }; })
        .filter(function (x) { return x.i !== idx; });
      html += '<section class="card"><h2 class="card-title">Other active alerts</h2>' +
        (others.length ? others.map(function (x) {
          var until = x.alert.expires_at ? ' until ' + fmtTime(x.alert.expires_at) : '';
          return '<button type="button" class="other-alert" data-alert="' + x.i + '">' +
            '<strong>' + esc(x.alert.type) + '</strong>' + esc(until) +
            ' <span class="details">Details &gt;</span></button>';
        }).join('') : '<p class="muted">No other alerts for ' + esc(where) + ' right now.</p>') +
        '</section>';
    }

    if (!state.alertsChecked) {
      html += '<section class="card"><p class="muted">Could not check National Weather Service alerts. ' +
        'Showing forecast-based alerts only.</p></section>';
    }

    return renderErrorBox() + html;
  }

  function renderLoading() {
    return '<div class="loading" role="status"><div class="spinner"></div>' +
      '<p>Loading ' + esc(placeShort()) + ' weather…</p></div>';
  }

  // ------------------------------------------------------------------ //
  // Screen switching / rendering
  // ------------------------------------------------------------------ //
  function setUpdateButton() {
    updateBtn.disabled = state.isLoading;
    updateBtn.classList.toggle('loading', state.isLoading);
    updateBtn.setAttribute('aria-busy', state.isLoading ? 'true' : 'false');
    lastUpdatedEl.textContent = state.lastUpdated
      ? 'Last updated: ' + fmtStamp(state.lastUpdated)
      : (state.isLoading ? 'Updating…' : 'Not updated yet');
  }

  function render() {
    titleEl.textContent = (state.screen === 'hourly' && state.hourlyDay && state.weather)
      ? 'Hourly · ' + dayLabel(state.hourlyDay)
      : TITLES[state.screen];
    backLink.hidden = state.screen === 'now';

    var label = placeShort();
    locationLabel.textContent = (state.location.type === 'current' ? '📍 ' : '') + label;
    locationBtn.title = 'Change location (now: ' + (state.place ? state.place.name : label) + ')';

    tabs.forEach(function (t) {
      var tab = t.getAttribute('data-tab');
      t.classList.toggle('active', tab === state.screen);
      t.innerHTML = tab.charAt(0).toUpperCase() + tab.slice(1) +
        (tab === 'alerts' && state.alerts.length ? '<span class="badge">' + state.alerts.length + '</span>' : '');
    });

    if (!state.weather) {
      screenEl.innerHTML = state.isLoading ? renderLoading() : renderErrorBox();
      return;
    }

    if (state.screen === 'hourly') {
      screenEl.innerHTML = renderHourlyForecastView();
      var activeChip = screenEl.querySelector('.chip.active');
      if (activeChip) {
        var bar = activeChip.parentNode;
        bar.scrollLeft += activeChip.getBoundingClientRect().left - bar.getBoundingClientRect().left - 40;
      }
    }
    else if (state.screen === 'week') screenEl.innerHTML = renderWeekView();
    else if (state.screen === 'alerts') screenEl.innerHTML = renderAlertDetails();
    else screenEl.innerHTML = renderMainScreen();
  }

  function onRoute() {
    // "#now", "#week", "#alerts", "#hourly" or "#hourly/2026-10-21"
    var parts = (location.hash || '#now').slice(1).split('/');
    state.screen = TITLES[parts[0]] ? parts[0] : 'now';
    state.hourlyDay = (state.screen === 'hourly' && /^\d{4}-\d{2}-\d{2}$/.test(parts[1] || '')) ? parts[1] : null;
    render();
    scrollEl.scrollTop = 0;
  }

  // ------------------------------------------------------------------ //
  // Events
  // ------------------------------------------------------------------ //
  updateBtn.addEventListener('click', function () { load('refresh'); });   // UC-02

  locationBtn.addEventListener('click', openSheet);
  sheetClose.addEventListener('click', closeSheet);
  sheetBackdrop.addEventListener('click', closeSheet);
  sheet.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSheet(); });

  locOptions.forEach(function (opt) {
    opt.addEventListener('click', function () {                            // UC-03
      if (opt.hasAttribute('data-current')) {
        useCurrentLocation(function (msg) { closeSheet(); showLocationError(msg); });
        closeSheet();
      } else {
        closeSheet();
        var id = opt.getAttribute('data-campus');
        if (state.location.type === 'campus' && state.location.id === id && state.weather) return;
        applyLocation({ type: 'campus', id: id });
      }
    });
  });

  screenEl.addEventListener('click', function (e) {
    var btn = e.target.closest('.other-alert');
    if (!btn) return;
    state.selectedAlert = parseInt(btn.getAttribute('data-alert'), 10) || 0;
    render();
    scrollEl.scrollTop = 0;
  });

  window.addEventListener('hashchange', onRoute);

  // UC-01: app opens -> load weather for the saved choice (default: Denton main campus)
  onRoute();
  setUpdateButton();
  var saved = readSavedLocation();
  if (saved && saved.type === 'current') {
    state.isLoading = true;
    render();
    useCurrentLocation(function (msg) {
      // Couldn't get the device location - fall back to the default campus.
      state.isLoading = false;
      state.location = { type: 'campus', id: DEFAULT_CAMPUS };
      pendingNotice = { type: 'location', message: msg + ' Showing the Denton main campus instead.' };
      load('launch');
    });
  } else {
    if (saved) state.location = saved;
    load('launch');
  }
})();
