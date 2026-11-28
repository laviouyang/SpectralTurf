/*
 * HomePage.jsx - The landing page at "/" (added 2026-11-23, UI redesign).
 *
 * Every number on this page is real and has a source:
 *   - the hero picture is a real Sentinel-2 analysis made by this app (see previewFacts.json,
 *     made with backend run_analysis for Village Greens Park, image 2026-08-05);
 *   - the model results come from ml/results_v3.md (evaluate_v3.py, 2026-11-07);
 *   - the photo AI results come from backend/photo_model/photo_classifier_v1.json
 *     (ml_photo/export_onnx.py, 379 test photos, 2026-11-26).
 * 2026-11-26 (student request): photo AI added, and the target audience named instead of "people".
 * 2026-11-27 (student request): app buttons say "Get started"; the water-statistics section removed.
 * 2026-11-27 later (student request): the 4 steps moved to the How it works page and the
 *   "Built on open data" strip to the Sources page; the nav's "Features" link scrolls to #features.
 * No testimonials, user counts, or partner logos, because we don't have any.
 */
import { useEffect, useState } from 'react';
import { Link } from './router.jsx';
import { Icon } from './Icons.jsx';
import { SiteFooter, SiteNav } from './SiteChrome.jsx';
import facts from './previewFacts.json';
import RegionMap from './RegionMap.jsx';

// A real NDVI picture from the app, with the same color scale the app uses.
function LivePreview() {
  const [view, setView] = useState('ndvi');
  const scale = facts.ndvi_scale;
  const gradient = scale.map(([v, c]) => `${c} ${(v / scale[scale.length - 1][0]) * 100}%`).join(', ');
  return (
    <figure className="preview-card">
      <div className="preview-toolbar">
        <span className="preview-dot" aria-hidden="true" />
        <span className="preview-title">Real Sentinel-2 analysis</span>
        <div className="segmented" role="group" aria-label="Picture shown">
          <button type="button" aria-pressed={view === 'ndvi'} onClick={() => setView('ndvi')}>NDVI</button>
          <button type="button" aria-pressed={view === 'true_color'} onClick={() => setView('true_color')}>
            True color
          </button>
        </div>
      </div>
      <div className="preview-image">
        <img
          className="pixel-image"
          src={`/preview/${view}.png`}
          alt={view === 'ndvi'
            ? 'NDVI map: irrigated ball fields in green with round brown dirt infields; dry, tan land to the right'
            : 'Natural-color Sentinel-2 image of the same area'}
          width="60"
          height="61"
        />
      </div>
      {view === 'ndvi' && (
        <div className="preview-legend">
          <div className="legend-bar" style={{ background: `linear-gradient(to right, ${gradient})` }} />
          <div className="legend-ends"><span>bare / not green</span><span>dense green</span></div>
        </div>
      )}
      <figcaption>
        {facts.place} · image {facts.date} · {Math.round(facts.clear_fraction * 100)}% clear pixels · each
        square is one 10 m pixel. The round brown spots on the left are dirt baseball infields.
      </figcaption>
    </figure>
  );
}

// Who SpectralTurf is built for (2026-11-26). "Built for" only: no claim that they use it yet.
const AUDIENCE = [
  { icon: 'target', title: 'Sports-field managers', text: 'Schools, recreation centers and sports complexes that keep natural-grass fields playable.' },
  { icon: 'people', title: 'Park and school grounds crews', text: 'Teams who look after many acres of grass and need to know which spots to walk to first.' },
  { icon: 'list', title: 'City parks departments', text: 'Many fields across a city: the My Fields ranking shows which one to visit first.' },
];

const FEATURES = [
  { icon: 'camera', title: 'Photo AI check', text: 'Upload or take a photo of the turf. It shows which of 6 categories it looks most like, with a percentage for each, or says “Uncertain”.' },
  { icon: 'chart', title: 'AI Expected-vs-Observed Check', text: 'Compares the newest clear image with what the model expected from the weather.' },
  { icon: 'list', title: 'My Fields priority ranking', text: 'Ranks your saved fields so the one that most needs a visit comes first.' },
  { icon: 'sliders', title: 'What-if explorer', text: 'Shows how greenness might change after a dry or hot spell, within what the AI has seen.' },
  { icon: 'chat', title: 'Ask SpectralTurf AI assistant', text: 'Plain-language answers built only from your field’s real data and photo check, with dates.' },
  { icon: 'shield', title: 'Honest data quality', text: 'Clouds, coarse pixels and thin evidence are shown, never hidden or filled in.' },
];

const PRINCIPLES = [
  { icon: 'ruler', title: 'Shows its uncertainty', text: 'Every AI estimate comes with its typical error and the date of the image it is based on.' },
  { icon: 'eye', title: 'Never guesses', text: 'With too few clear pixels it says “Insufficient evidence” instead of making up a number.' },
  { icon: 'people', title: 'Turf experts decide', text: 'It points to where to look. Photo results are preliminary, for a turf expert to confirm, and it never tells anyone how much to water.' },
];

export default function HomePage() {
  // Opening "/#features" from another page or a typed address: scroll to that section once drawn.
  useEffect(() => {
    if (window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView();
  }, []);
  return (
    <div className="site">
      <a href="#main" className="skip-link">Skip to content</a>
      <SiteNav />
      <main id="main">
        {/* ---- Hero ---- */}
        <section className="hero">
          <div className="container hero-grid">
            <div className="hero-copy">
              <p className="eyebrow">For sports-field managers and grounds crews · Satellite + photo AI</p>
              <h1>Find the fields that need attention — before the damage spreads.</h1>
              <p className="lead">
                SpectralTurf AI reads free Sentinel-2 satellite images and recent weather to show which
                parts of a park or sports field may warrant a closer look, so sports-field managers and
                park and school grounds crews can walk to the right spots first, then check a photo of
                any problem patch with the photo AI.
              </p>
              <div className="hero-actions">
                <Link to="/login" className="btn btn-primary btn-lg">
                  Get started <Icon name="arrowRight" size={18} />
                </Link>
                <Link to="/how-it-works" className="btn btn-secondary btn-lg">See how it works</Link>
              </div>
              <p className="hero-note">Free to try · Validated in Colorado (Denver area) · No account needed to analyze</p>
            </div>
            <LivePreview />
          </div>
        </section>

        {/* ---- Who it's for (added 2026-11-26) ---- */}
        <section id="audience" className="section section-tint" aria-labelledby="audience-title">
          <div className="container">
            <p className="eyebrow">Who it&apos;s for</p>
            <h2 id="audience-title" className="section-title">Built for the teams who look after large turf</h2>
            <div className="feature-grid">
              {AUDIENCE.map((a) => (
                <div className="feature-card" key={a.title}>
                  <span className="feature-icon"><Icon name={a.icon} size={24} /></span>
                  <h3>{a.title}</h3>
                  <p>{a.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---- US grass regions (added 2026-11-25; replaces the state picker) ---- */}
        <section id="regions" className="section" aria-labelledby="regions-title">
          <div className="container">
            <p className="eyebrow">Where it works</p>
            <h2 id="regions-title" className="section-title">US grass regions</h2>
            <p className="lead-sm">
              Different parts of the country grow different turfgrasses. Click a region to see its
              common grasses and whether SpectralTurf AI is validated there yet.
            </p>
            <RegionMap />
          </div>
        </section>

        {/* ---- Features ---- */}
        <section id="features" className="section section-tint" aria-labelledby="features-title">
          <div className="container">
            <p className="eyebrow">AI features</p>
            <h2 id="features-title" className="section-title">AI that explains what it sees, and says what it doesn&apos;t know</h2>
            <div className="feature-grid">
              {FEATURES.map((f) => (
                <div className="feature-card" key={f.title}>
                  <span className="feature-icon"><Icon name={f.icon} size={24} /></span>
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ---- Trust: real test results from ml/results_v3.md ---- */}
        <section id="trust" className="section" aria-labelledby="trust-title">
          <div className="container trust-grid">
            <div>
              <p className="eyebrow">Built to be trustworthy</p>
              <h2 id="trust-title" className="section-title">Tested on a year and on fields it never saw</h2>
              <p className="lead-sm">
                The AI predicts a field&apos;s greenness (NDVI) 7–20 days ahead. We compared its average
                error with a simple rule any grounds crew could use: &ldquo;it will look the same as last time.&rdquo;
                Lower is better.
              </p>
              <div className="result-cards">
                <div className="result-card">
                  <p className="result-label">Unseen year (2025)</p>
                  <p className="result-big">16% <span>lower error</span></p>
                  <dl className="result-rows">
                    <div><dt>AI model</dt><dd>0.058 NDVI</dd></div>
                    <div><dt>“Same as last time”</dt><dd>0.069</dd></div>
                    <div><dt>Seasonal average</dt><dd>0.086</dd></div>
                  </dl>
                </div>
                <div className="result-card">
                  <p className="result-label">Unseen fields</p>
                  <p className="result-big">14% <span>lower error</span></p>
                  <dl className="result-rows">
                    <div><dt>AI model</dt><dd>0.060 NDVI</dd></div>
                    <div><dt>“Same as last time”</dt><dd>0.069</dd></div>
                    <div><dt>Seasonal average</dt><dd>0.076</dd></div>
                  </dl>
                </div>
              </div>
              <p className="fine-print">
                Mean absolute error, 22 Denver-area fields, 2019–2025 (ml/results_v3.md). Both
                improvements are reliable: across 1,000 re-draws of the fields, the middle 95% of the
                differences stayed above zero. Honest limits: on unseen
                fields the AI was <strong>not</strong> clearly better than averaging the last few
                images, and the results are slightly optimistic because version 3 was designed after
                earlier tests.
              </p>
              {/* Photo AI test results (added 2026-11-26): photo_classifier_v1.json, website (int8) model */}
              <h3 className="trust-subtitle">Photo AI: tested on 379 photos it never saw</h3>
              <div className="result-cards">
                <div className="result-card">
                  <p className="result-label">Unseen photos</p>
                  <p className="result-big">90.0% <span>right category</span></p>
                  <dl className="result-rows">
                    <div><dt>Averaged over the 6 categories</dt><dd>69.3%</dd></div>
                    <div><dt>Said &ldquo;Uncertain&rdquo;</dt><dd>27.4%</dd></div>
                    <div><dt>Right when it answered</dt><dd>96.7%</dd></div>
                  </dl>
                </div>
              </div>
              <p className="fine-print">
                Test photos were kept apart from training by site or source. Honest limits: most photos
                came from public datasets and published articles, not real sports fields, and each
                category came mostly from one source, so real-world accuracy may be lower. Wear and
                dormant grass had only 2 test photos each. Results are preliminary: a turf expert
                should confirm before anything is treated.
              </p>
            </div>
            <ul className="principles">
              {PRINCIPLES.map((p) => (
                <li key={p.title}>
                  <span className="feature-icon"><Icon name={p.icon} size={24} /></span>
                  <div>
                    <h3>{p.title}</h3>
                    <p>{p.text}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* ---- Call to action ---- */}
        <section className="section">
          <div className="container">
            <div className="cta-banner">
              <div>
                <h2>Try SpectralTurf AI on your field</h2>
                <p>Outline a park or sports field in Colorado and get a real satellite check, usually within a minute. Then check a photo of any problem spot.</p>
              </div>
              <Link to="/login" className="btn btn-gold btn-lg">
                Get started <Icon name="arrowRight" size={18} />
              </Link>
            </div>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
