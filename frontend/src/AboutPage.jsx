/*
 * AboutPage.jsx - "/about": what SpectralTurf is, the science, the AI, and its limits
 * (added 2026-11-23, UI redesign). The facts here match the README and the code;
 * thresholds are labeled as this project's choices, not published standards.
 * 2026-11-26: photo AI section added (numbers from backend/photo_model/photo_classifier_v1.json),
 * assistant/privacy updated (photos no longer go to Gemini), target audience named.
 */
import { Link } from './router.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';
import { DATA as REGION_DATA, REGIONS } from './turfRegions.js';

const SECTIONS = [
  ['what', 'What it is'],
  ['data', 'Satellite data'],
  ['indices', 'The three measurements'],
  ['rule', 'The inspection flag'],
  ['ai', 'The AI model'],
  ['photo', 'The photo AI'],
  ['assistant', 'The AI assistant'],
  ['regions', 'Grass regions'],
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
              worth inspecting, plus a photo AI for a closer look on site. Every method and limit is
              written down here so anyone can check it.
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
                SpectralTurf is built for <strong>sports-field managers, park and school grounds
                crews, and city parks departments</strong>: the teams who look after large areas of
                grass. It helps them decide <strong>where to look first</strong>. You outline a field
                in Colorado; the app analyzes a real Sentinel-2 satellite image of it and marks the
                parts that may warrant inspection. On site, the photo AI (in the AI Diagnosis tab)
                says which of 6 categories a photo of the turf looks most like.
              </p>
              <p>
                It is <strong>decision support</strong>. Photo results are a <strong>preliminary AI
                result</strong> that a turf expert should confirm before anything is treated. It does
                not prove drought, prescribe watering, or control irrigation. A person always checks
                the field in person.
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

            <section id="photo">
              <h2>The photo AI</h2>
              <p>
                In the <strong>AI Diagnosis</strong> tab you can upload or take one photo of turf. The
                app says which of 6 categories it <strong>looks most like</strong>, with a percentage
                for each: healthy-looking grass, drought stress, fungal disease, insect damage, wear
                (foot traffic) and dormant grass. If the top category is below 75% (a project choice
                made on the training photos), it says &ldquo;Uncertain — inspect in person&rdquo;
                instead. From November to March it adds that brown grass may be normal winter
                dormancy. Every result says: &ldquo;Preliminary AI result — it can be wrong. Confirm
                with a turf expert before treating.&rdquo;
              </p>
              <ul>
                <li>
                  <strong>How it works:</strong> OpenAI&apos;s CLIP image model (ViT-B/32) turns the
                  photo into 512 numbers, and a logistic-regression classifier trained by this project
                  turns those into the 6 percentages. It runs on our own server; the photo is not
                  sent to Google Gemini.
                </li>
                <li>
                  <strong>Shrunk for a small server:</strong> the image model was converted to ONNX
                  with 8-bit weights (352 MB to 98 MB). On the 379 test photos it gave the same final
                  answer as the original model for 98.9% of them.
                </li>
                <li>
                  <strong>Test results:</strong> on 379 photos it never saw during training (kept
                  apart by site or source) it picked the right category for 90.0%. Averaged over the 6
                  categories, so the small ones count equally, it was right for 69.3%. It said
                  &ldquo;Uncertain&rdquo; for 27.4%; when it did answer, it was right 96.7% of the time.
                </li>
              </ul>
              <p className="callout">
                <strong>Honest limits:</strong> most training photos came from public datasets and
                published articles, not real sports fields, and each category came mostly from one
                source, so the AI may partly recognize the source rather than the problem. Real-world
                accuracy may be lower. Wear and dormant grass had only 2 test photos each (it got 0 of
                the 2 wear photos right). The labels come from captions and folder names and were not
                checked by a turf expert. It never names a specific disease or pest.
              </p>
            </section>

            <section id="assistant">
              <h2>The AI assistant (Ask SpectralTurf)</h2>
              <p>
                Google Gemini writes the answers, but it can only use read-only tools that return your
                field&apos;s real results. The server checks every answer: each number must come from
                those results, and answers with watering amounts, cause claims, or specific disease or
                pest names are blocked. If you attach a photo, our own photo AI checks it on the
                server and Gemini only receives the result (the percentages), never the photo. Any
                answer about the photo must say it is a preliminary AI result to confirm with a turf
                expert.
              </p>
            </section>

            <section id="regions">
              <h2>Grass regions</h2>
              <p>
                The homepage map splits the 48 states into 7 grass regions. When you draw a field, the
                app detects its region from the field&apos;s location and shows it (you can change it).
                The region is only a label: the satellite measurements are calculated the same way
                everywhere.
              </p>
              <p>
                <strong>Only Region 3 (Northern &amp; Central Plains) is validated</strong>, and only with
                Denver-area fields: the healthy-turf baseline (NDVI 0.5, NDMI 0), the color cutoff
                (NGRDI 0.15) and the AI model were made from them. In every other region the app says
                &ldquo;not validated for this region yet&rdquo;. The within-field check (comparing a field
                with itself) still works anywhere.
              </p>
              <ul>
                {REGIONS.map((r) => (
                  <li key={r.id}>
                    <strong>Region {r.id}: {r.name}</strong> ({r.climate}): {r.grasses.join(', ')}.{' '}
                    <a href={REGION_DATA.sources[r.source].url} target="_blank" rel="noreferrer">Source</a>
                  </li>
                ))}
              </ul>
              <p>
                <strong>How the map was made:</strong> a simplified map drawn for this project, not an
                official USDA map, and the boundaries are approximate. The region layout follows the
                &ldquo;Grass Types USA&rdquo; map by Simple Lawn Solutions (a lawn-care company, so a
                visual reference rather than a scientific source), redrawn by hand on U.S. Census state
                shapes (via us-atlas). The split into cool-season, transition and warm-season areas
                matches the zone maps of the{' '}
                <a href={REGION_DATA.sources.framework[0].url} target="_blank" rel="noreferrer">University of Maryland Extension</a>
                {' '}and{' '}
                <a href={REGION_DATA.sources.framework[1].url} target="_blank" rel="noreferrer">Kansas State University</a>
                . Each region&apos;s grass list comes from a university extension in that region.
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
                <li>The baseline, color cutoff and AI model are validated only for Denver-area fields (Region 3); grass-region boundaries are approximate.</li>
                <li>Low values say <em>where</em> to look, never <em>why</em>: wear, mowing, dormancy, disease or watering problems can all look alike from space.</li>
                <li>The photo AI was trained mostly on photos from public datasets and articles, not real sports fields; many problems look alike in a photo, so its result is preliminary and a turf expert should confirm it.</li>
              </ul>
            </section>

            <section id="privacy">
              <h2>Privacy</h2>
              <p>
                Accounts are optional and need only a username and password (no email). Passwords are
                stored as scrypt hashes. Saved fields are visible only to their owner. Questions and
                field numbers sent to the assistant go to Google Gemini. Usernames, field names and
                map locations are not sent. Photos are checked on our own server and never sent to
                Gemini or stored; hidden photo data (GPS location, camera, time) is removed first.
              </p>
            </section>

            <section id="credits">
              <h2>Credits</h2>
              <ul>
                <li>Contains modified Copernicus Sentinel data, processed via the Copernicus Data Space Ecosystem.</li>
                <li>Weather data by Open-Meteo.com.</li>
                <li>Field outlines and place search © OpenStreetMap contributors (Overpass, Nominatim).</li>
                <li>Drawing basemap: Esri World Imagery (for drawing only; not used in the analysis).</li>
                <li>Photo AI image features: CLIP ViT-B/32 by OpenAI (MIT license).</li>
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
