/*
 * fieldShapes.js - A field can be SEVERAL shapes (added 2026-11-27, student request).
 *
 * Parks often have several grass fields with walkways between them. Instead of drawing one big
 * outline and excluding every walkway, you can draw several shapes; together they are ONE field.
 *
 * GeoJSON sent to the backend (backend/field_shape.py checks it again):
 *   - one shape          -> Polygon       (exactly as before)
 *   - separate shapes    -> MultiPolygon  (one entry per piece)
 * Shapes that overlap or touch are merged into one piece (polygon-clipping library, MIT), so a
 * piece is never counted twice. If merging leaves an enclosed gap (shapes drawn around a hole),
 * the gap becomes an excluded area, because nobody drew turf there.
 */
import polygonClipping from 'polygon-clipping';

export const MAX_FIELD_PARTS = 20; // same as backend/field_shape.py

// The outline ring of every piece.
export function outerRings(geojson) {
  if (!geojson) return [];
  return geojson.type === 'MultiPolygon' ? geojson.coordinates.map((part) => part[0]) : [geojson.coordinates[0]];
}

// The middle of the box around all pieces, { lon, lat }.
export function boxCenter(geojson) {
  const points = outerRings(geojson).flat();
  const lons = points.map((p) => p[0]);
  const lats = points.map((p) => p[1]);
  return { lon: (Math.min(...lons) + Math.max(...lons)) / 2, lat: (Math.min(...lats) + Math.max(...lats)) / 2 };
}

// Merge drawn shapes (GeoJSON Polygons) into one field.
// Returns { geojson, holes }: geojson is a Polygon (one piece) or MultiPolygon (several);
// holes are enclosed gaps left by the merge, as GeoJSON Polygons (usually none).
export function mergeShapes(polygons) {
  if (polygons.length === 1) return { geojson: polygons[0], holes: [] }; // one shape: unchanged
  const merged = polygonClipping.union(...polygons.map((p) => p.coordinates));
  const pieces = merged.map((poly) => [poly[0]]);
  const holes = merged.flatMap((poly) => poly.slice(1)).map((ring) => ({ type: 'Polygon', coordinates: [ring] }));
  const geojson = pieces.length === 1
    ? { type: 'Polygon', coordinates: pieces[0] }
    : { type: 'MultiPolygon', coordinates: pieces };
  return { geojson, holes };
}
