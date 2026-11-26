/*
 * turfRegions.js - US grass regions (added 2026-11-25). The data is turfRegions.json, written by
 * scripts/make_turf_regions.py (the backend has an identical copy, backend/turf_regions.json).
 *
 * A SIMPLIFIED project map with APPROXIMATE boundaries; each region's grass list comes from that
 * region's university extension (see DATA.sources). Only Region 3 (Denver-area fields) is validated.
 */
import DATA from './turfRegions.json';

export { DATA };
export const REGIONS = DATA.regions;
export const VALIDATED_REGION = DATA.validated_region;

export function regionById(id) {
  return REGIONS.find((r) => r.id === id) || null;
}

// Ray casting: is (lon, lat) inside the ring [[lon, lat], ...]? (Same as backend/regions.py.)
function pointInRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0; i < ring.length - 1; i += 1) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    if ((y1 > lat) !== (y2 > lat)) {
      const xCross = x1 + ((lat - y1) * (x2 - x1)) / (y2 - y1);
      if (lon < xCross) inside = !inside;
    }
  }
  return inside;
}

// The region id (1-7) for a location, or null outside the mapped area.
export function detectRegion(lon, lat) {
  const found = REGIONS.find((r) => pointInRing(lon, lat, r.zone.coordinates[0]));
  return found ? found.id : null;
}

// The region of a drawn field (GeoJSON Polygon), from the middle of its bounding box.
export function regionOfPolygon(geojson) {
  if (!geojson) return null;
  const ring = geojson.coordinates[0];
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return detectRegion((Math.min(...lons) + Math.max(...lons)) / 2, (Math.min(...lats) + Math.max(...lats)) / 2);
}

export function regionStatus(id) {
  return id === VALIDATED_REGION ? 'Validated (Denver-area fields)' : 'Not validated for this region yet';
}
