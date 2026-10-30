// Do the gates actually fail? Inject known defects into a copy of clinic-a/dist pages
// (restored afterwards) and confirm each defect is caught by the intended check.
import fs from 'node:fs';
import path from 'node:path';
import { distDir, WEB_ROOT } from './lib.mjs';
import { checkJsonLd } from './check-jsonld.mjs';
import { checkLinks } from './check-links.mjs';

const SITE = 'clinic-a';
const quiet = (fn) => {
  const log = console.log;
  console.log = () => {};
  try {
    return fn();
  } finally {
    console.log = log;
  }
};
const cases = [
  {
    name: 'invented aggregateRating in Dentist JSON-LD',
    file: 'index.html',
    check: checkJsonLd,
    mutate: (h) =>
      h.replace(
        '"@type":"Dentist"',
        '"@type":"Dentist","aggregateRating":{"@type":"AggregateRating","ratingValue":"4.9","reviewCount":"212"}',
      ),
  },
  {
    name: 'wrong phone number in Dentist JSON-LD',
    file: 'contact.html',
    check: checkJsonLd,
    mutate: (h) => h.replace('"telephone":"(512) 555-0142"', '"telephone":"(512) 555-0199"'),
  },
  {
    name: 'FAQ markup that is not visible on the page',
    file: 'faq.html',
    check: checkJsonLd,
    mutate: (h) => h.replace(/(<h2[^>]*>)What are the hours/, '$1Hidden: what are the hours'),
  },
  {
    name: 'BlogPosting dateModified in the future',
    file: 'blog/how-often-dental-cleaning.html',
    check: checkJsonLd,
    mutate: (h) => h.replace('"dateModified":"2026-10-06"', '"dateModified":"2031-01-01"'),
  },
  {
    name: 'broken internal link',
    file: 'about.html',
    check: checkLinks,
    mutate: (h) => h.replace('href="/team"', 'href="/teem"'),
  },
  {
    name: 'broken #anchor to a dentist',
    file: 'blog/dental-emergency-austin.html',
    check: checkLinks,
    mutate: (h) => h.replace('href="/team#dr-elena-marsh"', 'href="/team#dr-nobody"'),
  },
  {
    name: 'noindex slipped in',
    file: 'services.html',
    check: checkLinks,
    mutate: (h) => h.replace('<title>', '<meta name="robots" content="noindex"><title>'),
  },
  {
    name: 'canonical points elsewhere',
    file: 'team.html',
    check: checkLinks,
    mutate: (h) => h.replace('example/team"', 'example/teams"'),
  },
  {
    name: 'foreign phone number in body text',
    file: 'faq.html',
    check: checkLinks,
    mutate: (h) => h.replace('Skip to content</a>', 'Skip to content</a><p>Call (512) 555-0000</p>'),
  },
  {
    name: 'opening hours: opens time changed in JSON-LD',
    file: 'contact.html',
    check: checkJsonLd,
    mutate: (h) => h.replace('"opens":"08:00"', '"opens":"09:30"'),
  },
  {
    name: 'opening hours: Friday became Saturday in JSON-LD',
    file: 'contact.html',
    check: checkJsonLd,
    mutate: (h) => h.replace('"dayOfWeek":["Friday"]', '"dayOfWeek":["Saturday"]'),
  },
  {
    name: 'street address changed in JSON-LD',
    file: 'index.html',
    check: checkJsonLd,
    mutate: (h) => h.replace('2214 Meridian Park Drive, Suite 110', '9 Elsewhere Street'),
  },
  {
    name: 'email changed in JSON-LD',
    file: 'index.html',
    check: checkJsonLd,
    mutate: (h) => h.replace('"email":"hello@bluebonnethollowdental.example"', '"email":"someone@else.example"'),
  },
  {
    name: 'insecure http:// link to the own site',
    file: 'about.html',
    check: checkLinks,
    mutate: (h) => h.replace('href="/team"', 'href="http://www.bluebonnethollowdental.example/team"'),
  },
  {
    name: 'same-page #fragment that does not exist',
    file: 'blog.html',
    check: checkLinks,
    mutate: (h) => h.replace('href="#main"', 'href="#nomain"'),
  },
];

let caught = 0;
for (const c of cases) {
  const f = path.join(distDir(SITE), c.file);
  const original = fs.readFileSync(f, 'utf8');
  const mutated = c.mutate(original);
  if (mutated === original) throw new Error(`selftest mutation did not apply: ${c.name}`);
  fs.writeFileSync(f, mutated);
  try {
    const r = quiet(() => c.check(SITE));
    const hit = !r.ok;
    if (hit) caught++;
    console.log(`${hit ? 'CAUGHT ' : 'MISSED '} ${c.name}${hit ? '  -> ' + r.failures[0].slice(0, 90) : ''}`);
  } finally {
    fs.writeFileSync(f, original);
  }
}
const clean = quiet(() => [checkJsonLd(SITE), checkLinks(SITE)].every((r) => r.ok));
console.log(`\n${caught}/${cases.length} injected defects caught; pristine dist passes: ${clean}`);
fs.mkdirSync(path.join(WEB_ROOT, 'reports'), { recursive: true });
fs.writeFileSync(
  path.join(WEB_ROOT, 'reports', 'selftest.json'),
  JSON.stringify({ injected: cases.length, caught, pristinePasses: clean }, null, 2),
);
process.exit(caught === cases.length && clean ? 0 : 1);
