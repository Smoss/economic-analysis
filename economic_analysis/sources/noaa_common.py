from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

STUDY_START = date(2016, 1, 1)
STUDY_END = date(2025, 12, 31)
BASELINE_END = date(2023, 12, 31)
RECENT_START = date(2024, 1, 1)
ISSUE_CYCLE = "12Z"
LEAD_DAYS = (1, 2, 3)
PRECIP_OCCURRENCE_THRESHOLD_IN = 0.01


@dataclass(frozen=True)
class WeatherStation:
    code: str
    station_id: str
    name: str
    latitude: float
    longitude: float
    state: str


NORTHEAST_AIRPORT_STATIONS: tuple[WeatherStation, ...] = (
    WeatherStation("BOS", "GHCND:USW00014739", "Boston Logan International Airport", 42.3606, -71.0097, "MA"),
    WeatherStation("BDL", "GHCND:USW00014740", "Bradley International Airport", 41.9389, -72.6832, "CT"),
    WeatherStation("JFK", "GHCND:USW00094789", "New York JFK International Airport", 40.6398, -73.7789, "NY"),
    WeatherStation("LGA", "GHCND:USW00014732", "New York LaGuardia Airport", 40.7794, -73.8803, "NY"),
    WeatherStation("EWR", "GHCND:USW00014734", "Newark Liberty International Airport", 40.6825, -74.1694, "NJ"),
    WeatherStation("PHL", "GHCND:USW00013739", "Philadelphia International Airport", 39.8683, -75.2311, "PA"),
    WeatherStation("PIT", "GHCND:USW00094823", "Pittsburgh International Airport", 40.4846, -80.2144, "PA"),
    WeatherStation("BUF", "GHCND:USW00014733", "Buffalo Niagara International Airport", 42.9405, -78.7322, "NY"),
    WeatherStation("BTV", "GHCND:USW00014742", "Burlington International Airport", 44.4719, -73.1533, "VT"),
    WeatherStation("PWM", "GHCND:USW00014764", "Portland International Jetport", 43.6462, -70.3093, "ME"),
    WeatherStation(
        "PVD",
        "GHCND:USW00014765",
        "Rhode Island T. F. Green International Airport",
        41.7225,
        -71.4325,
        "RI",
    ),
    WeatherStation("ALB", "GHCND:USW00014735", "Albany International Airport", 42.7481, -73.8037, "NY"),
    WeatherStation("SYR", "GHCND:USW00014771", "Syracuse Hancock International Airport", 43.1112, -76.1063, "NY"),
)


def station_codes() -> list[str]:
    return [station.code for station in NORTHEAST_AIRPORT_STATIONS]


def station_metadata() -> list[dict[str, str | float]]:
    return [
        {
            "code": station.code,
            "station_id": station.station_id,
            "name": station.name,
            "latitude": station.latitude,
            "longitude": station.longitude,
            "state": station.state,
        }
        for station in NORTHEAST_AIRPORT_STATIONS
    ]


def station_by_id() -> dict[str, WeatherStation]:
    return {station.station_id: station for station in NORTHEAST_AIRPORT_STATIONS}


def station_by_code() -> dict[str, WeatherStation]:
    return {station.code: station for station in NORTHEAST_AIRPORT_STATIONS}


def period_bucket(value: date | str) -> Literal["baseline_2016_2023", "recent_2024_2025"]:
    parsed = date.fromisoformat(value) if isinstance(value, str) else value
    if parsed >= RECENT_START:
        return "recent_2024_2025"
    return "baseline_2016_2023"
