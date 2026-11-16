"""Thin client for the Google Street View Static API.

The API key is never logged or included in returned error messages.
"""

from __future__ import annotations

import math
import os

import httpx

BASE = "https://maps.googleapis.com/maps/api/streetview"


class StreetViewError(RuntimeError):
    pass


def api_key() -> str:
    key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not key:
        raise StreetViewError(
            "GOOGLE_MAPS_API_KEY is not set. Put it in the .env file next to run.sh "
            "(see .env.example) or export it in the environment."
        )
    return key


def _redact(text: str, key: str) -> str:
    return text.replace(key, "<API_KEY>") if key else text


def _get(client: httpx.Client, path: str, params: dict) -> httpx.Response:
    key = api_key()
    try:
        resp = client.get(f"{BASE}{path}", params={**params, "key": key}, timeout=20)
    except httpx.HTTPError as exc:
        raise StreetViewError(_redact(f"Request failed: {exc}", key)) from None
    if resp.status_code != 200:
        raise StreetViewError(
            _redact(f"Street View API returned HTTP {resp.status_code}: {resp.text[:300]}", key)
        )
    return resp


def metadata(client: httpx.Client, lat: float, lon: float, radius_m: int = 100) -> dict:
    """Find the nearest panorama. Metadata requests are free of charge."""
    resp = _get(
        client,
        "/metadata",
        {"location": f"{lat},{lon}", "radius": radius_m, "source": "outdoor"},
    )
    data = resp.json()
    status = data.get("status")
    if status in ("OK", "ZERO_RESULTS", "NOT_FOUND"):
        return data
    raise StreetViewError(f"Street View metadata status {status}: {data.get('error_message', '')}")


def image(
    client: httpx.Client,
    pano_id: str,
    heading: float,
    pitch: float = 0,
    fov: int = 90,
    size: str = "640x640",
) -> bytes:
    """Fetch one Street View image (billable request)."""
    resp = _get(
        client,
        "",
        {
            "pano": pano_id,
            "heading": f"{heading % 360:.1f}",
            "pitch": pitch,
            "fov": fov,
            "size": size,
            "return_error_code": "true",
        },
    )
    if not resp.headers.get("content-type", "").startswith("image/"):
        raise StreetViewError("Street View API did not return an image")
    return resp.content


def bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial great-circle bearing in degrees from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))
