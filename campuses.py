"""
UNT locations the user can pick from (UC-03 Choose Location).

Coordinates are approximate campus centers - close enough for weather,
which is forecast on a grid a few kilometers wide.
"""

from __future__ import annotations

from typing import Optional

CAMPUSES = [
    # University of North Texas
    {
        "id": "denton-main",
        "name": "UNT Denton – Main Campus",
        "short": "Denton, TX",
        "group": "UNT campuses",
        "latitude": 33.2107,
        "longitude": -97.1477,
    },
    {
        "id": "discovery-park",
        "name": "UNT Discovery Park (Denton)",
        "short": "Discovery Park",
        "group": "UNT campuses",
        "latitude": 33.2537,
        "longitude": -97.1525,
    },
    {
        "id": "frisco-landing",
        "name": "UNT at Frisco – Frisco Landing",
        "short": "Frisco Landing",
        "group": "UNT campuses",
        "latitude": 33.1985,
        "longitude": -96.8049,
    },
    {
        "id": "inspire-park",
        "name": "UNT at Frisco – Inspire Park",
        "short": "Inspire Park",
        "group": "UNT campuses",
        "latitude": 33.1046,
        "longitude": -96.8298,
    },
    # Other UNT System universities
    {
        "id": "unt-dallas",
        "name": "UNT Dallas",
        "short": "UNT Dallas",
        "group": "UNT System",
        "latitude": 32.6705,
        "longitude": -96.7943,
    },
    {
        "id": "unt-dallas-law",
        "name": "UNT Dallas College of Law (Downtown)",
        "short": "UNT Dallas Law",
        "group": "UNT System",
        "latitude": 32.7797,
        "longitude": -96.7979,
    },
    {
        "id": "unt-health-fort-worth",
        "name": "UNT Health Fort Worth",
        "short": "UNT Health FW",
        "group": "UNT System",
        "latitude": 32.7499,
        "longitude": -97.3690,
    },
]

DEFAULT_CAMPUS_ID = "denton-main"


def get_campus(campus_id: Optional[str]) -> Optional[dict]:
    for campus in CAMPUSES:
        if campus["id"] == campus_id:
            return campus
    return None


def campus_groups() -> list:
    """[(group name, [campuses...]), ...] in display order."""
    groups: dict = {}
    for campus in CAMPUSES:
        groups.setdefault(campus["group"], []).append(campus)
    return list(groups.items())
