/*
 * polygonCheck.js - Is the drawn area usable for a satellite analysis?
 *
 * These limits are OUR PROJECT'S CHOICES, not published scientific standards.
 * They match the backend:
 *   - MIN_VALID_PIXELS = 20 in backend/indices.py   -> 20 x (10 m x 10 m) = 2,000 m²
 *   - MAX_PIXELS_PER_SIDE = 500 in backend/sentinel.py -> 500 x 10 m = 5 km
 */

export const MIN_AREA_M2 = 2000;
export const MAX_SIDE_M = 5000;
const PIXEL_AREA_M2 = 10 * 10; // one Sentinel-2 10 m pixel
const NDMI_PIXEL_AREA_M2 = 20 * 20; // one 20 m pixel (B8A, B11)

// Width and height of the polygon's bounding box in meters.
// Same cos(latitude) correction as pixel_size_for_bbox() in the backend.
function boxSizeMeters({ west, south, east, north }) {
  const metersPerDegreeLat = 111320;
  const middleLat = (south + north) / 2;
  const metersPerDegreeLon = 111320 * Math.cos((middleLat * Math.PI) / 180);
  return {
    widthM: (east - west) * metersPerDegreeLon,
    heightM: (north - south) * metersPerDegreeLat,
  };
}

// Returns { ok, problems, facts }. "problems" block analysis; "facts" are just information.
export function checkPolygon(polygon) {
  const problems = [];
  const { widthM, heightM } = boxSizeMeters(polygon.bounds);

  if (polygon.selfIntersects) {
    problems.push('The outline crosses itself. Redraw it so the edges do not cross.');
  }
  if (polygon.areaM2 < MIN_AREA_M2) {
    problems.push(
      `Area is too small (${Math.round(polygon.areaM2).toLocaleString()} m²). ` +
        `Draw at least ${MIN_AREA_M2.toLocaleString()} m² (about 20 satellite pixels).`
    );
  }
  if (widthM > MAX_SIDE_M || heightM > MAX_SIDE_M) {
    problems.push(
      `Area is too large (${(widthM / 1000).toFixed(1)} km x ${(heightM / 1000).toFixed(1)} km). ` +
        `Keep each side under ${MAX_SIDE_M / 1000} km.`
    );
  }

  return {
    ok: problems.length === 0,
    problems,
    facts: {
      areaM2: polygon.areaM2,
      acres: polygon.areaM2 / 4046.86,
      pixels10m: Math.floor(polygon.areaM2 / PIXEL_AREA_M2),
      pixels20m: Math.floor(polygon.areaM2 / NDMI_PIXEL_AREA_M2),
      widthM,
      heightM,
    },
  };
}
