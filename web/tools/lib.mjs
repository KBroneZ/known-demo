// Shared helpers for the tools/ scripts: find sites, walk dist folders, tiny logger.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const WEB_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const SITES_DIR = path.join(WEB_ROOT, 'sites');

/** True when `metaUrl` (import.meta.url) is the script node was started with. Works on POSIX, Windows and paths with spaces. */
export function isMain(metaUrl) {
  return !!process.argv[1] && metaUrl === pathToFileURL(path.resolve(process.argv[1])).href;
}

/**
 * Site ids (folder names under sites/). `--site a,b` or env SITES narrows the list.
 * Throws on an unknown site, a bare `--site`, or an empty result: a gate must never run on nothing.
 */
export function listSites(argv = process.argv, env = process.env, sitesDir = SITES_DIR) {
  const all = fs
    .readdirSync(sitesDir, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort();
  const i = argv.indexOf('--site');
  let wanted = null;
  if (i > -1) {
    const v = argv[i + 1];
    if (!v || v.startsWith('--')) throw new Error('--site needs a comma-separated list of site ids');
    wanted = v.split(',');
  } else if (env.SITES) wanted = env.SITES.split(',');
  if (wanted) {
    const unknown = wanted.filter((w) => !all.includes(w));
    if (unknown.length)
      throw new Error(`unknown site(s): ${unknown.join(', ')}. Available: ${all.join(', ') || '(none)'}`);
    all.splice(0, all.length, ...all.filter((s) => wanted.includes(s)));
  }
  if (all.length === 0) throw new Error(`no sites found under ${sitesDir}`);
  return all;
}

export const siteDir = (id) => path.join(SITES_DIR, id);
export const distDir = (id) => path.join(SITES_DIR, id, 'dist');

export function walk(dir, filter = () => true) {
  const out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(p, filter));
    else if (filter(p)) out.push(p);
  }
  return out.sort();
}

export const htmlFiles = (id) => walk(distDir(id), (p) => p.endsWith('.html'));

/** dist file -> URL path ("/blog/x.html" -> "/blog/x", "/index.html" -> "/") */
export function routeOf(id, file) {
  const rel = '/' + path.relative(distDir(id), file).split(path.sep).join('/');
  if (rel === '/index.html') return '/';
  return rel.replace(/\.html$/, '');
}

export function ms(start) {
  return Math.round(performance.now() - start);
}

/**
 * Collects real assertions. A report with zero checks FAILS: a gate that examined nothing proves nothing.
 * Only call ok() for a condition that could genuinely be false; do not record trivial passes.
 */
export class Report {
  constructor(name) {
    this.name = name;
    this.failures = [];
    this.checks = 0;
  }
  ok(cond, msg) {
    this.checks++;
    if (!cond) this.failures.push(msg);
    return cond;
  }
  finish(extra = '') {
    if (this.checks === 0) this.failures.push('0 checks ran (nothing was examined)');
    const status = this.failures.length ? 'FAIL' : 'PASS';
    console.log(
      `[${status}] ${this.name}: ${this.checks} checks, ${this.failures.length} failures${extra ? ' | ' + extra : ''}`,
    );
    for (const f of this.failures.slice(0, 25)) console.log('   - ' + f);
    if (this.failures.length > 25) console.log(`   ... ${this.failures.length - 25} more`);
    return this.failures.length === 0;
  }
}
