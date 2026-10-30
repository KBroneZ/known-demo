// Internal links + technical SEO hygiene, read from the built HTML:
// broken links/anchors, orphan pages, canonical, unique title/description, noindex, OG tags,
// sitemap <-> pages, robots.txt, NAP consistency, heading order, fictional-demo disclosure.
import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'node-html-parser';
import { loadSiteData } from '../packages/theme/src/lib/load.ts';
import { Report, listSites, siteDir, distDir, htmlFiles, routeOf, isMain } from './lib.mjs';

const PHONE = /\(\d{3}\) \d{3}-\d{4}/g;

export function checkLinks(site) {
  const rep = new Report(`links+seo ${site}`);
  const { clinic } = loadSiteData(siteDir(site));
  const base = clinic.website.replace(/\/$/, '');
  const files = htmlFiles(site);
  const pages = new Map(); // route -> {root, ids}
  for (const f of files) {
    const root = parse(fs.readFileSync(f, 'utf8'));
    const ids = new Set(root.querySelectorAll('[id]').map((e) => e.getAttribute('id')));
    pages.set(routeOf(site, f), { root, ids });
  }
  const assetExists = (p) => fs.existsSync(path.join(distDir(site), p.replace(/^\//, '')));
  const inbound = new Map([...pages.keys()].map((r) => [r, new Set()]));
  let internal = 0;
  let external = 0;

  const titles = new Map();
  const descs = new Map();
  for (const [route, { root }] of pages) {
    // ---- links
    for (const a of root.querySelectorAll('a[href]')) {
      const href = a.getAttribute('href');
      if (/^(mailto:|tel:)/.test(href)) continue;
      const insecureBase = base.replace(/^https:/, 'http:');
      const ownHttp = href.startsWith(insecureBase);
      rep.ok(!ownHttp, `${route}: insecure http:// link to the site's own host: ${href}`);
      if (/^https?:\/\//.test(href) && !href.startsWith(base) && !ownHttp) {
        external++;
        continue;
      }
      internal++;
      const local = href.replace(base, '').replace(insecureBase, '');
      // a bare #fragment refers to the current page; other relative links resolve against the page's own folder
      const url = new URL(
        local.startsWith('#') ? route + local : local,
        'https://x.test' + (route === '/' ? '/' : route.replace(/[^/]*$/, '')),
      );
      let target = url.pathname.length > 1 ? url.pathname.replace(/\/$/, '') : '/';
      const hash = url.hash.slice(1);
      if (pages.has(target)) {
        if (hash) rep.ok(pages.get(target).ids.has(hash), `${route}: anchor #${hash} missing on ${target}`);
        if (target !== route && a.closest('main')) inbound.get(target).add(route);
      } else {
        rep.ok(assetExists(target), `${route}: broken internal link ${href}`);
      }
    }
    // ---- head hygiene
    const title = root.querySelector('title')?.textContent.trim();
    const desc = root.querySelector('meta[name="description"]')?.getAttribute('content');
    rep.ok(!!title && title.length <= 100, `${route}: title missing or > 100 chars`);
    rep.ok(
      !!desc && desc.length >= 50 && desc.length <= 175,
      `${route}: description missing or outside 50-175 chars (${desc?.length})`,
    );
    if (title) titles.set(title, [...(titles.get(title) ?? []), route]);
    if (desc) descs.set(desc, [...(descs.get(desc) ?? []), route]);
    const canon = root.querySelectorAll('link[rel="canonical"]');
    rep.ok(canon.length === 1, `${route}: ${canon.length} canonical tags`);
    rep.ok(
      canon[0]?.getAttribute('href') === base + (route === '/' ? '/' : route),
      `${route}: canonical is not self-referential absolute URL`,
    );
    const robots = root.querySelector('meta[name="robots"]')?.getAttribute('content') ?? '';
    rep.ok(!/noindex/i.test(robots), `${route}: noindex present`);
    for (const p of ['og:title', 'og:type', 'og:image', 'og:url', 'og:description', 'og:locale']) {
      rep.ok(!!root.querySelector(`meta[property="${p}"]`)?.getAttribute('content'), `${route}: missing ${p}`);
    }
    rep.ok(
      root.querySelector('meta[property="og:url"]')?.getAttribute('content') === canon[0]?.getAttribute('href'),
      `${route}: og:url != canonical`,
    );
    rep.ok(root.querySelector('html')?.getAttribute('lang') === 'en', `${route}: missing html lang`);
    // ---- structure
    const h1 = root.querySelectorAll('h1');
    rep.ok(h1.length === 1, `${route}: ${h1.length} h1 elements`);
    let prev = 0;
    for (const h of root.querySelectorAll('h1,h2,h3,h4')) {
      const lvl = Number(h.tagName[1]);
      rep.ok(
        prev === 0 || lvl <= prev + 1,
        `${route}: heading jumps h${prev} -> h${lvl} ("${h.textContent.trim().slice(0, 40)}")`,
      );
      prev = lvl;
    }
    for (const img of root.querySelectorAll('img')) rep.ok(img.hasAttribute('alt'), `${route}: <img> without alt`);
    // ---- text sanity
    const text = root.querySelector('body').textContent;
    rep.ok(!/undefined|\[object|NaN|{{/.test(text), `${route}: leaked template value (undefined/[object]/NaN)`);
    const phones = new Set(text.match(PHONE) ?? []);
    rep.ok(
      [...phones].every((p) => p === clinic.nap.phone),
      `${route}: phone numbers other than clinic.yaml: ${[...phones].join(', ')}`,
    );
    rep.ok(
      /fictional demo/i.test(root.querySelector('footer')?.textContent ?? ''),
      `${route}: footer lacks the fictional-demo note`,
    );
  }
  for (const [t, rs] of titles) rep.ok(rs.length === 1, `duplicate <title> "${t}" on ${rs.join(', ')}`);
  for (const [d, rs] of descs) rep.ok(rs.length === 1, `duplicate meta description on ${rs.join(', ')}`);
  // ---- orphans: every page needs an inbound link from another page's <main>
  for (const [route, from] of inbound)
    if (route !== '/') rep.ok(from.size > 0, `orphan page (no inbound link from any <main>): ${route}`);

  // ---- sitemap
  const sm = fs.readFileSync(path.join(distDir(site), 'sitemap.xml'), 'utf8');
  const urls = [...sm.matchAll(/<loc>([^<]+)<\/loc><lastmod>([^<]+)<\/lastmod>/g)].map((m) => ({
    loc: m[1],
    lastmod: m[2],
  }));
  rep.ok(urls.length === pages.size, `sitemap lists ${urls.length} URLs but dist has ${pages.size} pages`);
  for (const u of urls) {
    const r = u.loc.replace(base, '') || '/';
    rep.ok(pages.has(r), `sitemap URL has no page: ${u.loc}`);
    rep.ok(/^\d{4}-\d{2}-\d{2}$/.test(u.lastmod), `sitemap lastmod malformed for ${u.loc}`);
  }
  rep.ok(!/priority|changefreq/.test(sm), 'sitemap contains priority/changefreq');
  const robots = fs.readFileSync(path.join(distDir(site), 'robots.txt'), 'utf8');
  rep.ok(robots.includes(`Sitemap: ${base}/sitemap.xml`), 'robots.txt lacks Sitemap line');
  rep.ok(!/^Disallow: \/\s*$/m.test(robots.split(/User-agent: (?!\*)/)[0]), 'robots.txt blocks everyone');
  rep.ok(
    /OAI-SearchBot[\s\S]*?Allow: \//.test(robots) && /Claude-SearchBot/.test(robots),
    'robots.txt does not allow AI search bots',
  );
  rep.ok(fs.existsSync(path.join(distDir(site), 'llms.txt')), 'llms.txt missing');
  if (clinic.pages) {
    const want = [...clinic.pages].sort().join('\n');
    const have = [...pages.keys()].sort().join('\n');
    rep.ok(
      want === have,
      `routes differ from clinic.yaml "pages" contract.\n     contract: ${want.replace(/\n/g, ' ')}\n     built:    ${have.replace(/\n/g, ' ')}`,
    );
  }
  const ok = rep.finish(`${pages.size} pages, ${internal} internal links, ${external} external (not fetched)`);
  return {
    ok,
    pages: pages.size,
    internalLinks: internal,
    externalLinks: external,
    checks: rep.checks,
    failures: rep.failures,
  };
}

if (isMain(import.meta.url)) {
  const all = listSites().map((s) => checkLinks(s));
  process.exit(all.every((r) => r.ok) ? 0 : 1);
}
