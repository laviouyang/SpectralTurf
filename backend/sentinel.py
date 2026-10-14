"""
sentinel.py - Everything that talks to the Copernicus Data Space (Sentinel Hub) API.

Jobs:
  1. get_token()            -> log in with our client ID/secret and get an access token
  2. fetch_true_color(...)  -> true-color picture (Process API)
  3. find_clearest_scene()  -> which date had the least cloud? (Catalog API)
  4. fetch_bands(...)       -> raw band numbers inside a polygon for one date (Process API)

Endpoints come from the official CDSE Beginners Guide:
https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/UserGuides/BeginnersGuide.html
"""

import io
import math
import os
import time

import numpy as np
import requests
import tifffile

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/process/v1"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/catalog/v1/search"

# "Plain longitude/latitude" - the same coordinate system GeoJSON and Leaflet use.
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"

# Sentinel-2's sharpest bands (B02, B03, B04, B08) are 10 m per pixel.
# Asking for smaller pixels would NOT add real detail, so we stick to 10 m.
METERS_PER_PIXEL = 10

# Safety limit so a mistake can't request a huge (expensive) image.
MAX_PIXELS_PER_SIDE = 500  # 500 px * 10 m = 5 km


class SentinelError(Exception):
    """An error with a message that is safe and useful to show the user."""


# ---------------------------------------------------------------------------
# 1. Authentication
# ---------------------------------------------------------------------------

# We remember the token so we don't log in again on every request.
_cached_token = None
_token_expires_at = 0.0


def get_token() -> str:
    global _cached_token, _token_expires_at

    # Reuse the saved token if it still has at least 60 seconds left.
    if _cached_token and time.time() < _token_expires_at - 60:
        return _cached_token

    client_id = os.getenv("CDSE_CLIENT_ID")
    client_secret = os.getenv("CDSE_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SentinelError(
            "Missing CDSE_CLIENT_ID or CDSE_CLIENT_SECRET. "
            "Create backend/.env from .env.example and add your credentials."
        )

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )
    except requests.RequestException as e:
        raise SentinelError(f"Could not reach the Copernicus login server: {type(e).__name__}")

    if response.status_code != 200:
        # Don't print the response body - it could echo credential details.
        raise SentinelError(
            f"Login failed (HTTP {response.status_code}). Check that your client ID and secret are correct."
        )

    data = response.json()
    _cached_token = data["access_token"]
    _token_expires_at = time.time() + data.get("expires_in", 3600)
    return _cached_token


# ---------------------------------------------------------------------------
# 2. Image size helper
# ---------------------------------------------------------------------------

def pixel_size_for_bbox(west: float, south: float, east: float, north: float):
    """
    Work out how many 10 m pixels fit across and down the box.

    Longitude lines get closer together as you move away from the equator,
    so one degree of longitude is shorter in Colorado (~85 km) than at the
    equator (~111 km). We multiply by cos(latitude) to correct for that.
    """
    meters_per_degree_lat = 111_320
    middle_lat = (south + north) / 2
    meters_per_degree_lon = 111_320 * math.cos(math.radians(middle_lat))

    width_m = (east - west) * meters_per_degree_lon
    height_m = (north - south) * meters_per_degree_lat

    width_px = max(1, round(width_m / METERS_PER_PIXEL))
    height_px = max(1, round(height_m / METERS_PER_PIXEL))
    return width_px, height_px, width_m, height_m


def geometry_bbox(geometry):
    """The smallest box (west, south, east, north) around a GeoJSON Polygon."""
    ring = geometry["coordinates"][0]
    lons = [point[0] for point in ring]
    lats = [point[1] for point in ring]
    return min(lons), min(lats), max(lons), max(lats)


def box_polygon(west, south, east, north):
    """Turn a box into a GeoJSON Polygon, so boxes and drawn shapes use the same code."""
    ring = [[west, south], [east, south], [east, north], [west, north], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


# ---------------------------------------------------------------------------
# 3. True-color request
# ---------------------------------------------------------------------------

# The evalscript runs on Sentinel Hub's servers once per pixel.
# - B04/B03/B02 are red/green/blue reflectance (mostly 0.0-0.3 for land).
# - We multiply by 2.5 ONLY to make the picture bright enough to see.
#   This is a display choice; we never do this to numbers used for NDVI/NDMI.
# - dataMask is 0 where there is no data; we make those pixels transparent.
TRUE_COLOR_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B02", "B03", "B04", "dataMask"],
    output: { bands: 4 }
  };
}
function evaluatePixel(s) {
  return [2.5 * s.B04, 2.5 * s.B03, 2.5 * s.B02, s.dataMask];
}
"""


def fetch_true_color(west, south, east, north, start_date, end_date, max_cloud=30) -> bytes:
    """Return PNG image bytes of real Sentinel-2 L2A true color for the box."""
    width_px, height_px = check_box(west, south, east, north)

    body = {
        "input": {
            "bounds": {
                "bbox": [west, south, east, north],
                "properties": {"crs": CRS84},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{start_date}T00:00:00Z",
                            "to": f"{end_date}T23:59:59Z",
                        },
                        # Skip scenes whose whole tile is more than max_cloud % cloudy.
                        "maxCloudCoverage": max_cloud,
                        # Prefer the least-cloudy scene in the date range.
                        "mosaickingOrder": "leastCC",
                    },
                }
            ],
        },
        "output": {
            "width": width_px,
            "height": height_px,
            "responses": [{"identifier": "default", "format": {"type": "image/png"}}],
        },
        "evalscript": TRUE_COLOR_EVALSCRIPT,
    }

    response = _post(PROCESS_URL, body)
    if not response.headers.get("content-type", "").startswith("image/png"):
        raise SentinelError("The satellite server returned something that is not a PNG image.")
    return response.content


def check_box(west, south, east, north):
    """Validate the box and return its size in 10 m pixels."""
    if not (west < east and south < north):
        raise SentinelError("Invalid box: west must be less than east, and south less than north.")
    width_px, height_px, width_m, height_m = pixel_size_for_bbox(west, south, east, north)
    if width_px > MAX_PIXELS_PER_SIDE or height_px > MAX_PIXELS_PER_SIDE:
        raise SentinelError(
            f"Area is too large ({width_m/1000:.1f} km x {height_m/1000:.1f} km). "
            f"Keep each side under {MAX_PIXELS_PER_SIDE * METERS_PER_PIXEL / 1000:.0f} km."
        )
    return width_px, height_px


def _post(url, body):
    """Send a request to Sentinel Hub and turn any failure into a clear SentinelError."""
    headers = {"Authorization": f"Bearer {get_token()}"}
    try:
        response = requests.post(url, json=body, headers=headers, timeout=60)
    except requests.Timeout:
        raise SentinelError("The satellite server took too long to respond. Try again in a minute.")
    except requests.RequestException as e:
        raise SentinelError(f"Could not reach the satellite server: {type(e).__name__}")

    if response.status_code == 401:
        raise SentinelError("The access token was rejected (HTTP 401). Restart the server to log in again.")
    if response.status_code == 429:
        raise SentinelError("Too many requests (HTTP 429). Wait a minute and try again.")
    if response.status_code != 200:
        # Sentinel Hub returns a JSON error description - safe to show.
        raise SentinelError(f"Satellite request failed (HTTP {response.status_code}): {response.text[:300]}")
    return response


# ---------------------------------------------------------------------------
# 4. Which date is clearest?  (Catalog API)
# ---------------------------------------------------------------------------

def find_clearest_scene(west, south, east, north, start_date, end_date, max_cloud=30):
    """
    Ask the Catalog which Sentinel-2 L2A scenes cover the box, then pick the one
    with the lowest cloud cover. This gives us a REAL observation date.

    Note: eo:cloud_cover is for the whole ~110 km tile, not just our field.
    The field itself could still be cloudy, which is why we ALSO mask clouds
    pixel-by-pixel with the SCL band later.
    """
    body = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [west, south, east, north],
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "limit": 100,
    }
    features = _post(CATALOG_URL, body).json().get("features", [])

    scenes = []
    for f in features:
        cloud = f.get("properties", {}).get("eo:cloud_cover")
        when = f.get("properties", {}).get("datetime")
        if cloud is not None and when and cloud <= max_cloud:
            scenes.append({"date": when[:10], "datetime": when, "tile_cloud_cover": round(cloud, 1)})

    if not scenes:
        raise SentinelError(
            f"No Sentinel-2 scenes with {max_cloud}% cloud cover or less between "
            f"{start_date} and {end_date}. Try a longer date range or a higher cloud limit."
        )

    # Lowest cloud first; if tied, the more recent date wins.
    scenes.sort(key=lambda s: (s["tile_cloud_cover"], -int(s["date"].replace("-", ""))))
    best = scenes[0]
    best["scenes_considered"] = len(scenes)
    return best


# ---------------------------------------------------------------------------
# 5. Raw band numbers for one date  (Process API, FLOAT32 GeoTIFF)
# ---------------------------------------------------------------------------

# Returns the raw values - NO brightening. Order matters: it must match BAND_NAMES.
# B02/B03/B04/B08/B8A/B11 are surface reflectance (about 0-1).
# B02 (blue) and B03 (green) are only used for the true-color picture.
# SCL is the scene-classification code (0-11). dataMask is 1 = data, 0 = none.
BAND_NAMES = ["B02", "B03", "B04", "B08", "B8A", "B11", "SCL", "dataMask"]
BANDS_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: ["B02", "B03", "B04", "B08", "B8A", "B11", "SCL", "dataMask"],
    output: { bands: 8, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  return [s.B02, s.B03, s.B04, s.B08, s.B8A, s.B11, s.SCL, s.dataMask];
}
"""


def fetch_bands(geometry, date):
    """
    Return a dict of numpy arrays (one per band) on a 10 m grid for a single day.

    We send the real polygon, not just its box. The image still covers the
    polygon's box, but Sentinel Hub sets dataMask = 0 for every pixel outside
    the polygon, so those pixels are never counted in the statistics.
    """
    west, south, east, north = geometry_bbox(geometry)
    width_px, height_px = check_box(west, south, east, north)

    body = {
        "input": {
            "bounds": {
                "geometry": geometry,
                "properties": {"crs": CRS84},
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": f"{date}T00:00:00Z", "to": f"{date}T23:59:59Z"},
                    },
                    # NEAREST (the default) copies each 20 m value into a 2x2 block.
                    # It never blends or invents values - important for SCL codes.
                    "processing": {"upsampling": "NEAREST", "downsampling": "NEAREST"},
                }
            ],
        },
        "output": {
            "width": width_px,
            "height": height_px,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
        },
        "evalscript": BANDS_EVALSCRIPT,
    }

    response = _post(PROCESS_URL, body)
    try:
        arr = tifffile.imread(io.BytesIO(response.content))
    except Exception:
        raise SentinelError(
            "Could not read the band data returned by the satellite server. "
            "If this keeps happening, run: pip install imagecodecs"
        )

    # Expect (height, width, 8). Some readers give (8, height, width) - handle both.
    n = len(BAND_NAMES)
    if arr.ndim == 3 and arr.shape[0] == n and arr.shape[-1] != n:
        arr = np.moveaxis(arr, 0, -1)
    if arr.ndim != 3 or arr.shape[-1] != n:
        raise SentinelError(f"Unexpected band data shape {arr.shape}.")

    return {name: arr[:, :, i] for i, name in enumerate(BAND_NAMES)}
