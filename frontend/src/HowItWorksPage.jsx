/*
 * HowItWorksPage.jsx - "/how-it-works" (added 2026-11-27, student request).
 *
 * The 4 steps used to be a section on the homepage, and the methodology (satellite data, the
 * inspection flag, the AI) used to be on the About page. Both now live here, so the homepage and
 * About page don't repeat them. Thresholds are labeled as this project's choices.
 */
import { Link } from './router.jsx';
import { Icon } from './Icons.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';

const STEPS = [
  { icon: 'draw', title: 'Draw your field', text: 'Search a park or school in Colorado and outline the turf on the map. A field can be several shapes (for fields with walkways between them), and you can cut out dirt infields and tracks.' },
  { icon: 'satellite', title: 'Satellite + AI analysis', text: 'SpectralTurf AI downloads the least-cloudy Sentinel-2 image, removes clouds and shadows, and compares greenness and leaf moisture with what the AI expected from recent weather.' },
  { icon: 'target', title: 'Inspect the right spots first', text: 'The map highlights the areas that may warrant a closer look, so your grounds crew walks to those spots first and sees for themselves.' },
  { icon: 'camera', title: 'Check a photo on the spot', text: 'Take a photo of the patch. The photo AI says which of 6 categories it looks most like: a preliminary result for a turf expert to confirm.' },
];

const SECTIONS = [
  ['data', 'Satellite data'],
  ['rule', 'The inspection flag'],
  ['weather-ai', 'The weather AI'],
  ['photo-ai', 'The photo AI'],
  ['assistant', 'The AI assistant'],
];

export default function HowItWorksPage() {
  return (
    <div className="site">
      <a href="#main" className="skip-link">Skip to content</a>
      <SiteNav />
      <main id="main" className="about">
        <header className="about-hero">
          <div className="container">
            <p className="eyebrow">How it works</p>
            <h1>From a drawn outline to a photo check at the right spot</h1>
            <p className="lead">
              Four steps in the app, and what happens behind each one.
            </p>
          </div>
        </header>

        <section className="section section-steps" aria-label="The four steps">
          <div className="container">
            <ol className="steps-grid steps-4">
              {STEPS.map((step, i) => (
                <li className="step-card" key={step.title}>
                  <span className="step-icon"><Icon name={step.icon} size={28} /></span>
                  <span className="step-number">Step {i + 1}</span>
                  <h3>{step.title}</h3>
                  <p>{step.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <div className="container about-grid">
          <nav className="about-toc" aria-label="On this page">
            <p className="toc-title">Behind the steps</p>
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
                  <dd><code>(Green − Red) / (Green + Red)</code>, bands B03 and B04, 10 m.</dd>
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

            <section id="weather-ai">
              <h2>The weather AI</h2>
              <p>
                A gradient-boosting model (scikit-learn) learned how the NDVI of 22 Denver-area fields
                changed 7–20 days after a clear image, from 38,342 real image pairs (2019–2025) and
                Open-Meteo weather. It flags an image much lower than expected (more than twice its
                typical error), estimates cloudy days (labeled as an estimate), and only allows What-if
                weather inside what it saw in training.
              </p>
            </section>

            <section id="photo-ai">
              <h2>The photo AI</h2>
              <p>
                OpenAI&apos;s CLIP image model turns a photo into 512 numbers, and our own
                logistic-regression classifier turns those into 6 category percentages. Below 75% (a
                project choice) it says &ldquo;Uncertain — inspect in person&rdquo;. It runs on our
                server, shrunk to 8-bit weights (same final answer as the full model for 98.9% of the
                test photos). Results are preliminary: a turf expert should confirm.
              </p>
            </section>

            <section id="assistant">
              <h2>The AI assistant</h2>
              <p>
                Google Gemini writes the answers, but only from read-only tools that return your
                field&apos;s real results. The server checks every answer: numbers must come from the
                tools, and watering amounts, cause claims and specific disease or pest names are blocked.
              </p>
              <p>
                Test results for both AI models are on the <Link to="/#trust">homepage</Link>; where every
                number and method comes from is on the <Link to="/sources">Sources</Link> page.
              </p>
              <p><Link to="/login" className="btn btn-primary">Get started</Link></p>
            </section>
          </article>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
