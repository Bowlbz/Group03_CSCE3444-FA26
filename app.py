"""
Mean Green Weather - Flask app (CSCE 3444 Team #03)

Live weather for UNT students, faculty and staff: current conditions,
hourly forecast, recommendations and hazard alerts for any UNT campus
or the user's current location.

Run:
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000 in your browser.
"""

from flask import Flask, jsonify, render_template, request

from backend import DEFAULT_CAMPUS_ID, MainScreenUI, campus_groups, get_campus

app = Flask(__name__)

# One app controller for the running app. Data is held in memory only.
main_screen = MainScreenUI()


def location_from_request():
    """
    Read the chosen location from the query string:
        ?campus=<campus id>        a UNT campus (see backend/campuses.py)
        ?lat=<lat>&lon=<lon>       the device's current location
    Returns (location dict, error message).
    """
    lat, lon = request.args.get("lat"), request.args.get("lon")
    if lat is not None or lon is not None:
        try:
            lat_f, lon_f = float(lat), float(lon)
        except (TypeError, ValueError):
            return None, "lat and lon must both be numbers."
        if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
            return None, "lat/lon are out of range."
        return {"latitude": lat_f, "longitude": lon_f}, None

    campus_id = request.args.get("campus", DEFAULT_CAMPUS_ID)
    if not get_campus(campus_id):
        return None, f"Unknown campus '{campus_id}'."
    return {"campus": campus_id}, None


def respond(result):
    return jsonify(result), (200 if result["ok"] else 503)


def bad_request(message):
    return jsonify({"ok": False, "error_type": "bad_request", "message": message}), 400


@app.route("/")
def index():
    return render_template(
        "index.html", campus_groups=campus_groups(), default_campus=DEFAULT_CAMPUS_ID
    )


@app.get("/api/launch")
def launch():
    """UC-01 View Current Weather - called when the app opens."""
    location, error = location_from_request()
    return bad_request(error) if error else respond(main_screen.launch(location))


@app.post("/api/refresh")
def refresh():
    """UC-02 Refresh Information - called when the Update button is tapped."""
    location, error = location_from_request()
    return bad_request(error) if error else respond(main_screen.on_refresh_clicked(location))


@app.get("/api/location")
def select_location():
    """UC-03 Choose Location - a UNT campus or the user's current location."""
    location, error = location_from_request()
    return bad_request(error) if error else respond(main_screen.on_location_selected(location))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
