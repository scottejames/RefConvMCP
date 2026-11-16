# RefConvMCP

An MCP server that takes **Ordnance Survey (British National Grid) grid references**, such as `SU 123 456`, converts them to lat/long, and fetches **Google Street View** images for that spot.

> "Show me Street View at NN 166 712, looking all four ways"

## Tools

| Tool | What it does | Cost |
| --- | --- | --- |
| `gridref_to_latlon` | Grid ref → WGS84 lat/long, easting/northing and a Google Maps link | free, offline |
| `latlon_to_gridref` | Lat/long → grid ref (2–10 figures) | free, offline |
| `streetview_coverage` | Checks for a panorama near a grid ref and returns its capture date and distance/bearing to the point | free (metadata endpoint) |
| `streetview_from_gridref` | Returns Street View image(s) inline and can also save them as JPEGs | billed per image by Google |

### Grid reference formats

- Lettered, 0–10 digits: `SU`, `SU1245`, `SU 123 456`, `su123456`, `NN 16650 71250`
- Numeric easting/northing in metres: `412300,145600`

A grid reference is a **square**: 6 figures is 100 m and 8 figures is 10 m. The server uses the centre of the square and then finds the nearest outdoor Street View panorama within `radius_m` (default 100 m). By default it returns one image, taken from that panorama and **looking towards the grid ref point**. Use `views=4` to get all-round coverage, or set `heading`, `pitch` and `fov` yourself.

The conversion uses [pyproj](https://pyproj4.github.io/pyproj/) (EPSG:27700 → EPSG:4326).

## Setup

### 1. Google API key

1. In [Google Cloud Console](https://console.cloud.google.com/), create or choose a project and enable billing. Street View has a monthly free tier.
2. Enable the **Street View Static API** under APIs & Services → Library.
3. Create an API key under APIs & Services → Credentials. Restrict it to the Street View Static API.

### 2. Install

Requires [uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/scottejames/RefConvMCP.git
cd RefConvMCP
uv sync
cp .env.example .env && chmod 600 .env   # then put your key in .env
```

### 3. Register with Claude Code

```sh
claude mcp add --scope user refconv -- "$PWD/run.sh"
```

## Keeping the API key out of git

- The key lives **only** in `.env`. That file is gitignored, so it is never committed. `.env.example` is the committed template.
- `run.sh` sources `.env` and then starts the server. Claude Code is registered against `run.sh`, so the key is **not** stored in `~/.claude.json` either.
- If an API error message contains the key, the server redacts it before returning the message to the model.
- Other MCP clients can skip `run.sh` and set `GOOGLE_MAPS_API_KEY` in the environment directly.

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_MAPS_API_KEY` | yes (Street View tools only) | Google key with the Street View Static API enabled |
| `REFCONV_OUTPUT_DIR` | no | Where images are saved (`run.sh` defaults to `./streetview_images`, which is gitignored) |

## Development

```sh
uv run pytest
```

## Licence

MIT. Street View imagery is © Google and subject to the [Google Maps Platform Terms](https://cloud.google.com/maps-platform/terms).
