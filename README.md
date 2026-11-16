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

## How it works

```
"SU 123 456"
   │  1. parse grid ref        (gridref.py)
   ▼
easting 412350, northing 145650   (centre of the 100 m square)
   │  2. reproject OSGB36 → WGS84   (pyproj, EPSG:27700 → EPSG:4326)
   ▼
51.2099, -1.8246
   │  3. find nearest panorama   (Street View metadata API, free)
   ▼
pano_id, panorama lat/long, capture date
   │  4. work out the camera heading from the panorama to the point
   │  5. fetch image(s) by pano_id    (Street View Static API, billed)
   ▼
JPEG(s) returned to the model as MCP image content and saved to disk
```

1. **Parsing a grid reference** (`src/refconv_mcp/gridref.py`). The two letters name a 100 km square on the British National Grid. The letter `I` isn't used, and the first letter picks a 500 km block. The server turns the letters into the square's south-west corner in metres. The digits split into an easting half and a northing half. Their scale depends on how many there are: 6 figures means each digit pair counts in 100 m steps. The server then adds half a square to get the centre. You can also enter an easting/northing in metres directly.
2. **Converting to lat/long.** Easting and northing are on the OSGB36 datum with a Transverse Mercator projection. GPS and Google use WGS84. [pyproj](https://pyproj4.github.io/pyproj/) does the datum shift and projection, which is accurate to a few metres. That's well inside a 6-figure square. `latlon_to_gridref` does the same steps in reverse.
3. **Finding a panorama** (`src/refconv_mcp/streetview.py`). The Street View *metadata* endpoint is free. It returns the nearest outdoor panorama within `radius_m`, or `ZERO_RESULTS` if there isn't one. That way the server never pays for an image that doesn't exist.
4. **Aiming the camera.** Panoramas are usually on a road, not on the grid point itself. The server calculates the compass bearing from the panorama to the point, so the default view looks *at* the place you asked about. With `views=N`, the N headings are spread evenly around 360°, starting from that bearing.
5. **Fetching images.** Each view is requested by `pano_id`, so every image comes from the same panorama. The images go back to the model as MCP image content. They're also saved as `<gridref>_<timestamp>_h<heading>.jpg` in `REFCONV_OUTPUT_DIR`.

The server (`src/refconv_mcp/server.py`) uses the official MCP Python SDK (FastMCP) and talks to the client over stdio.

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
