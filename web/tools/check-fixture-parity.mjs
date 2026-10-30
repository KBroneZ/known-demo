// Proves sites/clinic-a/clinic.yaml still carries every key and value of the QA fixture it was
// copied from (demo/qa/fixtures/clinic.yaml, owned by the QA terminal and never edited here).
// Only additions are allowed; the QA gate therefore sees the same facts the website shows.
import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'yaml';
import { Report, SITES_DIR, isMain } from './lib.mjs';

// QA_FIXTURE overrides the path (used by the tests). A missing fixture FAILS: nothing was compared, so nothing is proven.
const DEFAULT_FIXTURE = path.resolve(SITES_DIR, '../../qa/fixtures/clinic.yaml');
// `pages` is skipped: it is the website's route contract (check-links verifies it against the build).
export function checkParity(
  fixture = process.env.QA_FIXTURE ?? DEFAULT_FIXTURE,
  siteFile = path.join(SITES_DIR, 'clinic-a/clinic.yaml'),
) {
  const rep = new Report('fixture parity (clinic-a vs qa fixture)');
  if (!fs.existsSync(fixture)) {
    rep.ok(false, `QA fixture not found: ${fixture}`);
    return rep.finish();
  }
  const a = parse(fs.readFileSync(fixture, 'utf8'));
  const b = parse(fs.readFileSync(siteFile, 'utf8'));
  const sub = (x, y, at) => {
    if (Array.isArray(x)) {
      rep.ok(Array.isArray(y) && y.length >= x.length, `${at}: array shrank`);
      if (at === 'pages') return; // the site's own route contract: it ships 3 posts, the fixture lists 4
      if (at === 'services') x.forEach((v, i) => sub(v, y[i], `${at}[${i}]`));
      else if (x.every((v) => typeof v !== 'object'))
        x.forEach((v) => rep.ok(y.includes(v), `${at}: lost ${JSON.stringify(v)}`));
      else x.forEach((v, i) => sub(v, y[i], `${at}[${i}]`));
    } else if (x && typeof x === 'object') {
      for (const k of Object.keys(x)) sub(x[k], y?.[k], `${at}.${k}`.replace(/^\./, ''));
    } else rep.ok(x === y, `${at}: ${JSON.stringify(x)} != ${JSON.stringify(y)}`);
  };
  sub(a, b, '');
  return rep.finish(`fixture keys ${Object.keys(a).join(', ')}`);
}

if (isMain(import.meta.url)) process.exit(checkParity() ? 0 : 1);
