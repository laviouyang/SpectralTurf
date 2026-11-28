/*
 * SourcesPage.jsx - "/sources" (added 2026-11-27, student request): every data source, science
 * reference, model and library the app relies on, in one place. The homepage's "Built on open
 * data" strip moved here. The short data credits stay in the footer (they must be on every page).
 */
import { SiteFooter, SiteNav, GITHUB_URL } from './SiteChrome.jsx';
import { DATA as REGION_DATA } from './turfRegions.js';

const repo = (path) => `${GITHUB_URL}/blob/main/${path}`;

const SECTIONS = [
  ['data', 'Data'],
  ['science', 'Science'],
  ['regions', 'Grass regions'],
  ['ai', 'AI models'],
  ['results', 'Our test results'],
  ['software', 'Software'],
];

function Ext({ href, children }) {
  return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
}

// The extension pages used for the grass lists of each region (turfRegions.json "sources").
const REGION_SOURCES = ['CSU', 'OSU', 'USU', 'UMN', 'UA', 'NCSU', 'UF']
  .map((key) => REGION_DATA.sources[key])
  .filter(Boolean);

export default function SourcesPage() {
  return (
    <div className="site">
      <a href="#main" className="skip-link">Skip to content</a>
      <SiteNav />
      <main id="main" className="about">
        <header className="about-hero">
          <div className="container">
            <p className="eyebrow">Sources</p>
            <h1>Where the data, methods and numbers come from</h1>
            <p className="lead">
              Everything SpectralTurf AI shows comes from these sources. Cutoffs that are not from a
              source are marked as this project&apos;s own choices.
            </p>
          </div>
        </header>

        <div className="container about-grid">
          <nav className="about-toc" aria-label="On this page">
            <p className="toc-title">On this page</p>
            <ol>
              {SECTIONS.map(([id, label]) => (
                <li key={id}><a href={`#${id}`}>{label}</a></li>
              ))}
            </ol>
          </nav>

          <article className="prose">
            <section id="data">
              <h2>Data</h2>
              <ul>
                <li>
                  <strong>Satellite images:</strong> Copernicus Sentinel-2 Level-2A, from the{' '}
                  <Ext href="https://dataspace.copernicus.eu/">Copernicus Data Space Ecosystem</Ext>{' '}
                  (contains modified Copernicus Sentinel-2 data). Cloud and shadow masking uses
                  Sentinel-2&apos;s own scene classification (SCL) layer.
                </li>
                <li>
                  <strong>Weather:</strong> daily rain, high temperature and evapotranspiration by{' '}
                  <Ext href="https://open-meteo.com/">Open-Meteo.com</Ext> (historical archive and forecast).
                </li>
                <li>
                  <strong>Field outlines for training and place search:</strong> ©{' '}
                  <Ext href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</Ext>, searched with{' '}
                  <Ext href="https://nominatim.openstreetmap.org/">Nominatim</Ext>.
                </li>
                <li>
                  <strong>Background maps (for drawing only, never analyzed):</strong>{' '}
                  <Ext href="https://www.esri.com/">Esri World Imagery</Ext> and{' '}
                  <Ext href="https://www.openstreetmap.org/copyright">OpenStreetMap</Ext>.
                </li>
              </ul>
            </section>

            <section id="science">
              <h2>Science</h2>
              <ul>
                <li><strong>NDVI</strong> (greenness): Rouse, J. W. et al. (1974), &ldquo;Monitoring vegetation systems in the Great Plains with ERTS.&rdquo;</li>
                <li><strong>NDMI</strong> (leaf moisture, near-infrared vs. short-wave infrared): Gao, B.-C. (1996), &ldquo;NDWI — A normalized difference water index for remote sensing of vegetation liquid water from space,&rdquo; <em>Remote Sensing of Environment</em> 58.</li>
                <li><strong>NGRDI</strong> (green vs. yellow): Tucker, C. J. (1979), &ldquo;Red and photographic infrared linear combinations for monitoring vegetation,&rdquo; <em>Remote Sensing of Environment</em> 8.</li>
                <li>
                  &ldquo;What to check when you visit&rdquo; points to{' '}
                  <Ext href="https://extension.colostate.edu/">Colorado State University Extension</Ext>.
                </li>
                <li className="callout">
                  The inspection cutoffs (NGRDI 0.15, NDVI 0.5, NDMI 0.0, 0.20 below the median, 5% / 50%,
                  20 clear pixels) and the photo AI&apos;s 75% &ldquo;Uncertain&rdquo; line are{' '}
                  <strong>this project&apos;s choices</strong>, made from real data, not published standards.
                </li>
              </ul>
            </section>

            <section id="regions">
              <h2>Grass regions</h2>
              <p>
                The 7-region split is our own approximation. Zone framework:{' '}
                {REGION_DATA.sources.framework.map((s, i) => (
                  <span key={s.url}>{i > 0 && '; '}<Ext href={s.url}>{s.name}</Ext></span>
                ))}.
              </p>
              <p>Grass lists checked against:</p>
              <ul>
                {REGION_SOURCES.map((s) => (
                  <li key={s.url}><Ext href={s.url}>{s.name}</Ext></li>
                ))}
              </ul>
              <p>
                {REGION_DATA.sources.layout.name}. {REGION_DATA.sources.states.name} (
                <Ext href={REGION_DATA.sources.states.url}>us-atlas</Ext>).
              </p>
            </section>

            <section id="ai">
              <h2>AI models</h2>
              <ul>
                <li>
                  <strong>Weather AI:</strong> our own gradient-boosting model, trained with{' '}
                  <Ext href="https://scikit-learn.org/">scikit-learn</Ext> on Sentinel-2 NDVI of 22
                  Denver-area fields (outlines from OpenStreetMap) and Open-Meteo weather, 2019–2025.
                </li>
                <li>
                  <strong>Photo AI:</strong> image features from{' '}
                  <Ext href="https://github.com/openai/CLIP">CLIP ViT-B/32 by OpenAI</Ext> (MIT license),
                  run with <Ext href="https://onnxruntime.ai/">ONNX Runtime</Ext>; our own classifier on
                  top, trained on photos from public turf datasets and published extension and research
                  articles.
                </li>
                <li>
                  <strong>AI assistant:</strong> answers written by{' '}
                  <Ext href="https://ai.google.dev/">Google Gemini</Ext>, only from the app&apos;s own tool results.
                </li>
              </ul>
            </section>

            <section id="results">
              <h2>Our test results</h2>
              <p>The numbers on the homepage come straight from these result files in the source code:</p>
              <ul>
                <li><Ext href={repo('ml/results_v3.md')}>Weather AI test results (ml/results_v3.md)</Ext></li>
                <li><Ext href={repo('ml_photo/results_onnx.md')}>Photo AI test results (ml_photo/results_onnx.md)</Ext></li>
              </ul>
            </section>

            <section id="software">
              <h2>Software</h2>
              <p>
                Built with <Ext href="https://fastapi.tiangolo.com/">FastAPI</Ext>,{' '}
                <Ext href="https://numpy.org/">NumPy</Ext>, <Ext href="https://react.dev/">React</Ext>,{' '}
                <Ext href="https://leafletjs.com/">Leaflet</Ext> with Leaflet.draw, and{' '}
                <Ext href="https://github.com/mfogel/polygon-clipping">polygon-clipping</Ext>. All of
                SpectralTurf AI&apos;s own code is on <Ext href={GITHUB_URL}>GitHub</Ext>.
              </p>
            </section>
          </article>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
