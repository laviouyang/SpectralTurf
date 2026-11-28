/*
 * MapView.jsx - The Leaflet map with polygon drawing tools.
 *
 * The map tells App about shapes through onPolygonChange(...) (the turf outline)
 * and onExclusionsChange(...) (parts inside it that are not turf).
 * App tells the map what to do through these props:
 *   polygon       - when App sets it to null (Clear button), we erase the drawing
 *   exclusions    - when App sets it to [] (Remove exclusions), we erase them
 *   editing       - true: show draggable corners; false: hide them and save the shape
 *   excludeRequest- { kind: 'rectangle' | 'polygon' }: start drawing an excluded area
 *   loadRequest   - { geometry, exclusions }: draw a saved outline (from "Show on map")
 *
 * 2026-11-27 (student request): a field can be SEVERAL shapes. Drawing another outline shape ADDS
 * it to the field instead of replacing it ("Clear area" starts over). Overlapping shapes are merged
 * (fieldShapes.js); separate shapes become one field with several pieces (MultiPolygon).
 * Map buttons, in this order: draw polygon (+), draw rectangle (+), exclude polygon (−),
 * exclude rectangle (−); the icons are in App.css.
 *   searchTarget  - when a search result is picked, we zoom to it
 *   overlay       - an analysis picture ({ url, bounds }) to lay over the field, or null
 */
import { useEffect, useRef } from 'react';
import L from './leafletSetup';
import 'leaflet-draw';
import { mergeShapes, outerRings } from './fieldShapes.js';

// Roughly the middle of Colorado, zoomed out to show the whole state.
const COLORADO_CENTER = [39.0, -105.55];
const COLORADO_ZOOM = 7;

// interactive: false = the shape ignores mouse clicks, so clicks go through it to
// the map. Without this, clicking inside the outline (e.g. to draw an excluded
// area) was swallowed by the outline and no corner was placed.
const SHAPE_STYLE = { color: '#ff7800', weight: 2, fillOpacity: 0.15, interactive: false };
// Excluded areas: dashed dark outline with a gray fill. "exclusion: true" is our
// own tag, so we can tell these shapes apart from the outline when they are finished.
const EXCLUDE_STYLE = {
  color: '#333333',
  weight: 2,
  dashArray: '6 4',
  fillColor: '#777777',
  fillOpacity: 0.45,
  interactive: false,
  exclusion: true,
};

// Hover labels for the drawing toolbar, so it is clear these draw the OUTLINE.
// 2026-11-27: drawing another shape ADDS it to the field.
L.drawLocal.draw.toolbar.buttons.polygon = 'Add turf: draw a polygon (draw more shapes to add more areas to the same field)';
L.drawLocal.draw.toolbar.buttons.rectangle = 'Add turf: draw a rectangle (draw more shapes to add more areas to the same field)';

// Start drawing one excluded area (used by the map's ✂ buttons and the sidebar buttons).
function startExcluding(map, kind) {
  const Tool = kind === 'polygon' ? L.Draw.Polygon : L.Draw.Rectangle;
  const tool = new Tool(map, { showArea: false, allowIntersection: false, shapeOptions: EXCLUDE_STYLE });
  tool.enable();
  return tool;
}

// A small map toolbar with the two Exclude (−) buttons, placed under the drawing tools.
// 2026-11-27: order polygon then rectangle (same as the drawing tools); icons in App.css.
function excludeControl(onClick) {
  const control = L.control({ position: 'topleft' });
  control.onAdd = () => {
    const bar = L.DomUtil.create('div', 'leaflet-bar exclude-control');
    for (const [kind, title] of [
      ['polygon', 'Exclude a polygon inside the outline (not turf, e.g. a track or path)'],
      ['rectangle', 'Exclude a rectangle inside the outline (not turf, e.g. a dirt infield)'],
    ]) {
      const button = L.DomUtil.create('a', `exclude-${kind}`, bar);
      button.href = '#';
      button.title = title;
      button.setAttribute('aria-label', title);
      button.setAttribute('role', 'button');
      L.DomEvent.on(button, 'click', (event) => {
        L.DomEvent.preventDefault(event);
        onClick(kind);
      });
    }
    L.DomEvent.disableClickPropagation(bar); // clicking a button must not click the map
    return bar;
  };
  return control;
}

// Turn a drawn Leaflet shape into plain data that the rest of the app can use.
function describeLayer(layer) {
  const bounds = layer.getBounds();
  return {
    // GeoJSON is the standard format we send to the backend.
    geojson: layer.toGeoJSON().geometry,
    // Area on the curved Earth, in square meters (helper from Leaflet.draw).
    areaM2: L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]),
    bounds: {
      west: bounds.getWest(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      north: bounds.getNorth(),
    },
    // True if two edges cross each other (a "bow tie" shape).
    selfIntersects: layer.intersects(),
  };
}

// GeoJSON corners are [longitude, latitude]; Leaflet wants [latitude, longitude].
function ringToLatLngs(ring) {
  return ring.slice(0, -1).map(([lon, lat]) => [lat, lon]);
}

// 2026-11-27: merge overlapping outline shapes into pieces that don't overlap. Enclosed gaps
// become excluded areas. Returns true if excluded areas were added. Shapes whose edges cross
// themselves are left alone (the sidebar then asks the user to fix them).
function mergeOutlineLayers(drawnItems, excludedItems) {
  const layers = drawnItems.getLayers();
  if (layers.length < 2 || layers.some((layer) => layer.intersects())) return false;
  const { geojson, holes } = mergeShapes(layers.map((layer) => layer.toGeoJSON().geometry));
  drawnItems.clearLayers();
  for (const ring of outerRings(geojson)) drawnItems.addLayer(L.polygon(ringToLatLngs(ring), SHAPE_STYLE));
  for (const hole of holes) excludedItems.addLayer(L.polygon(ringToLatLngs(hole.coordinates[0]), EXCLUDE_STYLE));
  return holes.length > 0;
}

// 2026-11-27: the whole field (all outline shapes) as the same kind of data describeLayer gives.
function describeField(drawnItems) {
  const layers = drawnItems.getLayers();
  if (layers.length === 1) return { ...describeLayer(layers[0]), parts: 1 };
  const bounds = drawnItems.getBounds();
  return {
    geojson: { type: 'MultiPolygon', coordinates: layers.map((layer) => layer.toGeoJSON().geometry.coordinates) },
    areaM2: layers.reduce((sum, layer) => sum + L.GeometryUtil.geodesicArea(layer.getLatLngs()[0]), 0),
    bounds: { west: bounds.getWest(), south: bounds.getSouth(), east: bounds.getEast(), north: bounds.getNorth() },
    selfIntersects: layers.some((layer) => layer.intersects()),
    parts: layers.length,
  };
}

export default function MapView({
  polygon,
  onPolygonChange,
  exclusions,
  onExclusionsChange,
  editing,
  onEditingChange,
  excludeRequest,
  searchTarget,
  loadRequest,
  overlay,
}) {
  const containerRef = useRef(null); // the <div> the map lives in
  const mapRef = useRef(null); // the Leaflet map object
  const drawnItemsRef = useRef(null); // the layer holding the user's outline
  const excludedItemsRef = useRef(null); // the layer holding excluded areas

  // 1. Create the map once, when the component first appears.
  useEffect(() => {
    const map = L.map(containerRef.current).setView(COLORADO_CENTER, COLORADO_ZOOM);

    // Two background maps the user can switch between (top-right button).
    // These are ONLY for finding and outlining the field. The analysis
    // itself uses Sentinel-2 data from our backend.
    const satellite = L.tileLayer(
      'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
      {
        maxZoom: 19,
        attribution:
          'Imagery &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community',
      }
    );
    const streets = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    });
    // Version 2 (student request): start on the street map; the satellite photo is one click away.
    streets.addTo(map);
    L.control.layers({ 'Satellite photo (Esri)': satellite, 'Street map (OpenStreetMap)': streets }).addTo(map);
    L.control.scale({ metric: true, imperial: true }).addTo(map);

    // A layer for the analysis pictures, placed under the drawn shapes so they
    // stay visible on top (Leaflet's shape layer is at level 400).
    map.createPane('analysis');
    map.getPane('analysis').style.zIndex = 350;

    // The layers that hold the user's outline and excluded areas.
    const drawnItems = new L.FeatureGroup();
    const excludedItems = new L.FeatureGroup();
    map.addLayer(drawnItems);
    map.addLayer(excludedItems);

    // The drawing toolbar (top-left). Only polygons and rectangles are allowed.
    // showArea is off because of a known Leaflet.draw bug; we compute area ourselves.
    // There is no edit/delete toolbar: the sidebar's buttons do that.
    const drawControl = new L.Control.Draw({
      draw: {
        polygon: {
          allowIntersection: false, // don't let edges cross while drawing
          showArea: false,
          drawError: { color: '#d00000', message: 'Edges cannot cross each other.' },
          shapeOptions: SHAPE_STYLE,
        },
        rectangle: { showArea: false, shapeOptions: SHAPE_STYLE },
        polyline: false,
        circle: false,
        circlemarker: false,
        marker: false,
      },
    });
    map.addControl(drawControl);

    // The ✂ Exclude buttons. They only make sense once there is an outline.
    excludeControl((kind) => {
      if (drawnItems.getLayers().length === 0) return;
      startExcluding(map, kind);
    }).addTo(map);

    // Starting a new drawing ends any editing that was in progress.
    map.on(L.Draw.Event.DRAWSTART, () => onEditingChange(false));

    map.on(L.Draw.Event.CREATED, (event) => {
      // An excluded area was finished: add it to the list.
      if (event.layer.options.exclusion) {
        excludedItems.addLayer(event.layer);
        onExclusionsChange(excludedItems.getLayers().map(describeLayer));
        return;
      }
      // A new outline shape was finished. 2026-11-27: it is ADDED to the field (it used to
      // replace the old outline). Overlapping shapes are merged; excluded areas are kept.
      drawnItems.addLayer(event.layer);
      const gapsExcluded = mergeOutlineLayers(drawnItems, excludedItems);
      onPolygonChange(describeField(drawnItems));
      if (gapsExcluded) onExclusionsChange(excludedItems.getLayers().map(describeLayer));
    });

    mapRef.current = map;
    drawnItemsRef.current = drawnItems;
    excludedItemsRef.current = excludedItems;

    // Clean up if the component is removed (also needed for React dev mode).
    return () => map.remove();
  }, [onPolygonChange, onExclusionsChange, onEditingChange]);

  // When App switches editing on, show draggable corners.
  // When it switches editing off ("Save shape"), hide them and report the new shape.
  // 2026-11-27: every shape of the field can be edited; on Save, overlapping shapes are merged.
  useEffect(() => {
    const drawnItems = drawnItemsRef.current;
    const layers = drawnItems?.getLayers() || [];
    if (layers.length === 0) return;
    if (editing) {
      layers.forEach((layer) => layer.editing.enable());
    } else if (layers.some((layer) => layer.editing.enabled())) {
      layers.forEach((layer) => layer.editing.disable());
      const gapsExcluded = mergeOutlineLayers(drawnItems, excludedItemsRef.current);
      onPolygonChange(describeField(drawnItems));
      if (gapsExcluded) onExclusionsChange(excludedItemsRef.current.getLayers().map(describeLayer));
    }
  }, [editing, onPolygonChange, onExclusionsChange]);

  // 2. When App clears the outline or the exclusions, erase them from the map too.
  useEffect(() => {
    if (polygon === null && drawnItemsRef.current) {
      drawnItemsRef.current.clearLayers();
    }
  }, [polygon]);
  useEffect(() => {
    if (exclusions.length === 0 && excludedItemsRef.current) {
      excludedItemsRef.current.clearLayers();
    }
  }, [exclusions]);

  // 3. Start drawing an excluded area when App asks (the "Exclude" buttons).
  useEffect(() => {
    if (!excludeRequest || !mapRef.current) return;
    const tool = startExcluding(mapRef.current, excludeRequest.kind);
    return () => tool.disable(); // stop if another request comes in first
  }, [excludeRequest]);

  // 4. When a search result is chosen, zoom the map to it.
  useEffect(() => {
    if (!searchTarget || !mapRef.current) return;
    const { south, west, north, east } = searchTarget;
    mapRef.current.fitBounds([[south, west], [north, east]], { maxZoom: 17 });
  }, [searchTarget]);

  // 5. Draw a saved field (from the account history) as if the user had just drawn it.
  useEffect(() => {
    if (!loadRequest || !mapRef.current) return;
    // 2026-11-27: a saved field can have several pieces (MultiPolygon): draw each one.
    drawnItemsRef.current.clearLayers();
    excludedItemsRef.current.clearLayers();
    for (const ring of outerRings(loadRequest.geometry)) {
      drawnItemsRef.current.addLayer(L.polygon(ringToLatLngs(ring), SHAPE_STYLE));
    }
    for (const shape of loadRequest.exclusions) {
      excludedItemsRef.current.addLayer(L.polygon(ringToLatLngs(shape.coordinates[0]), EXCLUDE_STYLE));
    }
    onPolygonChange(describeField(drawnItemsRef.current));
    onExclusionsChange(excludedItemsRef.current.getLayers().map(describeLayer));
    mapRef.current.fitBounds(drawnItemsRef.current.getBounds(), { maxZoom: 18 });
  }, [loadRequest, onPolygonChange, onExclusionsChange]);

  // 6. Show the chosen analysis picture (NDVI, NDMI, or true color) over the field.
  // The picture covers exactly the box the backend analyzed. The "pixel-image" CSS
  // class keeps each satellite pixel a sharp square instead of a blurry blend.
  useEffect(() => {
    if (!overlay || !mapRef.current) return;
    const { west, south, east, north } = overlay.bounds;
    const layer = L.imageOverlay(overlay.url, [[south, west], [north, east]], {
      pane: 'analysis',
      className: 'pixel-image',
      opacity: 0.9,
    }).addTo(mapRef.current);
    return () => layer.remove(); // remove it when the choice or the result changes
  }, [overlay]);

  return <div ref={containerRef} className="map" />;
}
