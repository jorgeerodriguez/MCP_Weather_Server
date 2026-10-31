from urllib.parse import urlencode

import httpx
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("weather")

BASE_URL = "https://api.weather.gov"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

STATE_CODES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee",
    "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia",
    "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}
STATE_ABBREVIATIONS = {name: code for code, name in STATE_CODES.items()}


async def fetch(url: str) -> dict | None:
    """Make an async GET request and return JSON, or None on failure."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                url,
                timeout=10,
                headers={"User-Agent": "mcp-weather-demo/1.0"}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None


POINT_ERROR = "Could not resolve location to a forecast grid. Check your coordinates (US locations only)."


async def fetch_point(lat: float, lon: float) -> dict:
    """Look up the NWS grid metadata (forecast URLs, stations) for a location."""
    points = await fetch(f"{BASE_URL}/points/{lat:.4f},{lon:.4f}")
    return (points or {}).get("properties", {})


def c_to_f(celsius: float) -> int:
    return round(celsius * 9 / 5 + 32)


@mcp.tool()
async def get_alerts(state: str) -> str:
    """
    Get active weather alerts for a US state.
    Args:
        state: Two-letter US state code (e.g. CA, NY, TX)
    """
    state = state.strip().upper()
    if len(state) != 2 or not state.isalpha():
        return f"Invalid state code '{state}'. Use a two-letter code like CA, NY, or TX."
    data = await fetch(f"{BASE_URL}/alerts/active/area/{state}")
    if not data or not data.get("features"):
        return f"No active weather alerts for {state}."
    alerts = []
    for feature in data["features"][:3]:
        props = feature.get("properties", {})
        alerts.append(
            f"- {props.get('event', 'Unknown event')} | "
            f"{props.get('areaDesc', 'Unknown area')} | "
            f"Severity: {props.get('severity', 'Unknown')}"
        )
    return f"Active alerts for {state}:\n" + "\n".join(alerts)


@mcp.tool()
async def get_forecast(lat: float, lon: float) -> str:
    """
    Get a 3-period weather forecast for a location.
    Args:
        lat: Latitude (e.g. 37.7749 for San Francisco)
        lon: Longitude (e.g. -122.4194 for San Francisco)
    """
    point = await fetch_point(lat, lon)
    forecast_url = point.get("forecast")
    if not forecast_url:
        return POINT_ERROR
    forecast = await fetch(forecast_url)
    periods = (forecast or {}).get("properties", {}).get("periods")
    if not periods:
        return "Forecast data unavailable. The NWS API may be temporarily down."
    result = []
    for period in periods[:3]:
        result.append(
            f"{period.get('name', 'Unknown')}: "
            f"{period.get('temperature', '?')}°{period.get('temperatureUnit', '')} "
            f"— {period.get('shortForecast', 'No details')}"
        )
    return "\n".join(result)


@mcp.tool()
async def get_hourly_forecast(lat: float, lon: float, hours: int = 12) -> str:
    """
    Get an hour-by-hour weather forecast for a location.
    Args:
        lat: Latitude (e.g. 37.7749 for San Francisco)
        lon: Longitude (e.g. -122.4194 for San Francisco)
        hours: Number of hours to return, 1 to 48 (default 12)
    """
    hours = max(1, min(hours, 48))
    point = await fetch_point(lat, lon)
    hourly_url = point.get("forecastHourly")
    if not hourly_url:
        return POINT_ERROR
    forecast = await fetch(hourly_url)
    periods = (forecast or {}).get("properties", {}).get("periods")
    if not periods:
        return "Hourly forecast unavailable. The NWS API may be temporarily down."
    result = []
    for period in periods[:hours]:
        # startTime looks like "2026-10-31T14:00:00-07:00"; keep the date and hour
        start = period.get("startTime", "")[:16].replace("T", " ")
        rain = (period.get("probabilityOfPrecipitation") or {}).get("value")
        result.append(
            f"{start}: {period.get('temperature', '?')}°{period.get('temperatureUnit', '')} "
            f"— {period.get('shortForecast', 'No details')} "
            f"| Rain: {rain if rain is not None else 0}% "
            f"| Wind: {period.get('windSpeed', '?')} {period.get('windDirection', '')}"
        )
    return "\n".join(result)


@mcp.tool()
async def get_current_conditions(lat: float, lon: float) -> str:
    """
    Get the latest observed weather from the station nearest a location.
    Args:
        lat: Latitude (e.g. 37.7749 for San Francisco)
        lon: Longitude (e.g. -122.4194 for San Francisco)
    """
    point = await fetch_point(lat, lon)
    stations_url = point.get("observationStations")
    if not stations_url:
        return POINT_ERROR
    stations = await fetch(stations_url)
    features = (stations or {}).get("features")
    if not features:
        return "No observation stations found near this location."
    station = features[0].get("properties", {})
    station_id = station.get("stationIdentifier")
    obs = await fetch(f"{BASE_URL}/stations/{station_id}/observations/latest")
    props = (obs or {}).get("properties")
    if not props:
        return f"No recent observations from station {station_id}."

    def value(field: str) -> float | None:
        return (props.get(field) or {}).get("value")

    temp_c = value("temperature")
    humidity = value("relativeHumidity")
    wind_kmh = value("windSpeed")
    lines = [
        f"Station: {station.get('name', 'Unknown')} ({station_id})",
        f"Observed: {props.get('timestamp', 'Unknown')[:16].replace('T', ' ')} UTC",
        f"Conditions: {props.get('textDescription') or 'Unknown'}",
        f"Temperature: {c_to_f(temp_c)}°F" if temp_c is not None else "Temperature: n/a",
        f"Humidity: {humidity:.0f}%" if humidity is not None else "Humidity: n/a",
        f"Wind: {wind_kmh * 0.621371:.0f} mph" if wind_kmh is not None else "Wind: n/a",
    ]
    return "\n".join(lines)


@mcp.tool()
async def find_location(city: str, state: str | None = None) -> str:
    """
    Find the latitude and longitude of a US city. Use this before the forecast
    and conditions tools when you only know a place name.
    Args:
        city: City name (e.g. Austin). "Austin, TX" also works.
        state: Optional two-letter US state code to narrow results (e.g. TX)
    """
    if state is None and "," in city:
        city, state = (part.strip() for part in city.split(",", 1))
    city = city.strip()
    if not city:
        return "Please provide a city name."
    state_name = None
    if state:
        state = state.strip().upper()
        state_name = STATE_CODES.get(state)
        if not state_name:
            return f"Unknown state code '{state}'. Use a two-letter code like CA, NY, or TX."

    query = urlencode({"name": city, "count": 20, "countryCode": "US", "language": "en"})
    data = await fetch(f"{GEOCODE_URL}?{query}")
    results = (data or {}).get("results") or []
    if state_name:
        results = [r for r in results if r.get("admin1") == state_name]
    if not results:
        where = f"{city}, {state}" if state else city
        return f"No US locations found for '{where}'."

    lines = []
    for r in results[:5]:
        admin1 = r.get("admin1", "")
        code = STATE_ABBREVIATIONS.get(admin1, admin1)
        population = r.get("population")
        pop = f" (pop. {population:,})" if population else ""
        lines.append(
            f"{r.get('name', city)}, {code}: "
            f"{r['latitude']:.4f}, {r['longitude']:.4f}{pop}"
        )
    header = "Matches:" if len(lines) > 1 else "Match:"
    return header + "\n" + "\n".join(lines)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
