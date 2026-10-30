import type { APIRoute } from 'astro';
import { clinic, routeTable } from '../lib/site.ts';
import { abs } from '../lib/jsonld.ts';

// lastmod is the real content date: post.updated for posts, clinic.yaml `updated` for the rest.
// No priority / changefreq (Google ignores both).
export const GET: APIRoute = async () => {
  const rows = await routeTable();
  const xml =
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    rows.map((r) => `  <url><loc>${abs(clinic, r.path)}</loc><lastmod>${r.lastmod}</lastmod></url>`).join('\n') +
    '\n</urlset>\n';
  return new Response(xml, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
