/*
 * make_us_map.mjs - builds src/usMap.json, the picture data for the homepage grass-region map
 * (added 2026-11-25). Run from the frontend folder:   node scripts/make_us_map.mjs
 *
 * State shapes: U.S. Census Bureau cartographic boundaries, from the us-atlas package (ISC
 * license; Census data is public domain). Alaska, Hawaii and the territories are left out.
 * Region zones: src/turfRegions.json (approximate, drawn by hand). Both go through the SAME map
 * projection (Albers, the usual one for US maps), so the regions line up with the states.
 * The website only loads the finished usMap.json; these packages are not shipped to visitors.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { merge, mesh } from 'topojson-client';
import { presimplify, quantile, simplify } from 'topojson-simplify';
import { geoAlbers, geoPath } from 'd3-geo';

const read = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf-8'));
const us = read('../node_modules/us-atlas/states-10m.json');
const regions = read('../src/turfRegions.json');

// Keep the 48 states + DC (drop Alaska 02, Hawaii 15, and the territories).
const DROP = new Set(['02', '15', '60', '66', '69', '72', '78']);
us.objects.states.geometries = us.objects.states.geometries.filter((g) => !DROP.has(g.id));

// Fewer points = a smaller file; 0.6 keeps the shapes clearly recognisable at this size.
const pre = presimplify(us);
const topo = simplify(pre, quantile(pre, 0.6));
const nation = merge(topo, topo.objects.states.geometries);
const borders = mesh(topo, topo.objects.states, (a, b) => a !== b); // lines between states

// Albers projection fitted into the picture, with room on the left for Region 1's label.
const WIDTH = 960;
const HEIGHT = 560;
const projection = geoAlbers().parallels([29.5, 45.5]).rotate([96, 0]).center([-0.6, 38.7])
  .fitExtent([[95, 12], [WIDTH - 12, HEIGHT - 12]], nation);
const path = geoPath(projection).digits(1);

// Region zones: straight lines between their corners (they are approximate anyway).
const round = (v) => Math.round(v * 10) / 10;
const zonePath = (ring) => `M${ring.map((p) => projection(p).map(round).join(',')).join('L')}Z`;

const out = {
  about: 'Made by scripts/make_us_map.mjs. States: U.S. Census Bureau via us-atlas. Regions: turfRegions.json (approximate).',
  width: WIDTH,
  height: HEIGHT,
  nation: path(nation),
  borders: path(borders),
  zones: Object.fromEntries(regions.regions.map((r) => [r.id, zonePath(r.zone.coordinates[0])])),
  labels: Object.fromEntries(regions.regions.map((r) => [r.id, projection(r.label).map(round)])),
};
writeFileSync(new URL('../src/usMap.json', import.meta.url), `${JSON.stringify(out)}\n`);
console.log('usMap.json written:', JSON.stringify(out).length, 'characters');
