// JSON-LD validator: every <script type="application/ld+json"> in dist must parse, use the
// expected types for its page kind, carry the required properties, match clinic.yaml and the
// visible text, and must never contain ratings or reviews.
// Offline approximation of the Rich Results Test; it is not Google's validator.
import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'node-html-parser';
import { loadSiteData } from '../packages/theme/src/lib/load.ts';
import { openingHoursSpec } from '../packages/theme/src/lib/format.ts';
import { Report, listSites, siteDir, htmlFiles, routeOf, isMain } from './lib.mjs';

const REQUIRED = {
  Dentist: ['@id', 'name', 'url', 'telephone', 'address', 'openingHoursSpecification'],
  BreadcrumbList: ['itemListElement'],
  FAQPage: ['mainEntity'],
  BlogPosting: ['headline', 'datePublished', 'dateModified', 'author', 'publisher', 'mainEntityOfPage'],
};
const FORBIDDEN = ['aggregateRating', 'review', 'reviews', 'rating', 'ratingValue', 'award'];

const kindOf = (route) =>
  route === '/'
    ? 'home'
    : route.startsWith('/blog/')
      ? 'post'
      : route.startsWith('/services/')
        ? 'service'
        : route.slice(1);

function expectedTypes(route, clinic, fm) {
  const kind = kindOf(route);
  const t = [];
  if (['home', 'about', 'contact'].includes(kind)) t.push('Dentist');
  if (kind !== 'home') t.push('BreadcrumbList');
  if (kind === 'faq') t.push('FAQPage');
  if (kind === 'service') {
    const svc = clinic.services.find((s) => `/services/${s.slug}` === route);
    if (svc?.faq.length) t.push('FAQPage');
  }
  if (kind === 'post') {
    t.push('BlogPosting');
    if (fm?.faq) t.push('FAQPage');
  }
  return t;
}

function postFaqFlag(site, route) {
  const slug = route.split('/').pop();
  const dir = path.join(siteDir(site), 'src/content/posts');
  for (const f of fs.readdirSync(dir)) {
    const raw = fs.readFileSync(path.join(dir, f), 'utf8');
    if (new RegExp(`^slug:\\s*["']?${slug}["']?\\s*$`, 'm').test(raw)) return { faq: /^faq:/m.test(raw) };
  }
  return null;
}

const walkKeys = (o, fn) => {
  if (Array.isArray(o)) o.forEach((x) => walkKeys(x, fn));
  else if (o && typeof o === 'object') for (const [k, v] of Object.entries(o)) (fn(k, v), walkKeys(v, fn));
};
const norm = (s) => s.replace(/\s+/g, ' ').trim();

export function checkJsonLd(site) {
  const rep = new Report(`jsonld ${site}`);
  const { clinic } = loadSiteData(siteDir(site));
  const today = new Date().toISOString().slice(0, 10);
  let scripts = 0;
  for (const file of htmlFiles(site)) {
    const route = routeOf(site, file);
    const root = parse(fs.readFileSync(file, 'utf8'));
    const bodyText = norm(root.querySelector('body').textContent);
    const blocks = root.querySelectorAll('script[type="application/ld+json"]');
    const found = [];
    for (const b of blocks) {
      scripts++;
      let data;
      try {
        data = JSON.parse(b.textContent);
      } catch (e) {
        rep.ok(false, `${route}: invalid JSON in ld+json (${e.message})`);
        continue;
      }
      rep.ok(data['@context'] === 'https://schema.org', `${route}: missing @context`);
      const type = data['@type'];
      found.push(type);
      for (const prop of REQUIRED[type] ?? []) rep.ok(prop in data, `${route}: ${type} missing "${prop}"`);
      rep.ok(type in REQUIRED, `${route}: unexpected type ${type}`);
      const forbidden = [];
      walkKeys(data, (k) => {
        if (FORBIDDEN.includes(k)) forbidden.push(k);
      });
      rep.ok(forbidden.length === 0, `${route}: forbidden property "${forbidden.join(', ')}" in ${type}`);
      if (type === 'Dentist') {
        const n = clinic.nap;
        rep.ok(data.name === clinic.name, `${route}: Dentist.name != clinic.yaml`);
        rep.ok(data.telephone === n.phone, `${route}: Dentist.telephone != clinic.yaml`);
        rep.ok(
          data.address?.postalCode === n.zip && data.address?.addressLocality === n.city,
          `${route}: Dentist.address != clinic.yaml`,
        );
        rep.ok(/^https:\/\//.test(data.url), `${route}: Dentist.url not absolute https`);
        rep.ok(data.email === n.email, `${route}: Dentist.email != clinic.yaml`);
        const street = n.suite ? `${n.street}, ${n.suite}` : n.street;
        rep.ok(
          data.address?.streetAddress === street && data.address?.addressRegion === n.state,
          `${route}: Dentist street/state != clinic.yaml`,
        );
        // hours: day sets, opens and closes must equal what clinic.yaml says, entry by entry
        rep.ok(
          JSON.stringify(data.openingHoursSpecification) === JSON.stringify(openingHoursSpec(clinic)),
          `${route}: Dentist.openingHoursSpecification != clinic.yaml hours`,
        );
      }
      if (type === 'BreadcrumbList') {
        const items = data.itemListElement;
        rep.ok(
          items.every((it, i) => it.position === i + 1 && it.name && /^https:\/\//.test(it.item)),
          `${route}: BreadcrumbList items malformed`,
        );
        const last = items[items.length - 1]?.item;
        rep.ok(last === clinic.website.replace(/\/$/, '') + route, `${route}: last breadcrumb is not the page itself`);
      }
      if (type === 'FAQPage') {
        rep.ok(data.mainEntity.length > 0, `${route}: FAQPage empty`);
        for (const q of data.mainEntity) {
          rep.ok(
            q['@type'] === 'Question' && q.acceptedAnswer?.['@type'] === 'Answer' && q.acceptedAnswer.text,
            `${route}: malformed Question`,
          );
          // the marked-up Q&A must be visible on the page
          rep.ok(
            bodyText.includes(norm(q.name)) && bodyText.includes(norm(q.acceptedAnswer.text)),
            `${route}: FAQ "${q.name}" not visible in page text`,
          );
        }
      }
      if (type === 'BlogPosting') {
        for (const k of ['datePublished', 'dateModified']) {
          rep.ok(/^\d{4}-\d{2}-\d{2}$/.test(data[k]) && data[k] <= today, `${route}: ${k} invalid or in the future`);
        }
        rep.ok(data.dateModified >= data.datePublished, `${route}: dateModified before datePublished`);
        rep.ok(
          data.author?.['@type'] === 'Person' && clinic.dentists.some((d) => d.name === data.author.name),
          `${route}: author not a dentist in clinic.yaml`,
        );
        // visible dates must match markup dates (Google requirement)
        const times = root.querySelectorAll('time').map((t) => t.getAttribute('datetime'));
        rep.ok(
          times.includes(data.datePublished) && times.includes(data.dateModified),
          `${route}: visible <time> does not match JSON-LD dates`,
        );
        rep.ok(root.querySelector('h1')?.textContent.trim() === data.headline, `${route}: headline != visible h1`);
      }
    }
    const fm = kindOf(route) === 'post' ? postFaqFlag(site, route) : null;
    for (const t of expectedTypes(route, clinic, fm))
      rep.ok(found.includes(t), `${route}: expected ${t} not found (has ${found.join(', ') || 'none'})`);
  }
  const ok = rep.finish(`${scripts} ld+json blocks`);
  return { ok, scripts, checks: rep.checks, failures: rep.failures };
}

if (isMain(import.meta.url)) {
  const all = listSites().map((s) => checkJsonLd(s));
  process.exit(all.every((r) => r.ok) ? 0 : 1);
}
