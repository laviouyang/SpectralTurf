/*
 * ChatExtras.jsx - Photo and speech helpers for the "Ask SpectralTurf" chat.
 *
 *  PhotoButton   pick or take ONE photo of the field. It is shrunk in the browser (max 1600 px)
 *                before uploading; the server shrinks it again and removes hidden data such as
 *                the GPS location. A photo is NOT a measurement: the AI only describes what
 *                it can see and never names a disease or cause.
 *  MicButton     speak your question instead of typing it (the browser's speech recognition;
 *                in Chrome/Edge your voice is turned into text by the browser maker's servers).
 *                The words go into the text box so you can check them before pressing Ask.
 *  ReadAloud     reads an answer out loud with the computer's own voice (stays on your device).
 */
import { useEffect, useRef, useState } from 'react';

const MAX_FILE_MB = 20;
const BROWSER_SIDE = 1600;

// Shrink the photo in the browser and turn it into JPEG base64 text (smaller upload).
function shrinkPhoto(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, BROWSER_SIDE / Math.max(img.width, img.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
      resolve({ base64: dataUrl.split(',')[1], preview: dataUrl });
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('This file could not be opened as a photo (use JPEG, PNG or WebP).'));
    };
    img.src = url;
  });
}

export function PhotoButton({ photo, onChange, disabled }) {
  const input = useRef(null);
  const [error, setError] = useState('');

  async function choose(e) {
    const file = e.target.files?.[0];
    e.target.value = ''; // lets you pick the same file again
    if (!file) return;
    setError('');
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      setError('Please choose a JPEG, PNG or WebP photo.');
      return;
    }
    if (file.size > MAX_FILE_MB * 1024 * 1024) {
      setError(`That photo is bigger than ${MAX_FILE_MB} MB.`);
      return;
    }
    try {
      onChange(await shrinkPhoto(file));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="chat-photo">
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={choose} />
      {photo ? (
        <div className="chat-photo-preview">
          <img src={photo.preview} alt="Photo to send with your question" />
          <button type="button" className="link-button" onClick={() => onChange(null)} disabled={disabled}>
            Remove photo
          </button>
        </div>
      ) : (
        <button type="button" className="secondary" onClick={() => input.current.click()} disabled={disabled}
                title="Attach one photo of the field">
          📷 Photo
        </button>
      )}
      {error && <p className="problems">{error}</p>}
    </div>
  );
}

const Recognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);

export function MicButton({ onText, disabled }) {
  const [listening, setListening] = useState(false);
  const [error, setError] = useState('');
  const recognizer = useRef(null);

  useEffect(() => () => recognizer.current?.abort(), []); // stop listening if the panel goes away

  if (!Recognition) {
    return <span className="muted" title="Voice typing works in Chrome and Edge">🎤 not supported here</span>;
  }

  function start() {
    setError('');
    const r = new Recognition();
    r.lang = 'en-US';
    r.interimResults = true; // show words while you speak
    r.onresult = (event) => {
      const words = Array.from(event.results).map((result) => result[0].transcript).join('');
      onText(words);
    };
    r.onerror = (event) => {
      setError(event.error === 'not-allowed'
        ? 'Microphone blocked. Allow it in the browser (lock icon in the address bar).'
        : `Voice typing stopped (${event.error}).`);
    };
    r.onend = () => setListening(false);
    recognizer.current = r;
    r.start();
    setListening(true);
  }

  return (
    <>
      <button type="button" className={listening ? '' : 'secondary'} disabled={disabled}
              onClick={() => (listening ? recognizer.current?.stop() : start())}
              title="Speak your question (the words appear in the box; check them, then press Ask)">
        {listening ? '⏹ Stop' : '🎤 Speak'}
      </button>
      {error && <p className="problems">{error}</p>}
    </>
  );
}

// Text for speaking: no Markdown stars, and "0.68" read as "0 point 68" is fine.
function speakable(text) {
  return text.replace(/\*\*/g, '').replace(/^\s*[*-]\s+/gm, '');
}

export function ReadAloud({ text }) {
  const [speaking, setSpeaking] = useState(false);
  useEffect(() => () => window.speechSynthesis?.cancel(), []);
  if (!window.speechSynthesis) return null;

  function toggle() {
    window.speechSynthesis.cancel();
    if (speaking) {
      setSpeaking(false);
      return;
    }
    const utterance = new SpeechSynthesisUtterance(speakable(text));
    utterance.lang = 'en-US';
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  return (
    <button type="button" className="link-button" onClick={toggle}>
      {speaking ? '⏹ Stop reading' : '🔊 Read aloud'}
    </button>
  );
}
