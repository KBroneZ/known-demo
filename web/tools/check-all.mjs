// Runs every quality gate against the built sites and writes reports/quality.json.
import fs from 'node:fs';
import path from 'node:path';
import { WEB_ROOT, listSites } from './lib.mjs';
import { checkJsonLd } from './check-jsonld.mjs';
import { checkLinks } from './check-links.mjs';
import { checkWeight } from './check-weight.mjs';
import { checkBrowser } from './check-browser.mjs';
import { checkParity } from './check-fixture-parity.mjs';

const sites = listSites();
const out = { date: new Date().toISOString(), sites: {} };
let ok = checkParity();
for (const s of sites) {
  const j = checkJsonLd(s);
  const l = checkLinks(s);
  const w = checkWeight(s);
  out.sites[s] = { jsonld: j, links: l, weight: w.summary };
  ok = ok && j.ok && l.ok && w.ok;
}
const b = await checkBrowser(sites);
for (const r of b) {
  out.sites[r.site].browser = r;
  ok = ok && r.ok;
}
fs.mkdirSync(path.join(WEB_ROOT, 'reports'), { recursive: true });
fs.writeFileSync(path.join(WEB_ROOT, 'reports', 'quality.json'), JSON.stringify(out, null, 2));
console.log(ok ? '\nALL GATES PASS' : '\nSOME GATES FAILED');
process.exit(ok ? 0 : 1);
