/*
 * AboutPage.jsx - "/about": what SpectralTurf is, the science, the AI, and its limits
 * (added 2026-11-23, UI redesign). The facts here match the README and the code;
 * thresholds are labeled as this project's choices, not published standards.
 */
import { Link } from './router.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';

const SECTIONS = [
  ['what', 'What it is'],
  ['data', 'Satellite data'],
  ['indices', 'The three measurements'],
  ['rule', 'The inspection flag'],
  ['ai', 'The AI model'],
  ['assistant', 'The AI assistant'],
  ['limits', 'Limitations'],
  ['privacy', 'Privacy'],
  ['credits', 'Credits'],
];

export default function AboutPage() {
  return (
    <div className="site">
      <a href="#main" className="skip-link">Skip to content</a>
      <SiteNav />
      <main id="main" className="about">
        <header className="about-hero">
          <div className="container">
            <p className="eyebrow">About &amp; methodology</p>
            <h1>How SpectralTurf works, and what it can&apos;t do</h1>
            <p className="lead">
              A high-school project that turns free satellite images into a short list of turf areas
              worth inspecting. Every method and limit is written down here so anyone can check it.
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
            <section id="what">
              <h2>What it is</h2>
              <p>
                SpectralTurf helps the people who look after large areas of grass (parks, school
                fields, sports complexes) decide <strong>where to look first</strong>. You outline a
                field in Colorado; the app analyzes a real Sentinel-2 satellite image of it and marks
                the parts that may warrant inspection.
              </p>
              <p>
                It is <strong>decision support</strong>. It does not diagnose disease, prove drought,
                prescribe watering, or control irrigation. A person always checks the field in person.
              </p>
            </section>

            <section id="data">
              <h2>Satellite data</h2>
              <ul>
                <li>
                  <strong>Source:</strong> Copernicus Sentinel-2 Level-2A (surface reflectance), from
                  the Copernicus Data Space Ecosystem. The satellites revisit Colorado every few days.
                </li>
                <li>
                  <strong>Image choice:</strong> the least-cloudy image in your date range. The date of
                  that image is always shown.
                </li>
                <li>
                  <strong>Clouds and shadows:</strong> each pixel is checked with Sentinel-2&apos;s own
                  scene classification. Cloud, cloud shadow, cirrus, dark/shadow, saturated, snow and
                  no-data pixels are removed. The tile&apos;s overall cloud percentage is not enough on
                  its own, so this per-pixel check is always done.
                </li>
                <li>
                  <strong>Resolution:</strong> 10 m pixels for greenness and color; 20 m for moisture.
                  Pixels are never smoothed, so the map never shows detail that isn&apos;t there.
                </li>
                <li>
                  <strong>Not enough data:</strong> with fewer than 20 clear pixels (a project choice)
                  the app says &ldquo;Insufficient evidence&rdquo; and shows no averages.
                </li>
              </ul>
            </section>

            <section id="indices">
              <h2>The three measurements</h2>
              <dl className="formula-list">
                <div>
                  <dt>NDVI: greenness</dt>
                  <dd><code>(NIR − Red) / (NIR + Red)</code>, bands B08 and B04, 10 m. Dense green grass scores high (above about 0.6); bare soil and pavement are near 0 to 0.2.</dd>
                </div>
                <div>
                  <dt>NDMI: leaf moisture</dt>
                  <dd><code>(NIR − SWIR) / (NIR + SWIR)</code>, bands B8A and B11, <strong>20 m</strong>. Water in leaves absorbs shortwave infrared, so higher means more leaf water.</dd>
                </div>
                <div>
                  <dt>NGRDI: visible green vs. yellow</dt>
                  <dd><code>(Green − Red) / (Green + Red)</code>, bands B03 and B04, 10 m (Tucker, 1979). Below 0, grass reflects more red than green and looks yellow or brown.</dd>
                </div>
              </dl>
            </section>

            <section id="rule">
              <h2>The inspection flag</h2>
              <p>Inside your outline (skipping the edge pixels, which mix in pavement or dirt), each clear pixel gets three checks:</p>
              <ol>
                <li><strong>Color:</strong> NGRDI below 0.15 means yellow or pale instead of deep green.</li>
                <li><strong>Healthy-turf baseline:</strong> NDVI below 0.5 or NDMI below 0.0.</li>
                <li><strong>Within the field:</strong> NDVI more than 0.20 below the field&apos;s own median.</li>
              </ol>
              <p>
                An area is flagged when at least 5% of the checked pixels (and at least 5 pixels) fail a
                check. If 50% or more fail, the whole field is flagged.
              </p>
              <p className="callout">
                These cutoffs are <strong>this project&apos;s choices</strong>, based on real
                measurements of watered Colorado sports turf in summer 2026. They are not published
                standards.
              </p>
            </section>

            <section id="ai">
              <h2>The AI model</h2>
              <p>
                A gradient-boosting model (scikit-learn HistGradientBoostingRegressor) learned how the
                NDVI of 22 Denver-area fields changed 7–20 days after a clear image. It used 38,342
                real image pairs from 2019–2025 plus daily rain, temperature and evapotranspiration
                from Open-Meteo.
              </p>
              <ul>
                <li><strong>Expected vs. observed:</strong> if the newest image is much lower than the model expected (more than twice its typical error), the app says the weather alone doesn&apos;t explain it.</li>
                <li><strong>Cloudy days:</strong> when no clear image exists for 7+ days, it can show an estimate. This is clearly labeled as an estimate, not a measurement.</li>
                <li><strong>What-if:</strong> only weather values inside what the model saw in training are allowed.</li>
              </ul>
              <h3>How well it works</h3>
              <p>
                It was tested on a year it never saw (2025) and on fields it never saw. Its average
                error was 0.058 NDVI in 2025 (16% lower than &ldquo;same as last time&rdquo;) and 0.060 on
                unseen fields (14% lower). On unseen fields it was <strong>not</strong> clearly better
                than averaging the last few images. The numbers are slightly optimistic, because
                version 3 was designed after earlier test results were seen. Weather inputs matter
                little, probably because most fields are watered. Full results are in{' '}
                <code>ml/results_v3.md</code>.
              </p>
            </section>

            <section id="assistant">
              <h2>The AI assistant (Ask SpectralTurf)</h2>
              <p>
                Google Gemini writes the answers, but it can only use read-only tools that return your
                field&apos;s real results. The server checks every answer: each number must come from
                those results, and answers with watering amounts, cause claims, or disease guesses are
                blocked. Photos are only described, never diagnosed.
              </p>
            </section>

            <section id="limits">
              <h2>Limitations</h2>
              <ul>
                <li>Patches smaller than a 10 m (or 20 m) pixel can be missed.</li>
                <li>Edge pixels can mix turf with dirt, pavement or trees.</li>
                <li>One image is a snapshot of one day; thin haze can slip past cloud masking.</li>
                <li>Dormant grass in spring or autumn and other grass types can fall below the summer baseline naturally.</li>
                <li>Artificial turf looks green to the eye but has low NDVI.</li>
                <li>Low values say <em>where</em> to look, never <em>why</em>: wear, mowing, dormancy, disease or watering problems can all look alike from space.</li>
              </ul>
            </section>

            <section id="privacy">
              <h2>Privacy</h2>
              <p>
                Accounts are optional and need only a username and password (no email). Passwords are
                stored as scrypt hashes. Saved fields are visible only to their owner. Questions,
                field numbers and photos sent to the assistant go to Google Gemini. Usernames, field
                names and map locations are not sent, and photo location data is removed first.
              </p>
            </section>

            <section id="credits">
              <h2>Credits</h2>
              <ul>
                <li>Contains modified Copernicus Sentinel data, processed via the Copernicus Data Space Ecosystem.</li>
                <li>Weather data by Open-Meteo.com.</li>
                <li>Field outlines and place search © OpenStreetMap contributors (Overpass, Nominatim).</li>
                <li>Drawing basemap: Esri World Imagery (for drawing only; not used in the analysis).</li>
              </ul>
              <p><Link to="/app" className="btn btn-primary">Open the app</Link></p>
            </section>
          </article>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
