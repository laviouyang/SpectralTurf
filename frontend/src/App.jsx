/*
 * App.jsx - The main page: sidebar (search + selected area) and the map.
 *
 * Stage 4: search, draw, edit, clear.
 * Stage 5: Analyze sends the polygon to the backend and shows the real results.
 * Stage 8: "Exclude" areas inside the outline that are not turf (e.g. dirt infields).
 * Accounts: optional log in; each analysis is saved to the user's history.
 * UI redesign (2026-11-23): full-screen map, slim top bar (logo, search, account menu) and a
 * floating panel with tabs (Analyze / My Fields / AI Check / Ask AI); on phones the panel is a
 * bottom sheet. Only the layout changed: the same components, state and API calls as before.
 * All tabs stay mounted (just hidden), so nothing reloads or re-runs when you switch tabs.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import MapView from './MapView.jsx';
import SearchBox from './SearchBox.jsx';
import Results from './Results.jsx';
import AccountPanel, { SavedAnalyses } from './AccountPanel.jsx';
import MyFields from './MyFields.jsx';
import WhatIf from './WhatIf.jsx';
import AIWeatherCheck from './AIWeatherCheck.jsx';
import AskSpectralTurf from './AskSpectralTurf.jsx';
import Panel from './Panel.jsx';
import { AccountMenu, EmptyState, ResultsSkeleton, Spinner } from './AppChrome.jsx';
import { Icon, Logo } from './Icons.jsx';
import { Link } from './router.jsx';
import { analyzeArea, currentUser, deleteHistoryItem, getHistory, logOut } from './api.js';
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

  // Accounts: who is logged in (null = visitor) and their saved analyses.
  const [user, setUser] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyError, setHistoryError] = useState('');
  // The name an analysis is saved under (only used when logged in).
  const [fieldName, setFieldName] = useState('');
  // Set by "Show on map": tells the map to draw a saved outline and exclusions.
  const [loadRequest, setLoadRequest] = useState(null);

  // Layout only (UI redesign): which tab is shown, the account menu, and the panel/sheet.
  const [tab, setTab] = useState('analyze');
  const [accountOpen, setAccountOpen] = useState(() => window.location.hash === '#account');
  const [sheetOpen, setSheetOpen] = useState(false); // phones: bottom sheet pulled up?
  const [panelHidden, setPanelHidden] = useState(false); // desktop: panel tucked away?
  const panelScroll = useRef(null);
  function openTab(id) {
    if (id !== tab && panelScroll.current) panelScroll.current.scrollTop = 0; // each tab starts at its top
    setTab(id);
    setSheetOpen(true);
    setPanelHidden(false);
  }
  // A new outline or a new result: show the Analyze tab so the next step is visible.
  useEffect(() => {
    if (polygon) openTab('analyze');
  }, [polygon]);

  // When the page opens, check whether a saved login is still valid.
  useEffect(() => {
    currentUser().then(setUser);
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      setHistory(await getHistory());
      setHistoryError('');
    } catch (e) {
      setHistoryError(`Could not load your saved analyses. ${e.message}`);
    }
  }, []);

  // Load the history whenever someone logs in; empty it when they log out.
  useEffect(() => {
    if (user) refreshHistory();
    else setHistory([]);
  }, [user, refreshHistory]);

  async function handleLogOut() {
    await logOut().catch(() => {});
    setUser(null);
  }

  async function handleDelete(item) {
    try {
      await deleteHistoryItem(item.id);
    } catch (e) {
      setHistoryError(e.message);
    }
    refreshHistory();
  }

  // Put a saved field back on the map with the same dates, ready to analyze again.
  function handleShowSaved(item) {
    setEditing(false);
    setStart(item.start);
    setEnd(item.end);
    setFieldName(item.name);
    setLoadRequest({ geometry: item.geometry, exclusions: item.exclusions, id: Date.now() });
  }

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
      const data = await analyzeArea(polygon.geojson, exclude, start, end, user ? fieldName : '');
      if (thisRequest === requestCount.current) setResult(data);
      if (data.saved_id) refreshHistory();
      if (data.save_error) setHistoryError(`This analysis was not saved: ${data.save_error}`);
    } catch (e) {
      if (thisRequest === requestCount.current) setError(e.message);
    } finally {
      if (thisRequest === requestCount.current) setLoading(false);
    }
  }

  const excludeShapes = exclusions.map((shape) => shape.geojson);
  const today = new Date().toLocaleDateString('en-CA');
  const TABS = [
    { id: 'analyze', label: 'Analyze', icon: 'draw' },
    { id: 'myfields', label: 'My Fields', icon: 'list' },
    { id: 'aicheck', label: 'AI Check', icon: 'chart' },
    { id: 'ask', label: 'Ask AI', icon: 'chat' },
  ];

  return (
    <div className="app-shell" data-sheet={sheetOpen ? 'open' : 'closed'} data-panel={panelHidden ? 'hidden' : 'shown'}>
      {/* ---- Slim top bar: logo, place search, account ---- */}
      <header className="app-topbar">
        <Link to="/" className="brand" aria-label="SpectralTurf home">
          <Logo size={30} />
          <span className="brand-name">SpectralTurf</span>
        </Link>
        <div className="topbar-search">
          <SearchBox
            onSelect={(target) => {
              setSearchTarget(target);
              setSheetOpen(false); // phones: show the map
            }}
          />
        </div>
        <AccountMenu user={user} open={accountOpen} onOpenChange={setAccountOpen}>
          <AccountPanel
            user={user}
            onUserChange={setUser}
            onLogOut={handleLogOut}
            history={history}
            historyError={historyError}
            onShow={(item) => {
              handleShowSaved(item);
              setAccountOpen(false);
              openTab('analyze');
            }}
            onDelete={handleDelete}
          />
        </AccountMenu>
      </header>

      <div className="app-stage">
        <MapView
          polygon={polygon}
          onPolygonChange={handlePolygonChange}
          exclusions={exclusions}
          onExclusionsChange={handleExclusionsChange}
          excludeRequest={excludeRequest}
          editing={editing}
          onEditingChange={setEditing}
          searchTarget={searchTarget}
          loadRequest={loadRequest}
          overlay={overlay}
        />

        {panelHidden && (
          <button type="button" className="panel-reveal" onClick={() => setPanelHidden(false)}>
            <Icon name="chevronRight" size={18} /> Show panel
          </button>
        )}

        {/* ---- Floating panel (desktop) / bottom sheet (phones) ---- */}
        <aside className="float-panel" aria-label="SpectralTurf tools">
          <button
            type="button"
            className="sheet-handle"
            aria-expanded={sheetOpen}
            onClick={() => setSheetOpen(!sheetOpen)}
          >
            <span className="handle-bar" aria-hidden="true" />
            <span className="visually-hidden">{sheetOpen ? 'Lower the panel' : 'Raise the panel'}</span>
          </button>
          <div className="panel-tabs" role="tablist" aria-label="Tools">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                id={`tab-${t.id}`}
                aria-selected={tab === t.id}
                aria-controls={`tabpanel-${t.id}`}
                className="panel-tab"
                onClick={() => openTab(t.id)}
              >
                <Icon name={t.icon} size={18} />
                <span>{t.label}</span>
                {t.id === 'aicheck' && result && <span className="tab-dot" title="Ready for this field" />}
              </button>
            ))}
            <button
              type="button"
              className="icon-button panel-hide"
              onClick={() => setPanelHidden(true)}
              aria-label="Hide the panel"
              title="Hide the panel"
            >
              <Icon name="chevronLeft" size={18} />
            </button>
          </div>

          <div className="panel-scroll" ref={panelScroll}>
            {/* ===== Analyze ===== */}
            <div role="tabpanel" id="tabpanel-analyze" aria-labelledby="tab-analyze" hidden={tab !== 'analyze'}>
              {!polygon ? (
                <EmptyState icon="draw" title="Draw a field to get started">
                  <ol className="steps">
                    <li>Search for a park, school, or address in the bar at the top.</li>
                    <li>Click the <strong>polygon</strong> (pentagon) or <strong>rectangle</strong> tool on the map, then click around the grass. Click the first point again to finish.</li>
                    <li>Include <strong>only turf</strong>. Leave out pavement and buildings around the field.</li>
                    <li>Dirt infields, tracks, or paths <strong>inside</strong> the field? Cut them out afterwards with the <strong>✂ buttons</strong> on the map.</li>
                  </ol>
                  <p className="muted">Want an earlier field? Open <strong>My Fields</strong> and press Show on map.</p>
                </EmptyState>
              ) : (
                <Panel
                  id="v2-field"
                  title="Your field"
                  defaultOpen
                  openWhen={polygon}
                  status={check ? (check.ok ? `${Math.round(check.facts.areaM2).toLocaleString()} m²` : '⚠ needs a fix') : null}
                >
                  {check && (
                    <>
                      <div className="key-numbers">
                        <div className="key-number">
                          <span className="key-value">{check.facts.acres.toFixed(2)}</span>
                          <span className="key-label">acres</span>
                        </div>
                        <div className="key-number">
                          <span className="key-value">{check.facts.pixels10m.toLocaleString()}</span>
                          <span className="key-label">10 m pixels (NDVI)</span>
                        </div>
                        <div className="key-number">
                          <span className="key-value">{check.facts.pixels20m.toLocaleString()}</span>
                          <span className="key-label">20 m pixels (NDMI)</span>
                        </div>
                      </div>

                      {editing ? (
                        <p className="notice notice-info">
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
                </Panel>
              )}

              <Panel
                id="v2-analysis"
                title="Satellite analysis"
                defaultOpen
                openWhen={result}
                status={loading ? 'analyzing…' : result ? `image ${result.observation?.date}` : null}
              >
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
                {user && (
                  <label className="field-name">
                    Field name (for your saved history)
                    <input
                      value={fieldName}
                      maxLength={80}
                      placeholder="e.g. Village Greens north field"
                      onChange={(e) => setFieldName(e.target.value)}
                    />
                  </label>
                )}

                <button type="button" className="btn-block" onClick={handleAnalyze} disabled={!canAnalyze}>
                  {loading && <Spinner />}
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
              </Panel>

              {loading && <ResultsSkeleton />}
              {result && <Results result={result} layer={layer} onLayerChange={setLayer} />}
              {result && (
                <button type="button" className="secondary btn-block" onClick={() => openTab('aicheck')}>
                  <Icon name="chart" size={18} /> See the AI Weather Check for this field
                </button>
              )}

              <Panel id="v2-goodtoknow" title="Good to know" className="limits">
                <p>
                  Sentinel-2 pixels are 10 m wide (20 m for moisture), so small dry patches may not show up,
                  and pixels at the edges can mix grass with dirt or pavement. The background photo is only
                  for drawing. The analysis uses Sentinel-2 data.
                </p>
              </Panel>
            </div>

            {/* ===== My Fields ===== */}
            <div role="tabpanel" id="tabpanel-myfields" aria-labelledby="tab-myfields" hidden={tab !== 'myfields'}>
              {!user ? (
                <EmptyState
                  icon="list"
                  title="Save fields to rank them"
                  action={(
                    <button type="button" onClick={() => setAccountOpen(true)}>
                      Log in or create an account
                    </button>
                  )}
                >
                  <p>
                    With a free account (username and password only), every analysis is saved, and
                    the AI can rank your fields so the one that most needs a visit comes first.
                  </p>
                </EmptyState>
              ) : (
                <>
                  <Panel id="v2-ranking" title="AI priority ranking" defaultOpen>
                    <MyFields user={user} onShow={handleShowSaved} />
                  </Panel>
                  <Panel id="v2-saved" title="Saved analyses" defaultOpen status={`${history.length}`}>
                    <SavedAnalyses
                      history={history}
                      historyError={historyError}
                      onShow={(item) => {
                        handleShowSaved(item);
                        openTab('analyze');
                      }}
                      onDelete={handleDelete}
                    />
                  </Panel>
                </>
              )}
            </div>

            {/* ===== AI Check: Weather Check + What if? ===== */}
            <div role="tabpanel" id="tabpanel-aicheck" aria-labelledby="tab-aicheck" hidden={tab !== 'aicheck'}>
              <Panel id="v2-weathercheck" title="AI Weather Check" defaultOpen>
                {result && polygon ? (
                  <AIWeatherCheck
                    key={JSON.stringify([polygon.geojson, excludeShapes, end])}
                    geometry={polygon.geojson}
                    exclude={excludeShapes}
                    defaultAsOf={end}
                  />
                ) : (
                  <EmptyState icon="chart" title="Analyze a field first">
                    <p>
                      After an analysis, the AI compares the newest clear image with what it expected
                      from recent weather.
                    </p>
                  </EmptyState>
                )}
              </Panel>
              <Panel id="v2-whatif" title="What if? — AI weather scenario" defaultOpen>
                <WhatIf
                  geometry={check?.ok && !editing ? polygon.geojson : null}
                  exclude={excludeShapes}
                  user={user}
                />
              </Panel>
            </div>

            {/* ===== Ask AI ===== */}
            <div role="tabpanel" id="tabpanel-ask" aria-labelledby="tab-ask" hidden={tab !== 'ask'}>
              <div className="card">
                <h2 className="card-title">Ask SpectralTurf</h2>
                <AskSpectralTurf
                  geometry={check?.ok && !editing ? polygon.geojson : null}
                  exclude={excludeShapes}
                  start={result ? start : null}
                  end={result ? end : null}
                  asOf={end && end < today ? end : today}
                  user={user}
                />
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
