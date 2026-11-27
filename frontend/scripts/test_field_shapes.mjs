// test_field_shapes.mjs - Checks for fieldShapes.js (added 2026-11-27): a field drawn as several shapes.
// Also writes backend/field_shape_cases.json: fields made from RANDOM shapes, merged exactly like the
// website does (incl. Leaflet's rounding to 6 decimals). backend/test_multipart.py then checks that the
// backend accepts every one of them (no "pieces must not overlap" surprises).
//
// Run (in frontend):   node scripts/test_field_shapes.mjs
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { boxCenter, mergeShapes, outerRings } from '../src/fieldShapes.js';

let passed = 0;
function check(name, ok) {
  if (!ok) throw new Error(`FAIL ${name}`);
  passed += 1;
  console.log(`PASS ${name}`);
}

const box = (w, s, e, n) => ({ type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] });
const A = box(-104.879, 39.6337, -104.8784, 39.6344);
const B = box(-104.879, 39.6355, -104.8784, 39.6360);

check('1. one shape is returned unchanged', mergeShapes([A]).geojson === A);
const separate = mergeShapes([A, B]).geojson;
check('2. two separate shapes -> MultiPolygon with 2 pieces', separate.type === 'MultiPolygon' && outerRings(separate).length === 2);
const joined = mergeShapes([A, box(-104.8787, 39.634, -104.878, 39.635)]).geojson;
check('3. two overlapping shapes -> ONE piece (Polygon)', joined.type === 'Polygon' && joined.coordinates.length === 1);
const touching = mergeShapes([A, box(-104.8784, 39.6337, -104.8778, 39.6344)]).geojson;
check('4. shapes that share an edge -> ONE piece', touching.type === 'Polygon');
// Four bars drawn around an empty middle: the middle was not drawn, so it becomes an excluded area.
const frame = mergeShapes([
  box(0, 0, 4, 1), box(0, 3, 4, 4), box(0, 0, 1, 4), box(3, 0, 4, 4),
]);
check('5. shapes drawn around a gap -> one piece + the gap as an excluded area',
  frame.geojson.type === 'Polygon' && frame.holes.length === 1 && frame.geojson.coordinates.length === 1);
const c = boxCenter(separate);
check('6. center of all pieces', Math.abs(c.lon + 104.8787) < 1e-9 && Math.abs(c.lat - 39.63485) < 1e-9);

// ---- random fields, like a user drawing several shapes ----
let seed = 2026;
const rand = () => {
  seed = (seed * 1103515245 + 12345) % 2147483648;
  return seed / 2147483648;
};
function randomShape() {
  const cx = -104.88 + rand() * 0.004;
  const cy = 39.63 + rand() * 0.004;
  if (rand() < 0.5) {
    const w = 0.0003 + rand() * 0.0015;
    const h = 0.0003 + rand() * 0.0015;
    return box(cx, cy, cx + w, cy + h);
  }
  // a star-shaped polygon (never crosses itself), like a hand-drawn outline
  const n = 4 + Math.floor(rand() * 7);
  const ring = [];
  for (let i = 0; i < n; i += 1) {
    const angle = (2 * Math.PI * (i + rand() * 0.8)) / n;
    const r = 0.0003 + rand() * 0.001;
    ring.push([cx + r * Math.cos(angle), cy + r * Math.sin(angle)]);
  }
  ring.push(ring[0]);
  return { type: 'Polygon', coordinates: [ring] };
}
const round6 = (v) => Math.round(v * 1e6) / 1e6; // Leaflet's toGeoJSON keeps 6 decimals
const roundRing = (ring) => ring.map(([x, y]) => [round6(x), round6(y)]);

const cases = [];
let multi = 0;
let gaps = 0;
for (let i = 0; i < 300; i += 1) {
  const shapes = Array.from({ length: 2 + Math.floor(rand() * 5) }, randomShape);
  const { geojson, holes } = mergeShapes(shapes);
  if (geojson.type === 'MultiPolygon') multi += 1;
  if (holes.length) gaps += 1;
  const rings = outerRings(geojson).map(roundRing);
  cases.push(rings.length === 1
    ? { type: 'Polygon', coordinates: [rings[0]] }
    : { type: 'MultiPolygon', coordinates: rings.map((ring) => [ring]) });
}
check(`7. 300 random fields merged (${multi} in several pieces, ${gaps} with an enclosed gap)`,
  cases.length === 300 && multi > 0 && multi < 300);
check('8. every merged piece is a closed ring with at least 3 corners',
  cases.every((g) => outerRings(g).every((r) => r.length >= 4
    && r[0][0] === r[r.length - 1][0] && r[0][1] === r[r.length - 1][1])));
const out = fileURLToPath(new URL('../../backend/field_shape_cases.json', import.meta.url));
writeFileSync(out, JSON.stringify(cases));
console.log(`(wrote ${cases.length} cases to backend/field_shape_cases.json for backend/test_multipart.py)`);
console.log(`\nAll ${passed} checks passed.`);
