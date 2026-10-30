// Tests for the tooling itself: the gates must fail when they should, never pass on nothing.
//   npm test        (node --test tools/tests). Needs the sites built once (npm run build).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import { WEB_ROOT, Report, listSites, isMain } from '../lib.mjs';
import { snapshot, diffSite, diffFailed, stableCids } from '../golden.mjs';
import { checkParity } from '../check-fixture-parity.mjs';
import { safeJson, cssTokens } from '../../packages/theme/src/lib/safe.ts';
import { ThemeSchema, ClinicSchema } from '../../packages/schema/src/index.ts';

const LIB_URL = pathToFileURL(path.join(WEB_ROOT, 'tools', 'lib.mjs')).href;
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), 'web tools '));
const silent = (fn) => {
  const l = console.log;
  console.log = () => {};
  try {
    return fn();
  } finally {
    console.log = l;
  }
};

// ---------------------------------------------------------------- H1: main-script guard
test('isMain is true for a script run from a path with spaces, false when imported', () => {
  const dir = path.join(tmp(), 'dir with spaces & (parens)');
  fs.mkdirSync(dir);
  fs.writeFileSync(
    path.join(dir, 'probe.mjs'),
    `import { isMain } from '${LIB_URL}';\nconsole.log(isMain(import.meta.url) ? 'MAIN' : 'IMPORTED');\n`,
  );
  fs.writeFileSync(path.join(dir, 'importer.mjs'), `import './probe.mjs';\n`);
  const direct = spawnSync(process.execPath, [path.join(dir, 'probe.mjs')], { encoding: 'utf8' });
  assert.equal(direct.stdout.trim(), 'MAIN', direct.stderr);
  const viaImport = spawnSync(process.execPath, [path.join(dir, 'importer.mjs')], { encoding: 'utf8' });
  assert.equal(viaImport.stdout.trim(), 'IMPORTED', viaImport.stderr);
  const relative = spawnSync(process.execPath, ['probe.mjs'], { cwd: dir, encoding: 'utf8' });
  assert.equal(relative.stdout.trim(), 'MAIN', 'relative argv[1] must also work');
});

test('a real tool actually runs when started from another cwd with a relative path', () => {
  const r = spawnSync(process.execPath, [path.join('web', 'tools', 'golden.mjs'), 'diff'], {
    cwd: path.dirname(WEB_ROOT),
    encoding: 'utf8',
  });
  assert.match(r.stdout, /clinic-a: \d+ files/, 'tool printed nothing: main guard failed');
  assert.equal(r.status, 0, r.stdout + r.stderr);
});

test('isMain is false when argv[1] is missing', () => {
  const saved = process.argv[1];
  process.argv[1] = '';
  try {
    assert.equal(isMain(import.meta.url), false);
  } finally {
    process.argv[1] = saved;
  }
});

// ---------------------------------------------------------------- H2: nothing-checked is a failure
test('Report with zero checks fails', () => {
  assert.equal(
    silent(() => new Report('empty').finish()),
    false,
  );
  const r = new Report('one');
  r.ok(true, '');
  assert.equal(
    silent(() => r.finish()),
    true,
  );
});

test('listSites rejects unknown sites, a bare --site and an empty sites dir', () => {
  assert.throws(() => listSites(['node', 'x', '--site', 'clinc-a'], {}), /unknown site/);
  assert.throws(() => listSites(['node', 'x', '--site'], {}), /needs a comma-separated list/);
  assert.throws(() => listSites(['node', 'x'], { SITES: 'foo' }), /unknown site/);
  assert.throws(() => listSites(['node', 'x'], {}, tmp()), /no sites found/);
  assert.deepEqual(listSites(['node', 'x', '--site', 'clinic-a'], {}), ['clinic-a']);
});

test('golden diff fails on an empty golden, on pages added since approval, and on changes outside the footer', () => {
  const empty = tmp();
  assert.equal(diffFailed(diffSite('clinic-a', 'footer', empty)), true, 'empty golden must fail');

  const g = tmp();
  snapshot('clinic-a', g);
  assert.equal(diffFailed(diffSite('clinic-a', 'footer', g)), false, 'identical must pass');

  fs.rmSync(path.join(g, 'clinic-a', 'faq.html'));
  const added = diffSite('clinic-a', 'footer', g);
  assert.deepEqual(added.added, ['faq.html']);
  assert.equal(diffFailed(added), true, 'a page missing from golden must fail');

  snapshot('clinic-a', g);
  const about = path.join(g, 'clinic-a', 'about.html');
  fs.writeFileSync(about, fs.readFileSync(about, 'utf8').replace('<h1', '<h1 data-x="1"'));
  assert.equal(diffFailed(diffSite('clinic-a', 'footer', g)), true, 'a change outside the footer must fail');

  snapshot('clinic-a', g);
  fs.writeFileSync(about, fs.readFileSync(about, 'utf8').replace('Fictional demo:', 'Fictional demo!'));
  const footerOnly = diffSite('clinic-a', 'footer', g);
  assert.equal(footerOnly.regionOnly, 1);
  assert.equal(diffFailed(footerOnly), false, 'a footer-only change is allowed');
});

test('stableCids ignores where the repo was built but still sees a real change', () => {
  const page = (x, y, text) =>
    `<style>a[data-astro-cid-${x}]{color:red}</style><a data-astro-cid-${x}>${text}</a><p data-astro-cid-${y}></p>`;
  assert.equal(stableCids(page('2dxizym6', 'ng5hga67', 'Book')), stableCids(page('k3j9qa01', 'p0x7rr2b', 'Book')));
  assert.notEqual(stableCids(page('2dxizym6', 'ng5hga67', 'Book')), stableCids(page('k3j9qa01', 'p0x7rr2b', 'Call')));
  // two ids collapsing into one is a structural change, not a rename
  assert.notEqual(stableCids(page('aaaaaaaa', 'bbbbbbbb', 'Book')), stableCids(page('aaaaaaaa', 'aaaaaaaa', 'Book')));
});

test('golden snapshot refuses to overwrite with a site that has no built HTML', () => {
  const g = tmp();
  snapshot('clinic-a', g);
  const before = fs.readdirSync(path.join(g, 'clinic-a')).length;
  const dist = path.join(WEB_ROOT, 'sites', 'clinic-a', 'dist');
  const hidden = dist + '.hidden';
  fs.renameSync(dist, hidden);
  try {
    assert.throws(() => snapshot('clinic-a', g), /no built HTML/);
  } finally {
    fs.renameSync(hidden, dist);
  }
  assert.equal(fs.readdirSync(path.join(g, 'clinic-a')).length, before, 'approved snapshot must be untouched');
});

test('fixture parity fails when the QA fixture is missing or a fixture value differs', () => {
  assert.equal(
    silent(() => checkParity(path.join(tmp(), 'nope.yaml'))),
    false,
  );
  const fx = path.join(tmp(), 'clinic.yaml');
  const real = path.resolve(WEB_ROOT, '../qa/fixtures/clinic.yaml');
  if (!fs.existsSync(real)) return; // the QA fixture ships next to web/ in this repo
  fs.writeFileSync(fx, fs.readFileSync(real, 'utf8').replace('"(512) 555-0142"', '"(512) 555-0100"'));
  assert.equal(
    silent(() => checkParity(fx)),
    false,
    'a changed fixture value must be reported',
  );
  assert.equal(
    silent(() => checkParity(real)),
    true,
  );
});

// ---------------------------------------------------------------- M7: markup break-out
test('safeJson can never close a <script> block', () => {
  const hostile = { answer: 'x</script><script>alert(1)</script><!-- y', sep: '  ' };
  const out = safeJson(hostile);
  assert.ok(!out.includes('<') && !out.includes(' ') && !out.includes(' '));
  assert.deepEqual(JSON.parse(out), hostile, 'escaping must not change the data');
});

test('cssTokens strips markup characters', () => {
  assert.ok(!cssTokens({ a: '</style><script>' }).includes('<'));
});

test('ThemeSchema rejects font and radius values that could break out of <style>', () => {
  const ok = JSON.parse(fs.readFileSync(path.join(WEB_ROOT, 'sites/clinic-a/theme.json'), 'utf8'));
  assert.equal(ThemeSchema.safeParse(ok).success, true);
  for (const bad of [
    { ...ok, fonts: { ...ok.fonts, heading: 'Georgia}</style><script>alert(1)</script>' } },
    { ...ok, fonts: { ...ok.fonts, body: 'a;b{c:d}' } },
    { ...ok, radius: '8px;background:url(//evil)' },
    { ...ok, radius: 'calc(1px)' },
  ])
    assert.equal(ThemeSchema.safeParse(bad).success, false, JSON.stringify(bad));
});

test('ClinicSchema rejects real-looking data (phone, domain, fictional flag)', async () => {
  const { parse } = await import('yaml');
  const clinic = parse(fs.readFileSync(path.join(WEB_ROOT, 'sites/clinic-b/clinic.yaml'), 'utf8'));
  assert.equal(ClinicSchema.safeParse(clinic).success, true);
  assert.equal(ClinicSchema.safeParse({ ...clinic, fictional: false }).success, false);
  assert.equal(ClinicSchema.safeParse({ ...clinic, website: 'https://example.com' }).success, false);
  assert.equal(ClinicSchema.safeParse({ ...clinic, nap: { ...clinic.nap, phone: '(512) 123-4567' } }).success, false);
});

// ---------------------------------------------------------------- mutation probes (defects injected into built pages)
test('selftest: every injected defect is caught and the pristine build passes', () => {
  const r = spawnSync(process.execPath, [path.join(WEB_ROOT, 'tools', 'selftest.mjs')], { encoding: 'utf8' });
  assert.equal(r.status, 0, r.stdout + r.stderr);
  const m = r.stdout.match(/(\d+)\/(\d+) injected defects caught/);
  assert.ok(m && m[1] === m[2] && Number(m[2]) >= 15, r.stdout);
});

// ---------------------------------------------------------------- add-client leaves nothing behind on invalid input
test('add-client rejects an invalid post before creating any folder', () => {
  const dir = tmp();
  const base = fs
    .readFileSync(path.join(WEB_ROOT, 'sites/clinic-b/clinic.yaml'), 'utf8')
    .replace(/^id: .*/m, 'id: test-bad-post-clinic');
  const yamlFile = path.join(dir, 'clinic.yaml');
  fs.writeFileSync(yamlFile, base);
  const posts = path.join(dir, 'posts');
  fs.mkdirSync(posts);
  fs.writeFileSync(path.join(posts, 'bad.md'), '---\ntitle: "x"\nslug: Bad Slug\n---\nbody\n');
  const r = spawnSync(process.execPath, [path.join(WEB_ROOT, 'tools', 'add-client.mjs'), yamlFile, '--posts', posts], {
    encoding: 'utf8',
  });
  assert.equal(r.status, 1, r.stdout + r.stderr);
  assert.match(r.stderr, /posts are not valid/);
  assert.equal(fs.existsSync(path.join(WEB_ROOT, 'sites', 'test-bad-post-clinic')), false, 'no half-built site folder');
});
