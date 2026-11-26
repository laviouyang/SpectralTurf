// test_field_picker.mjs - checks distinctFields in src/FieldPicker.jsx (the field drop-down)
// against the SAME cases as the backend test (backend/field_list_cases.json), so the drop-down
// and predict.distinct_saved_fields list exactly the same fields.
// Run (in frontend):   node scripts/test_field_picker.mjs
import { readFileSync } from 'node:fs';
import { transformSync } from 'esbuild'; // comes with Vite

const here = new URL('.', import.meta.url);
// FieldPicker.jsx has JSX, which Node can't read; esbuild turns it into plain JavaScript.
// jsxFactory 'h' means no React import is needed (we only call distinctFields, never draw).
const source = readFileSync(new URL('../src/FieldPicker.jsx', here), 'utf8');
const { code } = transformSync(source, { loader: 'jsx', format: 'esm', jsxFactory: 'h' });
const { distinctFields } = await import('data:text/javascript,' + encodeURIComponent(code));

const data = JSON.parse(readFileSync(new URL('../../backend/field_list_cases.json', here), 'utf8'));
let passed = 0;
for (const c of data.cases) {
  const saved = c.saved.map((r) => ({ id: r.id, name: r.name, geometry: data.shapes[r.shape], exclusions: [] }));
  const ids = distinctFields(saved).map((f) => f.id);
  if (JSON.stringify(ids) !== JSON.stringify(c.expected_ids)) {
    console.error(`FAIL distinctFields: ${c.name}\n  got ${JSON.stringify(ids)}, expected ${JSON.stringify(c.expected_ids)}`);
    process.exit(1);
  }
  passed += 1;
  console.log(`PASS distinctFields: ${c.name}`);
}
console.log(`\nAll ${passed} checks passed.`);
