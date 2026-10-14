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
 *   searchTarget  - when a search result is picked, we zoom to it
 *   overlay       - an analysis picture ({ url, bounds }) to lay over the field, or null
 */
import { useEffect, useRef } from 'react';
import L from './leafletSetup';
import 'leaflet-draw';

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
L.drawLocal.draw.toolbar.buttons.polygon = 'Draw turf outline as a polygon (replaces the current outline)';
L.drawLocal.draw.toolbar.buttons.rectangle = 'Draw turf outline as a rectangle (replaces the current outline)';

// Start drawing one excluded area (used by the map's ✂ buttons and the sidebar buttons).
function startExcluding(map, kind) {
  const Tool = kind === 'polygon' ? L.Draw.Polygon : L.Draw.Rectangle;
  const tool = new Tool(map, { showArea: false, allowIntersection: false, shapeOptions: EXCLUDE_STYLE });
  tool.enable();
  return tool;
}

// A small map toolbar with the two ✂ Exclude buttons, placed under the drawing tools.
function excludeControl(onClick) {
  const control = L.control({ position: 'topleft' });
  control.onAdd = () => {
    const bar = L.DomUtil.create('div', 'leaflet-bar exclude-control');
    for (const [kind, label, title] of [
      ['rectangle', '✂▭', 'Exclude a rectangle inside the outline (not turf, e.g. a dirt infield)'],
      ['polygon', '✂⬠', 'Exclude a polygon inside the outline (not turf, e.g. a track or path)'],
    ]) {
      const button = L.DomUtil.create('a', '', bar);
      button.href = '#';
      button.textContent = label;
      button.title = title;
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

export default function MapView({
  polygon,
  onPolygonChange,
  exclusions,
  onExclusionsChange,
  editing,
  onEditingChange,
  excludeRequest,
  searchTarget,
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
    satellite.addTo(map);
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
      // A new outline was finished: keep only this one (drawing again = redraw).
      // Old excluded areas belonged to the old outline, so they are removed too.
      drawnItems.clearLayers();
      excludedItems.clearLayers();
      drawnItems.addLayer(event.layer);
      onPolygonChange(describeLayer(event.layer));
      onExclusionsChange([]);
    });

    mapRef.current = map;
    drawnItemsRef.current = drawnItems;
    excludedItemsRef.current = excludedItems;

    // Clean up if the component is removed (also needed for React dev mode).
    return () => map.remove();
  }, [onPolygonChange, onExclusionsChange, onEditingChange]);

  // When App switches editing on, show draggable corners.
  // When it switches editing off ("Save shape"), hide them and report the new shape.
  useEffect(() => {
    const layer = drawnItemsRef.current?.getLayers()[0];
    if (!layer) return;
    if (editing) {
      layer.editing.enable();
    } else if (layer.editing.enabled()) {
      layer.editing.disable();
      onPolygonChange(describeLayer(layer));
    }
  }, [editing, onPolygonChange]);

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

  // 5. Show the chosen analysis picture (NDVI, NDMI, or true color) over the field.
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
