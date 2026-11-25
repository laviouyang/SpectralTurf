/*
 * region.js - Version 2 (2026-11-25): where SpectralTurf is "available".
 *
 * Search now works for any address, but the AI was trained only on real Colorado
 * (Denver-area) fields, and the inspection cutoffs were chosen from Colorado fields.
 * So the app warns when a place is outside Colorado. The homepage lists every state,
 * with all except Colorado marked "coming soon".
 */

// Colorado's borders are almost exactly a lat/long rectangle (about 37–41 °N, 102.04–109.06 °W).
const COLORADO = { south: 36.99, north: 41.0, west: -109.06, east: -102.04 };

export function isInColorado(lat, lon) {
  return lat >= COLORADO.south && lat <= COLORADO.north && lon >= COLORADO.west && lon <= COLORADO.east;
}

// The middle of a GeoJSON polygon's outline (good enough to tell which state a field is in).
export function polygonCenter(geojson) {
  const ring = geojson.coordinates[0];
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  return { lat: (Math.min(...lats) + Math.max(...lats)) / 2, lon: (Math.min(...lons) + Math.max(...lons)) / 2 };
}

export const OUTSIDE_COLORADO_MESSAGE =
  'This place is outside Colorado. The satellite measurements (NDVI, NDMI) are real anywhere, ' +
  'but the AI was trained only on Colorado fields, and the inspection cutoffs were chosen from ' +
  'Colorado fields, so the results here may not be accurate.';

export const AVAILABLE_STATE = 'Colorado';

export const US_STATES = [
  'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado', 'Connecticut', 'Delaware',
  'Florida', 'Georgia', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas', 'Kentucky',
  'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota', 'Mississippi',
  'Missouri', 'Montana', 'Nebraska', 'Nevada', 'New Hampshire', 'New Jersey', 'New Mexico',
  'New York', 'North Carolina', 'North Dakota', 'Ohio', 'Oklahoma', 'Oregon', 'Pennsylvania',
  'Rhode Island', 'South Carolina', 'South Dakota', 'Tennessee', 'Texas', 'Utah', 'Vermont',
  'Virginia', 'Washington', 'West Virginia', 'Wisconsin', 'Wyoming',
];
