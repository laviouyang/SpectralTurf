/*
 * AboutPage.jsx - "/about": how SpectralTurf works and what it can't do (added 2026-11-23).
 *
 * 2026-11-27 later (student request): the methodology (satellite data, inspection flag, AI) moved
 * to HowItWorksPage.jsx and the sources to SourcesPage.jsx; this page is about the project itself.
 * 2026-11-27 (student request): made SHORT. Things already on the homepage (who it's for, the
 * steps, the feature list, the test results, the grass lists per region) and in the footer (data
 * credits) are not repeated here. Thresholds are labeled as this project's choices.
 */
import { Link } from './router.jsx';
import { GITHUB_URL, SiteFooter, SiteNav } from './SiteChrome.jsx';

const SECTIONS = [
  ['project', 'The project'],
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
            <p className="eyebrow">About</p>
            <h1>About SpectralTurf AI, and what it can&apos;t do</h1>
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
            <section id="project">
              <h2>The project</h2>
              <p>
                SpectralTurf AI is a high-school project by Yuanzhi (Lavi) Ouyang. It started from one
                question: can free satellite images tell a grounds crew which part of a big grass field
                to walk to first?
              </p>
              <p>
                It is <strong>decision support</strong>. It points to where to look and says how sure it
                is. It does not control irrigation, tell anyone how much to water, or replace a turf
                expert: photo results are preliminary, and a person always checks the field before
                acting.
              </p>
              <p>
                How each part works is on the <Link to="/how-it-works">How it works</Link> page; every
                data source and reference is on the <Link to="/sources">Sources</Link> page.
              </p>
            </section>

            <section id="regions">
              <h2>Grass regions</h2>
              <p>
                The region is only a label; the satellite math is the same everywhere. Only Region 3
                (Northern &amp; Central Plains) is validated, because the baseline, color cutoff and AI
                were made from Denver-area fields. The region map is our own approximation, not an official
                USDA map (sources on the <Link to="/sources#regions">Sources</Link> page).
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
              <p>
                The source code is on <a href={GITHUB_URL} target="_blank" rel="noreferrer">GitHub</a>.
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
