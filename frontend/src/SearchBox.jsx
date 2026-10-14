/*
 * SearchBox.jsx - Find a place in Colorado using OpenStreetMap's Nominatim service.
 *
 * Nominatim usage policy (https://operations.osmfoundation.org/policies/nominatim/):
 *   - At most 1 request per second   -> we only search when the user presses Search
 *   - No search-as-you-type          -> we never search on each keystroke
 *   - Show attribution               -> "Search by OpenStreetMap Nominatim" below the box
 * It is a free, volunteer-run service meant for light use like this project.
 */
import { useRef, useState } from 'react';

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';
// Colorado's borders as a box: west, north, east, south.
const COLORADO_VIEWBOX = '-109.06,41.00,-102.04,36.99';

export default function SearchBox({ onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const lastSearchTime = useRef(0);

  async function handleSubmit(event) {
    event.preventDefault(); // stop the page from reloading
    const text = query.trim();
    if (!text) return;

    // Respect the 1-request-per-second limit.
    if (Date.now() - lastSearchTime.current < 1000) {
      setMessage('Please wait a second between searches.');
      return;
    }
    lastSearchTime.current = Date.now();

    setLoading(true);
    setMessage('');
    setResults([]);
    try {
      const params = new URLSearchParams({
        q: text,
        format: 'jsonv2',
        limit: '5',
        countrycodes: 'us',
        viewbox: COLORADO_VIEWBOX,
        bounded: '1', // only return places inside the Colorado box
      });
      const response = await fetch(`${NOMINATIM_URL}?${params}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const places = await response.json();

      if (places.length === 0) {
        setMessage(`No places found in Colorado for "${text}". Try adding the city name.`);
      } else if (places.length === 1) {
        choose(places[0]);
      } else {
        setResults(places);
      }
    } catch (error) {
      setMessage(`Search failed (${error.message}). Check your internet connection and try again.`);
    } finally {
      setLoading(false);
    }
  }

  function choose(place) {
    // Nominatim gives the place's box as [south, north, west, east] (as text).
    const [south, north, west, east] = place.boundingbox.map(Number);
    onSelect({ south, north, west, east });
    setResults([]);
    setMessage(`Showing: ${place.display_name}`);
  }

  return (
    <div className="search">
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Park, school, or address in Colorado"
          aria-label="Search for a place in Colorado"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Searching…' : 'Search'}
        </button>
      </form>

      {results.length > 0 && (
        <ul className="search-results">
          {results.map((place) => (
            <li key={place.place_id}>
              <button type="button" onClick={() => choose(place)}>
                {place.display_name}
              </button>
            </li>
          ))}
        </ul>
      )}

      {message && <p className="search-message">{message}</p>}
      <p className="attribution">
        Search by <a href="https://nominatim.openstreetmap.org/" target="_blank" rel="noreferrer">OpenStreetMap Nominatim</a>
      </p>
    </div>
  );
}
