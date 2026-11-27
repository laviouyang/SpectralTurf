/*
 * AboutPage.jsx - "/about": how SpectralTurf works and what it can't do (added 2026-11-23).
 *
 * 2026-11-27 (student request): made SHORT. Things already on the homepage (who it's for, the
 * steps, the feature list, the test results, the grass lists per region) and in the footer (data
 * credits) are not repeated here. Thresholds are labeled as this project's choices.
 */
import { Link } from './router.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';
import { DATA as REGION_DATA } from './turfRegions.js';

const SECTIONS = [
  ['data', 'Satellite data'],
  ['rule', 'The inspection flag'],
  ['ai', 'The AI'],
  ['regions', 'Grass regions'],
  ['limits', 'Limitations'],
  ['privacy', 'Privacy'],
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
              A high-school project. It is decision support: it shows where to look, and a person
              always checks the field before acting.
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
              <h2>Satellite data</h2>
              <ul>
                <li>Copernicus Sentinel-2 Level-2A images; the least-cloudy image in your dates is used, and its date is always shown.</li>
                <li>Every pixel is checked for cloud, shadow, snow and no data with Sentinel-2&apos;s own scene classification, and bad pixels are removed.</li>
                <li>10 m pixels for greenness and color, 20 m for moisture. Pixels are never smoothed.</li>
                <li>Fewer than 20 clear pixels (a project choice) means &ldquo;Insufficient evidence&rdquo; and no averages.</li>
              </ul>
              <dl className="formula-list">
                <div>
                  <dt>NDVI: greenness</dt>
                  <dd><code>(NIR − Red) / (NIR + Red)</code>, bands B08 and B04, 10 m.</dd>
                </div>
                <div>
                  <dt>NDMI: leaf moisture</dt>
                  <dd><code>(NIR − SWIR) / (NIR + SWIR)</code>, bands B8A and B11, <strong>20 m</strong>.</dd>
                </div>
                <div>
                  <dt>NGRDI: green vs. yellow</dt>
                  <dd><code>(Green − Red) / (Green + Red)</code>, bands B03 and B04, 10 m (Tucker, 1979).</dd>
                </div>
              </dl>
            </section>

            <section id="rule">
              <h2>The inspection flag</h2>
              <p>Skipping the edge pixels, each clear pixel inside your outline gets three checks:</p>
              <ol>
                <li><strong>Color:</strong> NGRDI below 0.15 (yellow or pale).</li>
                <li><strong>Healthy-turf baseline:</strong> NDVI below 0.5 or NDMI below 0.0.</li>
                <li><strong>Within the field:</strong> NDVI more than 0.20 below the field&apos;s own median.</li>
              </ol>
              <p>
                An area is flagged when at least 5% of pixels (and at least 5 pixels) fail a check; 50% or
                more flags the whole field.
              </p>
              <p className="callout">
                These cutoffs are <strong>this project&apos;s choices</strong>, based on real Colorado
                sports turf in summer 2026, not published standards.
              </p>
            </section>

            <section id="ai">
              <h2>The AI</h2>
              <ul>
                <li>
                  <strong>Weather model:</strong> a gradient-boosting model (scikit-learn) learned how
                  the NDVI of 22 Denver-area fields changed 7–20 days after a clear image, from 38,342
                  real image pairs (2019–2025) and Open-Meteo weather. It flags an image much lower than
                  expected (more than twice its typical error), estimates cloudy days (labeled as an
                  estimate), and only allows What-if weather inside what it saw in training.
                </li>
                <li>
                  <strong>Photo AI:</strong> OpenAI&apos;s CLIP image model turns a photo into 512
                  numbers, and our own logistic-regression classifier turns those into 6 category
                  percentages. Below 75% (a project choice) it says &ldquo;Uncertain — inspect in
                  person&rdquo;. It runs on our server, shrunk to 8-bit weights (same final answer as
                  the full model for 98.9% of the test photos). Results are preliminary: a turf expert
                  should confirm.
                </li>
                <li>
                  <strong>Ask SpectralTurf:</strong> Google Gemini writes the answers, but only from
                  read-only tools that return your field&apos;s real results. The server checks every
                  answer: numbers must come from the tools, and watering amounts, cause claims and
                  specific disease or pest names are blocked.
                </li>
              </ul>
              <p>Test results for both AI models are on the <Link to="/#trust">homepage</Link>.</p>
            </section>

            <section id="regions">
              <h2>Grass regions</h2>
              <p>
                The region is only a label; the satellite math is the same everywhere. Only Region 3
                (Northern &amp; Central Plains) is validated, because the baseline, color cutoff and AI
                were made from Denver-area fields. The map is our own approximation (layout after the
                &ldquo;Grass Types USA&rdquo; map by Simple Lawn Solutions, on U.S. Census state shapes),
                checked against the zone maps of the{' '}
                <a href={REGION_DATA.sources.framework[0].url} target="_blank" rel="noreferrer">University of Maryland</a>
                {' '}and{' '}
                <a href={REGION_DATA.sources.framework[1].url} target="_blank" rel="noreferrer">Kansas State</a>
                {' '}extensions. It is not an official USDA map.
              </p>
            </section>

            <section id="limits">
              <h2>Limitations</h2>
              <ul>
                <li>Patches smaller than a 10 m (or 20 m) pixel can be missed, and edge pixels mix in dirt or pavement.</li>
                <li>One image is one day; thin haze can slip past cloud masking.</li>
                <li>Dormant grass, other grass types and artificial turf can look low without a problem.</li>
                <li>Low values say <em>where</em> to look, never <em>why</em>.</li>
                <li>The photo AI learned mostly from public datasets and articles, not real sports fields, so real-world accuracy may be lower.</li>
              </ul>
            </section>

            <section id="privacy">
              <h2>Privacy</h2>
              <p>
                Accounts need only a username and password (stored as scrypt hashes); saved fields are
                visible only to their owner. Gemini gets questions and field numbers, never usernames,
                field names, locations or photos. Photos are checked on our server, never stored, and
                their hidden GPS data is removed first.
              </p>
              <p><Link to="/app" className="btn btn-primary">Get started</Link></p>
            </section>
          </article>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
