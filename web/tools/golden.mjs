// Golden snapshots: the approved HTML of every page (plus sitemap, robots, llms.txt).
//   golden.mjs snapshot            save current dist/ as the golden copy
//   golden.mjs diff [--region footer]   compare dist/ with golden/
// A page "may change only in <region>" means: HTML outside that region is byte-identical and the
// visible text outside it is identical (content text diff = 0).
// Before comparing, Astro's scoped-style ids (data-astro-cid-<hash>) are renamed in order of first appearance.
// Astro hashes the absolute path of components that live outside the site root (the shared theme), so the hash
// changes with the checkout folder and the OS; the renaming keeps every other byte of the comparison exact.
import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'node-html-parser';
import { WEB_ROOT, listSites, distDir, walk, isMain } from './lib.mjs';

// GOLDEN_DIR overrides the location (tests and prove-scale use a scratch copy so the approved golden/ is never rewritten by accident).
export const GOLDEN = process.env.GOLDEN_DIR ? path.resolve(process.env.GOLDEN_DIR) : path.join(WEB_ROOT, 'golden');
const KEEP = (p) => /\.(html|txt|xml)$/.test(p);

export function snapshot(site, golden = GOLDEN) {
  const out = path.join(golden, site);
  // never replace an approved snapshot with nothing (a failed build leaves no dist)
  const sources = fs.existsSync(distDir(site)) ? walk(distDir(site), KEEP) : [];
  if (!sources.some((f) => f.endsWith('.html')))
    throw new Error(`no built HTML in ${distDir(site)}: build the site before snapshotting`);
  fs.rmSync(out, { recursive: true, force: true });
  let n = 0;
  for (const f of sources) {
    const dest = path.join(out, path.relative(distDir(site), f));
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.copyFileSync(f, dest);
    n++;
  }
  return n;
}

const norm = (s) => s.replace(/\s+/g, ' ').trim();

/** Rename each distinct astro-cid-<hash> to astro-cid-<n>, numbered by first appearance in the page. */
export function stableCids(html) {
  const ids = new Map();
  return html.replace(/astro-cid-[a-z0-9]+/g, (cid) => {
    if (!ids.has(cid)) ids.set(cid, `astro-cid-${ids.size}`);
    return ids.get(cid);
  });
}

/** Split HTML into [before, region, after]. Region = <tag data-region="name">...</tag>. */
function split(html, region) {
  const open = html.indexOf(`data-region="${region}"`);
  if (open < 0) return [html, '', ''];
  const start = html.lastIndexOf('<', open);
  const tag = html.slice(start + 1).match(/^[a-z0-9]+/)[0];
  const end = html.indexOf(`</${tag}>`, open) + tag.length + 3;
  return [html.slice(0, start), html.slice(start, end), html.slice(end)];
}

function textOutside(html, region) {
  const root = parse(html);
  root.querySelectorAll(`[data-region="${region}"]`).forEach((e) => e.remove());
  root.querySelectorAll('script,style').forEach((e) => e.remove());
  return norm(root.querySelector('body')?.textContent ?? '');
}

export function diffSite(site, region, golden = GOLDEN) {
  const gdir = path.join(golden, site);
  const files = fs.existsSync(gdir) ? walk(gdir, KEEP) : [];
  const res = {
    site,
    files: files.length,
    added: [],
    unchanged: 0,
    regionOnly: 0,
    outsideChanged: [],
    textChanged: [],
    missing: [],
    regionBytesDelta: 0,
    otherFilesChanged: [],
  };
  for (const g of files) {
    const rel = path.relative(gdir, g);
    const cur = path.join(distDir(site), rel);
    if (!fs.existsSync(cur)) {
      res.missing.push(rel);
      continue;
    }
    const a = stableCids(fs.readFileSync(g, 'utf8'));
    const b = stableCids(fs.readFileSync(cur, 'utf8'));
    if (a === b) {
      res.unchanged++;
      continue;
    }
    if (!rel.endsWith('.html')) {
      res.otherFilesChanged.push(rel);
      continue;
    }
    const [a1, ar, a2] = split(a, region);
    const [b1, br, b2] = split(b, region);
    const outsideSame = a1 === b1 && a2 === b2;
    const textSame = textOutside(a, region) === textOutside(b, region);
    if (!outsideSame) res.outsideChanged.push(rel);
    if (!textSame) res.textChanged.push(rel);
    if (outsideSame && ar !== br) {
      res.regionOnly++;
      res.regionBytesDelta += Buffer.byteLength(br) - Buffer.byteLength(ar);
    }
  }
  // pages that exist in dist but were never approved are a change too
  const known = new Set(files.map((g) => path.relative(gdir, g)));
  if (fs.existsSync(distDir(site)))
    for (const f of walk(distDir(site), KEEP)) {
      const rel = path.relative(distDir(site), f);
      if (!known.has(rel)) res.added.push(rel);
    }
  return res;
}

/** A diff fails when it saw nothing, or anything changed outside the allowed region. */
export function diffFailed(r) {
  return (
    r.files === 0 ||
    r.outsideChanged.length > 0 ||
    r.textChanged.length > 0 ||
    r.missing.length > 0 ||
    r.otherFilesChanged.length > 0 ||
    r.added.length > 0
  );
}

export function summarize(r, region) {
  const changed = r.files - r.unchanged;
  return `${r.site}: ${r.files} files | unchanged ${r.unchanged} | changed ${changed} (only <${region}>: ${r.regionOnly}, outside <${region}>: ${r.outsideChanged.length}, non-HTML: ${r.otherFilesChanged.length}) | content-text diffs: ${r.textChanged.length} | missing ${r.missing.length} | added ${r.added.length}${r.files === 0 ? ' | EMPTY GOLDEN' : ''}`;
}

if (isMain(import.meta.url)) {
  const cmd = process.argv[2];
  const ri = process.argv.indexOf('--region');
  const region = ri > -1 ? process.argv[ri + 1] : 'footer';
  if (cmd === 'snapshot') {
    for (const s of listSites()) console.log(`golden ${s}: saved ${snapshot(s)} files`);
  } else if (cmd === 'diff') {
    let bad = false;
    for (const s of listSites()) {
      const r = diffSite(s, region);
      console.log(summarize(r, region));
      if (diffFailed(r)) bad = true;
    }
    process.exit(bad ? 1 : 0);
  } else {
    console.error('usage: golden.mjs snapshot | diff [--region footer]');
    process.exit(2);
  }
}
