// Page weight from dist: HTML (raw + gzip + brotli), plus the assets a page actually references
// (inline CSS is already inside the HTML; there is no JS and no web font). Budget: 100 KB gzip HTML per page.
import fs from 'node:fs';
import zlib from 'node:zlib';
import { parse } from 'node-html-parser';
import { Report, listSites, distDir, htmlFiles, routeOf, isMain } from './lib.mjs';

const BUDGET_GZIP = 100 * 1024;
const kb = (n) => (n / 1024).toFixed(1);

export function checkWeight(site) {
  const rep = new Report(`weight ${site}`);
  const rows = [];
  if (htmlFiles(site).length === 0) {
    rep.ok(false, 'no built HTML pages found');
    return { ok: rep.finish(), summary: null, rows, checks: rep.checks, failures: rep.failures };
  }
  for (const f of htmlFiles(site)) {
    const html = fs.readFileSync(f);
    const root = parse(html.toString('utf8'));
    const gzip = zlib.gzipSync(html, { level: 9 }).length;
    const br = zlib.brotliCompressSync(html).length;
    // external requests the page makes (same-origin only; none are expected beyond favicon)
    const refs = [...root.querySelectorAll('link[href],script[src],img[src]')]
      .map((e) => e.getAttribute('href') ?? e.getAttribute('src'))
      .filter((u) => u && u.startsWith('/') && !/^\/\//.test(u));
    const refBytes = refs.reduce((s, u) => {
      const p = distDir(site) + u;
      return s + (fs.existsSync(p) ? fs.statSync(p).size : 0);
    }, 0);
    const scripts = root.querySelectorAll('script:not([type="application/ld+json"])').length;
    rep.ok(gzip <= BUDGET_GZIP, `${routeOf(site, f)}: ${kb(gzip)} KB gzip over budget`);
    rep.ok(scripts === 0, `${routeOf(site, f)}: ${scripts} JavaScript <script> tags (expected 0)`);
    rows.push({
      route: routeOf(site, f),
      htmlRaw: html.length,
      htmlGzip: gzip,
      htmlBrotli: br,
      requests: 1 + refs.length,
      totalRawWithRefs: html.length + refBytes,
    });
  }
  const sum = (k) => rows.reduce((s, r) => s + r[k], 0);
  const max = rows.reduce((a, r) => (r.htmlGzip > a.htmlGzip ? r : a));
  const summary = {
    pages: rows.length,
    avgHtmlRaw: Math.round(sum('htmlRaw') / rows.length),
    avgHtmlGzip: Math.round(sum('htmlGzip') / rows.length),
    avgHtmlBrotli: Math.round(sum('htmlBrotli') / rows.length),
    maxHtmlGzip: max.htmlGzip,
    maxRoute: max.route,
    avgTotalRawWithRefs: Math.round(sum('totalRawWithRefs') / rows.length),
    avgRequests: Number((sum('requests') / rows.length).toFixed(1)),
    ogImageBytes: fs.statSync(distDir(site) + '/og.png').size,
  };
  const ok = rep.finish(
    `avg ${kb(summary.avgHtmlRaw)} KB raw / ${kb(summary.avgHtmlGzip)} KB gzip / ${kb(summary.avgHtmlBrotli)} KB br, max ${kb(summary.maxHtmlGzip)} KB gzip (${summary.maxRoute}), ${summary.avgRequests} requests/page`,
  );
  return { ok, summary, rows, checks: rep.checks, failures: rep.failures };
}

if (isMain(import.meta.url)) {
  const all = listSites().map((s) => checkWeight(s));
  process.exit(all.every((r) => r.ok) ? 0 : 1);
}
