/*
 * FieldPicker.jsx - Version 2 (2026-11-25): a drop-down to pick ONE field for the AI tools
 * (AI Weather Check, What if?, Ask AI). Choices: the field drawn on the map (if any) and
 * every field saved in "My Fields".
 *
 * "My Fields" = distinct saved outlines (same outline + same exclusions = same field), newest
 * save first. This mirrors predict.distinct_saved_fields in the backend.
 */

// Saved analyses (newest first) -> one entry per distinct field.
export function distinctFields(history) {
  const seen = new Set();
  const fields = [];
  for (const item of history) {
    const key = JSON.stringify([item.geometry, item.exclusions]);
    if (seen.has(key)) continue;
    seen.add(key);
    fields.push(item);
  }
  return fields;
}

// value: '' (nothing picked), 'map' (field on the map), or a saved analysis id as text.
export default function FieldPicker({ label, value, onChange, fields, mapAvailable, required = false }) {
  // A choice that isn't available (no field on the map, or a deleted saved field) shows as "Pick a field".
  const available = value === 'map' ? mapAvailable : fields.some((f) => String(f.id) === value);
  const shown = available ? value : '';
  return (
    <label className="field-picker">
      {label}
      <select value={shown} onChange={(e) => onChange(e.target.value)}>
        {(required || !shown) && <option value="">— Pick a field —</option>}
        <option value="map" disabled={!mapAvailable}>
          Field on the map{mapAvailable ? '' : ' (draw or analyze one first)'}
        </option>
        {fields.map((f) => (
          <option key={f.id} value={String(f.id)}>
            {f.name || 'Unnamed field'} (saved{f.observation_date ? `, image ${f.observation_date}` : ''})
          </option>
        ))}
      </select>
    </label>
  );
}
