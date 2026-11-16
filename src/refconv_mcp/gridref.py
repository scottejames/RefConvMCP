"""Parse Ordnance Survey (British National Grid) references and convert to WGS84.

Accepted inputs:
  - Lettered grid refs with 0-10 digits: "SU", "SU1245", "SU 123 456", "su123456", "NN 16650 71250"
  - Numeric easting/northing in metres: "412300,145600" or "412300 145600"

A grid reference denotes a square, not a point (6 figures = 100 m square).
By default the centre of the square is returned.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from pyproj import Transformer

# OSGB36 / British National Grid -> WGS84 (lon, lat order with always_xy)
_TO_WGS84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
_FROM_WGS84 = Transformer.from_crs("EPSG:4326", "EPSG:27700", always_xy=True)

_LETTERED = re.compile(r"^([A-HJ-Z]{2})(\d*)$")
_NUMERIC = re.compile(r"^(\d{1,7}(?:\.\d+)?)[,\s]+(\d{1,7}(?:\.\d+)?)$")


class GridRefError(ValueError):
    """Raised when a grid reference cannot be parsed or is out of range."""


@dataclass(frozen=True)
class GridPoint:
    input: str
    normalised: str  # e.g. "SU 123 456"
    easting: float
    northing: float
    precision_m: int  # size of the square the reference denotes (1 for numeric input)
    lat: float
    lon: float

    def as_dict(self) -> dict:
        return {
            "input": self.input,
            "grid_ref": self.normalised,
            "easting": round(self.easting, 1),
            "northing": round(self.northing, 1),
            "precision_m": self.precision_m,
            "lat": round(self.lat, 6),
            "lon": round(self.lon, 6),
            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={self.lat:.6f},{self.lon:.6f}",
        }


def _letter_index(ch: str) -> int:
    i = ord(ch) - ord("A")
    return i - 1 if i > 7 else i  # grid skips "I"


def _square_origin(letters: str) -> tuple[int, int]:
    """Return the SW corner (easting, northing) in metres of a 100 km square."""
    l1, l2 = _letter_index(letters[0]), _letter_index(letters[1])
    e100k = ((l1 - 2) % 5) * 5 + (l2 % 5)
    n100k = (19 - (l1 // 5) * 5) - (l2 // 5)
    if not (0 <= e100k <= 6 and 0 <= n100k <= 12):
        raise GridRefError(f"'{letters}' is not a British National Grid square")
    return e100k * 100_000, n100k * 100_000


def parse(ref: str, centre: bool = True) -> tuple[float, float, int, str]:
    """Parse a grid reference into (easting, northing, precision_m, normalised)."""
    raw = ref.strip().upper()
    compact = re.sub(r"\s+", "", raw)

    m = _LETTERED.match(compact)
    if m:
        letters, digits = m.groups()
        if len(digits) % 2 or len(digits) > 10:
            raise GridRefError(
                f"'{ref}': expected an even number of digits (0-10) after the letters, got {len(digits)}"
            )
        e0, n0 = _square_origin(letters)
        half = len(digits) // 2
        precision = 10 ** (5 - half)  # metres
        e = int(digits[:half] or 0) * precision
        n = int(digits[half:] or 0) * precision
        offset = precision / 2 if centre else 0
        normalised = f"{letters} {digits[:half]} {digits[half:]}".strip()
        return e0 + e + offset, n0 + n + offset, precision, normalised

    m = _NUMERIC.match(raw)
    if m:
        e, n = float(m.group(1)), float(m.group(2))
        if not (0 <= e < 700_000 and 0 <= n < 1_300_000):
            raise GridRefError(f"'{ref}': easting/northing outside the British National Grid")
        return e, n, 1, f"{e:.0f}, {n:.0f}"

    raise GridRefError(
        f"Could not parse '{ref}'. Use e.g. 'SU 123 456', 'NN166712' or '412300,145600'."
    )


def to_wgs84(ref: str, centre: bool = True) -> GridPoint:
    e, n, precision, normalised = parse(ref, centre=centre)
    lon, lat = _TO_WGS84.transform(e, n)
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise GridRefError(f"'{ref}': conversion failed")
    return GridPoint(ref, normalised, e, n, precision, lat, lon)


def from_wgs84(lat: float, lon: float, digits: int = 6) -> dict:
    """Convert WGS84 lat/long to a lettered grid reference with `digits` figures."""
    if digits % 2 or not 2 <= digits <= 10:
        raise GridRefError("digits must be an even number between 2 and 10")
    e, n = _FROM_WGS84.transform(lon, lat)
    if not (0 <= e < 700_000 and 0 <= n < 1_300_000):
        raise GridRefError(f"{lat},{lon} is outside the British National Grid")
    e100k, n100k = int(e // 100_000), int(n // 100_000)
    l1 = (19 - n100k) - (19 - n100k) % 5 + (e100k + 10) // 5
    l2 = (19 - n100k) * 5 % 25 + e100k % 5
    letters = "".join(chr(ord("A") + (i + 1 if i > 7 else i)) for i in (l1, l2))
    half = digits // 2
    scale = 10 ** (5 - half)
    es = f"{int(e % 100_000) // scale:0{half}d}"
    ns = f"{int(n % 100_000) // scale:0{half}d}"
    return {
        "grid_ref": f"{letters} {es} {ns}",
        "easting": round(e, 1),
        "northing": round(n, 1),
    }
