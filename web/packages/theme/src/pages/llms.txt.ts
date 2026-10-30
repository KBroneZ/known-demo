import type { APIRoute } from 'astro';
import { clinic, routeTable } from '../lib/site.ts';
import { abs } from '../lib/jsonld.ts';
import { addressLine, hoursSentence, endSentence } from '../lib/format.ts';

// A Markdown index of the key pages. Cheap to generate; no ranking benefit is assumed.
export const GET: APIRoute = async () => {
  const rows = await routeTable();
  const section = (title: string, kinds: string[]): string => {
    const items = rows.filter((r) => kinds.includes(r.kind));
    return items.length
      ? `## ${title}\n${items.map((r) => `- [${r.name}](${abs(clinic, r.path)}): ${r.description}`).join('\n')}\n`
      : '';
  };
  const body = [
    `# ${clinic.name}`,
    `> ${clinic.description}`,
    '',
    'This is a fictional demo clinic. It is not a real practice.',
    '',
    `Address: ${addressLine(clinic)}. Phone: ${clinic.nap.phone}. Open ${endSentence(hoursSentence(clinic))}`,
    '',
    section('Main pages', ['home', 'about', 'team', 'contact', 'faq']),
    section('Services', ['services', 'service']),
    section('Blog', ['blog', 'post']),
  ].join('\n');
  return new Response(body, { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
