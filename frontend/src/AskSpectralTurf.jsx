/*
 * AskSpectralTurf.jsx - Stage 10 Step 10: "Ask SpectralTurf" chat panel.
 *
 * The question goes to OUR backend (POST /api/ai/ask), never straight to Gemini: the Gemini
 * key stays on the server. The backend lets Gemini look things up with read-only tools
 * (your own saved fields, or only the field on screen if you're not logged in) and checks
 * every number in the answer against that data before sending it here.
 * Each question is answered on its own (the AI does not remember earlier questions).
 * Added 2026-11-22: attach a photo, speak the question, and have answers read aloud
 * (see ChatExtras.jsx).
 */
import { useState } from 'react';
import { askSpectralTurf } from './api.js';
import { MicButton, PhotoButton, ReadAloud } from './ChatExtras.jsx';

// Version 2: questions are always about ONE picked field, so the presets are about that field.
const FIELD_PRESETS = [
  'Should I inspect this field?',
  'Why was this field flagged?',
  'How reliable is this result?',
];
const PRESETS = [
  'Which field should I inspect first?',
  'Why was this field flagged?',
  'How reliable is this result?',
];
const MAX_CHARS = 500; // the backend refuses longer questions
const NOTE = 'AI-generated explanation based on SpectralTurf data. Confirm in person.';
const TOOL_NAMES = {
  get_my_fields: 'your fields',
  get_latest_analysis: 'latest analysis',
  get_expected_vs_observed: 'AI weather check',
  get_ranking: 'My Fields ranking',
  get_field_history: 'field history',
};

// Gemini writes a little Markdown (**bold**, "* " bullet lines). Show just those two things.
function boldParts(line) {
  return line.split(/\*\*(.+?)\*\*/g).map((part, i) => (i % 2 ? <strong key={i}>{part}</strong> : part));
}

function Answer({ text }) {
  const blocks = [];
  let bullets = [];
  const flush = () => {
    if (bullets.length) blocks.push(<ul key={`ul${blocks.length}`}>{bullets}</ul>);
    bullets = [];
  };
  text.split('\n').forEach((raw, i) => {
    const line = raw.trim();
    const bullet = line.match(/^[*-]\s+(.*)/);
    if (bullet) {
      bullets.push(<li key={i}>{boldParts(bullet[1])}</li>);
    } else {
      flush();
      if (line) blocks.push(<p key={i}>{boldParts(line)}</p>);
    }
  });
  flush();
  return <div className="ask-answer">{blocks}</div>;
}

// field (Version 2): 'screen' or a saved analysis id; questions are only about that field.
export default function AskSpectralTurf({ geometry, exclude, start, end, asOf, user, field, fieldLabel }) {
  const [question, setQuestion] = useState('');
  const [chat, setChat] = useState([]); // newest last: {question, reply?, error?}
  const [busy, setBusy] = useState(false);
  const [photo, setPhoto] = useState(null); // {base64, preview} or null

  async function send(text) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setQuestion('');
    const sentPhoto = photo;
    setPhoto(null); // one photo per question
    setChat((c) => [...c, { question: q, photo: sentPhoto?.preview }]);
    let entry;
    try {
      const reply = await askSpectralTurf({ question: q, geometry, exclude, start, end, as_of: asOf,
                                            photo: sentPhoto?.base64, field });
      entry = { question: q, photo: sentPhoto?.preview, reply };
    } catch (e) {
      entry = { question: q, photo: sentPhoto?.preview, error: e.message };
    }
    setChat((c) => [...c.slice(0, -1), entry]);
    setBusy(false);
  }

  return (
    <div className="ask-panel">
      <p className="next-step"><strong>{NOTE}</strong></p>
      <p className="muted">
        {field ? <>Every question is about <strong>{fieldLabel}</strong></> : (
          <>Ask about {user ? 'your saved fields or ' : ''}the field on the map
          {user ? '' : ' (log in to ask about your saved fields)'}</>
        )}, as of {asOf}. Answers use only
        SpectralTurf data; the AI never gives watering amounts or names a cause. Your question,
        field data and any photo are sent to Google Gemini (no username, no field names, no map
        location; the photo&apos;s hidden GPS data is removed). Please don&apos;t type personal
        information or send photos of people.
      </p>

      <div className="ask-presets">
        {(field ? FIELD_PRESETS : PRESETS).map((p) => (
          <button key={p} type="button" onClick={() => send(p)} disabled={busy}>{p}</button>
        ))}
      </div>

      <form onSubmit={(e) => { e.preventDefault(); send(question); }}>
        <textarea
          value={question}
          maxLength={MAX_CHARS}
          rows={2}
          placeholder={field ? 'Or type your own question about this field…' : 'Or type your own question about your fields…'}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(question); }
          }}
        />
        <div className="ask-send">
          <PhotoButton photo={photo} onChange={setPhoto} disabled={busy} />
          <MicButton onText={(words) => setQuestion(words.slice(0, MAX_CHARS))} disabled={busy} />
          <span className="muted">{question.length}/{MAX_CHARS}</span>
          <button type="submit" disabled={busy || !question.trim()}>{busy ? 'Thinking…' : 'Ask'}</button>
        </div>
      </form>

      <ol className="ask-chat">
        {chat.map((m, i) => (
          <li key={i}>
            <p className="ask-question"><strong>You:</strong> {m.question}</p>
            {m.photo && <img className="ask-photo" src={m.photo} alt="Photo you sent" />}
            {!m.reply && !m.error && <p className="muted">Looking up your field data… (can take 10–30 s)</p>}
            {m.error && <p className="problems-box">{m.error}</p>}
            {m.reply && (
              <div className={`inspect-card ${m.reply.status === 'ok' ? 'inspect-calm' : 'inspect-unknown'}`}>
                <strong>SpectralTurf AI:</strong>
                <Answer text={m.reply.answer} />
                <ReadAloud text={m.reply.answer} />
                {m.reply.photo_used && (
                  <p className="muted">
                    The photo is not a measurement: the AI only describes what it can see. Numbers
                    come from satellite data.
                  </p>
                )}
                {Object.keys(m.reply.field_names || {}).length > 0 && (
                  <p className="muted">
                    Field ids: {Object.entries(m.reply.field_names).map(([id, name]) => `${id} = ${name}`).join(' · ')}
                  </p>
                )}
                {m.reply.tools_used?.length > 0 && (
                  <p className="muted">
                    Data looked up: {m.reply.tools_used.map((t) => TOOL_NAMES[t] || t).join(', ')}
                  </p>
                )}
                <p className="muted"><em>{m.reply.label}</em></p>
              </div>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
