// Builds every site and records wall-clock build time per site in reports/build.json.
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { WEB_ROOT, listSites, siteDir, distDir, htmlFiles, walk, isMain } from './lib.mjs';

const ASTRO_BIN = path.join(WEB_ROOT, 'node_modules/astro/bin/astro.mjs');

export function buildSite(id) {
  const t0 = performance.now();
  // no shell: run the astro CLI with the current node binary (works on Windows, macOS and Linux)
  const r = spawnSync(process.execPath, [ASTRO_BIN, 'build'], { cwd: siteDir(id), encoding: 'utf8' });
  if (r.error) throw new Error(`could not start astro for ${id}: ${r.error.message}`);
  const seconds = (performance.now() - t0) / 1000;
  if (r.status !== 0 || !fs.existsSync(path.join(distDir(id), 'index.html'))) {
    console.error(r.stdout + r.stderr);
    throw new Error(`build failed for ${id}`);
  }
  const m = (r.stdout + r.stderr).replace(/\u001b\[[0-9;]*m/g, '').match(/page\(s\) built in ([\d.]+)(ms|s)/);
  const astroSeconds = m ? Number(m[1]) / (m[2] === 'ms' ? 1000 : 1) : null;
  const pages = htmlFiles(id).length;
  const files = walk(distDir(id)).length;
  return { site: id, seconds: Number(seconds.toFixed(2)), astroSeconds, htmlPages: pages, files };
}

if (isMain(import.meta.url)) {
  const results = listSites().map((id) => {
    const r = buildSite(id);
    console.log(
      `built ${r.site}: ${r.htmlPages} pages, ${r.files} files, ${r.seconds}s wall (incl. node/astro startup), astro reports ${r.astroSeconds}s for pages`,
    );
    return r;
  });
  fs.mkdirSync(path.join(WEB_ROOT, 'reports'), { recursive: true });
  fs.writeFileSync(path.join(WEB_ROOT, 'reports', 'build.json'), JSON.stringify(results, null, 2));
}
