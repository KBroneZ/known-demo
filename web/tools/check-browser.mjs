// Real-browser checks on the built sites, all local (no account, nothing leaves the machine):
//  - axe-core (WCAG 2.x A/AA rules incl. color contrast) at desktop and 375px mobile widths
//  - horizontal overflow at 375px
//  - lab LCP and CLS from PerformanceObserver (headless Chrome/Edge, no throttling: indicative only)
// Uses puppeteer-core with the Chrome or Edge already installed; nothing is downloaded.
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { createRequire } from 'node:module';
import puppeteer from 'puppeteer-core';
import { Report, listSites, distDir, htmlFiles, routeOf, WEB_ROOT, isMain } from './lib.mjs';

const require = createRequire(import.meta.url);
const AXE_SRC = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const BROWSERS = [
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  '/usr/bin/google-chrome',
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
];
const TYPES = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.xml': 'application/xml',
  '.txt': 'text/plain',
};

function serve(root) {
  const server = http.createServer((req, res) => {
    let p;
    try {
      p = decodeURIComponent(new URL(req.url, 'http://x').pathname);
    } catch {
      res.writeHead(400);
      return res.end('bad request');
    }
    if (p === '/') p = '/index.html';
    else if (!path.extname(p)) p += '.html';
    const f = path.join(root, p);
    if (
      (!(f + path.sep).startsWith(root + path.sep) && f !== root) ||
      !fs.existsSync(f) ||
      fs.statSync(f).isDirectory()
    ) {
      res.writeHead(404);
      return res.end('not found');
    }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] ?? 'application/octet-stream' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise((r) => server.listen(0, '127.0.0.1', () => r(server)));
}

const VITALS = `(() => { window.__v = { cls: 0, lcp: 0 };
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__v.cls += e.value; }).observe({ type: 'layout-shift', buffered: true });
  new PerformanceObserver(l => { for (const e of l.getEntries()) window.__v.lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true }); })()`;

// Runs in the page: width overflow plus the element that sticks out furthest, so a failure names its cause.
function overflowProbe() {
  const vw = window.innerWidth;
  let culprit = 'none';
  let worst = 0;
  for (const el of document.body.querySelectorAll('*')) {
    const over = el.getBoundingClientRect().right - vw;
    if (over > 0 && over >= worst) {
      worst = over;
      const cls = typeof el.className === 'string' && el.className ? '.' + el.className.trim().split(/\s+/)[0] : '';
      culprit = `${el.tagName.toLowerCase()}${cls} "${(el.textContent || '').trim().slice(0, 40)}"`;
    }
  }
  return { ...window.__v, overflow: document.documentElement.scrollWidth - vw, culprit };
}

export async function checkBrowser(sites) {
  const exe = BROWSERS.find((b) => fs.existsSync(b));
  if (!exe) throw new Error('no local Chrome/Edge found for puppeteer-core');
  // GitHub's Ubuntu runners block Chrome's user-namespace sandbox, so CI launches without it.
  const args = process.env.CI ? ['--no-sandbox'] : [];
  const browser = await puppeteer.launch({ executablePath: exe, headless: true, args });
  const results = [];
  try {
    for (const site of sites) {
      const rep = new Report(`browser ${site}`);
      const server = await serve(distDir(site));
      const origin = `http://127.0.0.1:${server.address().port}`;
      const vitals = [];
      let violations = 0;
      let axeRuns = 0;
      for (const file of htmlFiles(site)) {
        const route = routeOf(site, file);
        for (const [label, width] of [
          ['desktop', 1280],
          ['mobile', 375],
        ]) {
          const page = await browser.newPage();
          await page.setViewport({ width, height: 900, deviceScaleFactor: 1 });
          await page.evaluateOnNewDocument(VITALS);
          await page.goto(origin + route, { waitUntil: 'load' });
          await new Promise((r) => setTimeout(r, 150));
          await page.evaluate(AXE_SRC);
          const axe = await page.evaluate(() =>
            axe
              .run(document, {
                runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'] },
              })
              .then((r) => ({
                violations: r.violations.map((v) => ({
                  id: v.id,
                  impact: v.impact,
                  nodes: v.nodes.length,
                  sample: v.nodes[0]?.target?.join(' '),
                })),
                passes: r.passes.length,
              })),
          );
          axeRuns++;
          for (const v of axe.violations) {
            violations += v.nodes;
            rep.ok(false, `${route} [${label}]: axe ${v.id} (${v.impact}) x${v.nodes}, e.g. ${v.sample}`);
          }
          const m = await page.evaluate(overflowProbe);
          if (label === 'mobile')
            rep.ok(m.overflow <= 0, `${route}: horizontal overflow ${m.overflow}px at 375px, widest: ${m.culprit}`);
          if (label === 'desktop') vitals.push({ route, lcp: m.lcp, cls: m.cls });
          await page.close();
        }
      }
      server.close();
      const worstLcp = Math.max(...vitals.map((v) => v.lcp));
      const worstCls = Math.max(...vitals.map((v) => v.cls));
      rep.ok(worstCls <= 0.1, `worst CLS ${worstCls.toFixed(3)} > 0.1`);
      rep.ok(
        vitals.every((v) => v.lcp > 0),
        `no LCP entry recorded on: ${vitals
          .filter((v) => !(v.lcp > 0))
          .map((v) => v.route)
          .join(', ')}`,
      );
      rep.ok(worstLcp <= 2500, `worst lab LCP ${Math.round(worstLcp)} ms > 2500`);
      const ok = rep.finish(
        `${axeRuns} axe runs (desktop+mobile), ${violations} violating nodes, worst lab LCP ${Math.round(worstLcp)} ms, worst CLS ${worstCls.toFixed(3)}`,
      );
      results.push({
        site,
        ok,
        axeRuns,
        violations,
        worstLcpMs: Math.round(worstLcp),
        worstCls: Number(worstCls.toFixed(3)),
        failures: rep.failures,
      });
    }
  } finally {
    await browser.close();
  }
  fs.mkdirSync(path.join(WEB_ROOT, 'reports'), { recursive: true });
  fs.writeFileSync(path.join(WEB_ROOT, 'reports', 'browser.json'), JSON.stringify(results, null, 2));
  return results;
}

if (isMain(import.meta.url)) {
  const r = await checkBrowser(listSites());
  process.exit(r.every((x) => x.ok) ? 0 : 1);
}
