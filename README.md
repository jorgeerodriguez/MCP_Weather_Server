# MCP Weather Server

An [MCP](https://modelcontextprotocol.io) server that gives AI assistants such as Claude live US weather data from the [National Weather Service API](https://www.weather.gov/documentation/services-web-api). It needs no API key.

## Tools

| Tool | What it does |
|---|---|
| `find_location(city, state?)` | Finds the latitude/longitude of a US city. Accepts `"Austin"`, `"Austin", "TX"`, or `"Austin, TX"`. |
| `get_forecast(lat, lon)` | Forecast for the next 3 periods (e.g. Today, Tonight, Tomorrow). |
| `get_hourly_forecast(lat, lon, hours=12)` | Hour-by-hour forecast with chance of rain and wind (1–48 hours). |
| `get_current_conditions(lat, lon)` | Latest observation (temperature, humidity, wind) from the nearest weather station. |
| `get_alerts(state)` | Up to 3 active weather alerts for a two-letter state code (e.g. `CA`). |

When you only give a place name, the assistant calls `find_location` first and then passes the coordinates to the forecast tools.

Example output from `get_hourly_forecast`:

```
2026-10-31 10:00: 59°F — Mostly Sunny | Rain: 1% | Wind: 3 mph SSW
2026-10-31 11:00: 61°F — Mostly Sunny | Rain: 1% | Wind: 3 mph SW
```

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)
- Node.js (only for the MCP Inspector)

## Setup

```bash
git clone https://github.com/jorgeerodriguez/MCP_Weather_Server.git
cd MCP_Weather_Server
uv sync
```

## Running

Start the server over stdio:

```bash
uv run weather
```

The server waits silently for an MCP client to connect, so it looks idle when started by hand. Press Ctrl+C to stop it.

To try the tools interactively in your browser, use the MCP Inspector:

```bash
uv run mcp dev src/weather/server.py
```

## Using with Claude Desktop

Open the config file (**Settings → Developer → Edit Config** in Claude Desktop), or edit it directly:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Add the server under `mcpServers`:

```json
{
  "mcpServers": {
    "weather": {
      "command": "/full/path/to/uv",
      "args": ["--directory", "/full/path/to/MCP_Weather_Server", "run", "weather"]
    }
  }
}
```

Use full paths: Claude Desktop does not load your shell's `PATH`. Run `which uv` to find the path to `uv`. Then quit Claude Desktop completely and reopen it.

## Project layout

```
src/weather/
├── server.py     # MCP server and tools
└── __main__.py   # enables `python -m weather`
```

## Notes

- **US only.** The National Weather Service covers the US and its territories. Coordinates elsewhere return an error message.
- City lookup uses the free [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api).
- Some small weather stations don't report every field, so `get_current_conditions` may show `n/a` for wind or conditions.
- Built on the MCP Python SDK 2.x (`MCPServer`). Code written for SDK 1.x (`FastMCP`) needs the import changed.
