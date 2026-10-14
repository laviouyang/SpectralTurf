/*
 * App.jsx - The main page: sidebar (search + selected area) and the map.
 *
 * Stage 4: search, draw, edit, clear.
 * Stage 5: Analyze sends the polygon to the backend and shows the real results.
 * Stage 8: "Exclude" areas inside the outline that are not turf (e.g. dirt infields).
 */
import { useCallback, useMemo, useRef, useState } from 'react';
import MapView from './MapView.jsx';
import SearchBox from './SearchBox.jsx';
import Results from './Results.jsx';
import { analyzeArea } from './api.js';
import { checkPolygon } from './polygonCheck.js';

export default function App() {
  // The drawn area (or null if nothing is drawn yet).
  const [polygon, setPolygon] = useState(null);
  // Parts inside the outline that are not turf, like dirt infields (list of shapes).
  const [exclusions, setExclusions] = useState([]);
  // Set when an "Exclude" button is clicked; tells the map to start drawing one.
  const [excludeRequest, setExcludeRequest] = useState(null);
  // True while the user is dragging corners (between "Edit shape" and "Save shape").
  const [editing, setEditing] = useState(false);
  // The place picked in the search box; the map zooms to it.
  const [searchTarget, setSearchTarget] = useState(null);

  // Analysis options and results.
  const [start, setStart] = useState('2026-06-01');
  const [end, setEnd] = useState('2026-08-31');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  // Counts analyses, so an old, slow answer can't show up for a newer shape.
  const requestCount = useRef(0);
  // Which analysis picture is shown on the map: 'ndvi', 'ndmi', 'true_color', or 'none'.
  const [layer, setLayer] = useState('ndvi');

  // The picture for the map. useMemo keeps it the same object until the result
  // or layer changes, so the map doesn't redraw it on every keystroke.
  const overlay = useMemo(() => {
    if (!result || layer === 'none') return null;
    return { url: result.images[layer], bounds: result.box };
  }, [result, layer]);

  const check = polygon ? checkPolygon(polygon) : null;
  const datesOk = start && end && start <= end;
  const canAnalyze = check?.ok && !editing && !loading && datesOk;

  // Whenever the shapes change, old results no longer match them, so remove them.
  // (useCallback keeps these the same functions, so the map isn't rebuilt.)
  const forgetResults = useCallback(() => {
    requestCount.current += 1;
    setResult(null);
    setError('');
    setLoading(false);
  }, []);
  const handlePolygonChange = useCallback((newPolygon) => {
    setPolygon(newPolygon);
    forgetResults();
  }, [forgetResults]);
  const handleExclusionsChange = useCallback((newExclusions) => {
    setExclusions(newExclusions);
    forgetResults();
  }, [forgetResults]);

  function clearArea() {
    setEditing(false);
    handlePolygonChange(null);
    handleExclusionsChange([]);
  }

  // Roughly how much is excluded (overlaps or parts outside the outline would be
  // counted twice, so this is "about"; the backend reports the exact pixel count).
  const excludedM2 = exclusions.reduce((sum, shape) => sum + shape.areaM2, 0);

  async function handleAnalyze() {
    const thisRequest = ++requestCount.current;
    setLoading(true);
    setResult(null);
    setError('');
    try {
      const exclude = exclusions.map((shape) => shape.geojson);
      const data = await analyzeArea(polygon.geojson, exclude, start, end);
      if (thisRequest === requestCount.current) setResult(data);
    } catch (e) {
      if (thisRequest === requestCount.current) setError(e.message);
    } finally {
      if (thisRequest === requestCount.current) setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>SpectralTurf AI</h1>
        <p>
          Outline sports-field turf in Colorado to check it with real Sentinel-2 satellite data.
          Results help decide where a person may want to look more closely. They are not a diagnosis.
        </p>
      </header>

      <main className="layout">
        <aside className="sidebar">
          <section>
            <h2>1. Find a place</h2>
            <SearchBox onSelect={setSearchTarget} />
          </section>

          <section>
            <h2>2. Outline the turf</h2>
            <ol className="steps">
              <li>Click the <strong>polygon</strong> (pentagon) or <strong>rectangle</strong> tool at the top left of the map.</li>
              <li>Click around the grass. Click the first point again to finish.</li>
              <li>Include <strong>only turf</strong>. Leave out pavement and buildings around the field.</li>
              <li>
                Dirt infields, tracks, or paths <strong>inside</strong> the field? Cut them out with the{' '}
                <strong>✂ buttons</strong> on the map (or the Exclude buttons below). The pentagon and
                square tools always draw a <em>new</em> outline.
              </li>
              <li>To adjust it, click <strong>Edit shape</strong>, drag the corners, then <strong>Save shape</strong>. Drawing again replaces it.</li>
            </ol>
          </section>

          <section>
            <h2>3. Selected area</h2>
            {!polygon && <p className="muted">No area selected yet. Draw a shape on the map.</p>}

            {check && (
              <>
                <ul className="facts">
                  <li>
                    Area: {Math.round(check.facts.areaM2).toLocaleString()} m² ({check.facts.acres.toFixed(2)} acres)
                  </li>
                  <li>About {check.facts.pixels10m.toLocaleString()} Sentinel-2 pixels at 10 m (NDVI)</li>
                  <li>About {check.facts.pixels20m.toLocaleString()} pixels at 20 m (NDMI is coarser)</li>
                </ul>

                {editing ? (
                  <p className="muted">
                    Editing: drag the white squares on the map to move corners. The numbers above
                    update when you click <strong>Save shape</strong>.
                  </p>
                ) : check.ok ? (
                  <p className="ok">✓ This area can be analyzed.</p>
                ) : (
                  <ul className="problems">
                    {check.problems.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                )}

                <div className="button-row">
                  {editing ? (
                    <button type="button" onClick={() => setEditing(false)}>
                      Save shape
                    </button>
                  ) : (
                    <button type="button" className="secondary" onClick={() => setEditing(true)}>
                      Edit shape
                    </button>
                  )}
                  <button type="button" className="secondary" onClick={clearArea}>
                    Clear area
                  </button>
                </div>

                <div className="exclude-box">
                  <p>
                    <strong>Leave out non-turf parts</strong>
                    <br />
                    <span className="muted">
                      Inside your outline, cover anything that is not supposed to be grass (dirt
                      infields, tracks, paths). Those pixels are not analyzed at all. Use these
                      buttons or the ✂ buttons on the map, once for each area.
                    </span>
                  </p>
                  <div className="button-row">
                    <button
                      type="button"
                      className="secondary"
                      disabled={editing}
                      onClick={() => setExcludeRequest({ kind: 'rectangle' })}
                    >
                      Exclude a rectangle
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      disabled={editing}
                      onClick={() => setExcludeRequest({ kind: 'polygon' })}
                    >
                      Exclude a polygon
                    </button>
                  </div>
                  {exclusions.length > 0 && (
                    <p className="muted">
                      Excluded: {exclusions.length} area{exclusions.length > 1 ? 's' : ''}, about{' '}
                      {Math.round(excludedM2).toLocaleString()} m².{' '}
                      <button type="button" className="link-button" onClick={() => handleExclusionsChange([])}>
                        Remove exclusions
                      </button>
                    </p>
                  )}
                </div>

                <details>
                  <summary>Coordinates (GeoJSON sent to the backend)</summary>
                  <p className="muted">GeoJSON lists each corner as [longitude, latitude].</p>
                  <pre>{JSON.stringify(polygon.geojson, null, 2)}</pre>
                </details>
              </>
            )}
          </section>

          <section>
            <h2>4. Analyze</h2>
            <div className="dates">
              <label>
                From
                <input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </label>
              <label>
                To
                <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </label>
            </div>
            {!datesOk && <p className="problems">The start date must be on or before the end date.</p>}
            <p className="muted">
              The app picks the least-cloudy Sentinel-2 image in this date range.
            </p>

            <button type="button" onClick={handleAnalyze} disabled={!canAnalyze}>
              {loading ? 'Analyzing…' : 'Analyze'}
            </button>
            {!polygon && <p className="muted">Draw an area first.</p>}
            {editing && <p className="muted">Click Save shape before analyzing.</p>}
            {loading && (
              <p className="muted">Downloading real Sentinel-2 data. This can take up to a minute.</p>
            )}
            {error && (
              <p className="problems-box">
                <strong>Analysis failed.</strong> {error}
              </p>
            )}
            {result && <Results result={result} layer={layer} onLayerChange={setLayer} />}
          </section>

          <section className="limits">
            <h2>Good to know</h2>
            <p>
              Sentinel-2 pixels are 10 m wide (20 m for moisture), so small dry patches may not show up,
              and pixels at the edges can mix grass with dirt or pavement. The background photo is only
              for drawing. The analysis uses Sentinel-2 data.
            </p>
          </section>
        </aside>

        <MapView
          polygon={polygon}
          onPolygonChange={handlePolygonChange}
          exclusions={exclusions}
          onExclusionsChange={handleExclusionsChange}
          excludeRequest={excludeRequest}
          editing={editing}
          onEditingChange={setEditing}
          searchTarget={searchTarget}
          overlay={overlay}
        />
      </main>
    </div>
  );
}
