"""RefConvMCP server: OS grid references -> lat/long -> Google Street View images."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP, Image

from . import gridref, streetview

# Load .env from the project root (two levels above this file) if present.
# run.sh also sources it; this is a fallback for running the module directly.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

mcp = FastMCP(
    "refconv",
    instructions=(
        "Converts Ordnance Survey (British National Grid) grid references such as "
        "'SU 123 456' to WGS84 lat/long, and fetches Google Street View images for "
        "a grid reference. A 6-figure reference is a 100 m square; Street View snaps "
        "to the nearest panorama within the search radius. Image requests are billed "
        "by Google, so request only the views needed."
    ),
)


def _output_dir() -> Path:
    d = Path(os.getenv("REFCONV_OUTPUT_DIR", Path.cwd() / "streetview_images")).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d


@mcp.tool()
def gridref_to_latlon(grid_ref: str, centre: bool = True) -> dict:
    """Convert an OS grid reference to WGS84 latitude/longitude.

    Args:
        grid_ref: e.g. "SU 123 456", "NN166712", "TQ3080" or numeric "412300,145600".
        centre: return the centre of the referenced square (True) or its SW corner (False).
    """
    return gridref.to_wgs84(grid_ref, centre=centre).as_dict()


@mcp.tool()
def latlon_to_gridref(lat: float, lon: float, digits: int = 6) -> dict:
    """Convert WGS84 latitude/longitude to an OS grid reference.

    Args:
        lat: latitude in decimal degrees.
        lon: longitude in decimal degrees.
        digits: total figures in the reference (2-10, even). 6 = 100 m precision.
    """
    return gridref.from_wgs84(lat, lon, digits)


@mcp.tool()
def streetview_coverage(grid_ref: str, radius_m: int = 100) -> dict:
    """Check whether Google Street View has a panorama near a grid reference.

    Uses the free metadata endpoint, so it costs nothing. Returns the panorama
    location, capture date, and distance/bearing to the grid reference point.

    Args:
        grid_ref: OS grid reference, e.g. "SU 123 456".
        radius_m: how far from the point to search for a panorama (metres).
    """
    point = gridref.to_wgs84(grid_ref)
    with httpx.Client() as client:
        meta = streetview.metadata(client, point.lat, point.lon, radius_m)
    result = {"point": point.as_dict(), "status": meta.get("status")}
    if meta.get("status") == "OK":
        loc = meta["location"]
        result["panorama"] = {
            "pano_id": meta.get("pano_id"),
            "lat": loc["lat"],
            "lon": loc["lng"],
            "date": meta.get("date"),
            "copyright": meta.get("copyright"),
            "distance_to_point_m": round(
                streetview.distance_m(loc["lat"], loc["lng"], point.lat, point.lon), 1
            ),
            "bearing_to_point_deg": round(
                streetview.bearing(loc["lat"], loc["lng"], point.lat, point.lon), 1
            ),
        }
    return result


@mcp.tool()
def streetview_from_gridref(
    grid_ref: str,
    views: int = 1,
    heading: float | None = None,
    pitch: float = 0,
    fov: int = 90,
    radius_m: int = 100,
    size: str = "640x640",
    save: bool = True,
) -> list:
    """Fetch Google Street View image(s) for an OS grid reference.

    Finds the nearest outdoor panorama within radius_m of the centre of the grid
    square, then returns the image(s). By default one image is taken looking from
    the panorama towards the grid reference point.

    Args:
        grid_ref: OS grid reference, e.g. "SU 123 456" or "NN166712".
        views: number of images spread evenly around 360 deg (1-8). 4 gives N/E/S/W-style coverage.
        heading: compass heading of the first view in degrees. Default: towards the point
            (or 0 if the panorama is on top of it).
        pitch: up/down camera angle, -90 to 90.
        fov: horizontal field of view in degrees, 10-120.
        radius_m: search radius for the nearest panorama in metres.
        size: image size "WxH", max 640x640.
        save: also save JPEGs to REFCONV_OUTPUT_DIR and return their paths.
    """
    if not 1 <= views <= 8:
        raise ValueError("views must be between 1 and 8")
    if not re.fullmatch(r"\d{2,3}x\d{2,3}", size):
        raise ValueError("size must look like '640x640' (max 640 each side)")

    point = gridref.to_wgs84(grid_ref)
    with httpx.Client() as client:
        meta = streetview.metadata(client, point.lat, point.lon, radius_m)
        if meta.get("status") != "OK":
            return [
                f"No Street View panorama within {radius_m} m of {point.normalised} "
                f"({point.lat:.6f}, {point.lon:.6f}); status {meta.get('status')}. "
                "Try a larger radius_m."
            ]

        loc = meta["location"]
        dist = streetview.distance_m(loc["lat"], loc["lng"], point.lat, point.lon)
        if heading is None:
            heading = (
                streetview.bearing(loc["lat"], loc["lng"], point.lat, point.lon)
                if dist > 10
                else 0.0
            )
        headings = [(heading + i * 360 / views) % 360 for i in range(views)]

        out: list = []
        saved: list[str] = []
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = re.sub(r"[^A-Za-z0-9]+", "", point.normalised)
        for h in headings:
            data = streetview.image(client, meta["pano_id"], h, pitch, fov, size)
            out.append(Image(data=data, format="jpeg"))
            if save:
                path = _output_dir() / f"{slug}_{stamp}_h{int(round(h)):03d}.jpg"
                path.write_bytes(data)
                saved.append(str(path))

    summary = (
        f"{point.normalised} -> {point.lat:.6f}, {point.lon:.6f} "
        f"({point.precision_m} m square). Panorama {meta.get('pano_id')} "
        f"captured {meta.get('date', 'unknown date')}, {dist:.0f} m from the point. "
        f"Headings: {', '.join(f'{h:.0f}' for h in headings)} deg. "
        f"{meta.get('copyright', '')}"
    )
    if saved:
        summary += "\nSaved: " + ", ".join(saved)
    return [summary, *out]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
