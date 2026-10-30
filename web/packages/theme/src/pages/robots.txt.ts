import type { APIRoute } from 'astro';
import { clinic } from '../lib/site.ts';
import { abs } from '../lib/jsonld.ts';

// Search/answer-engine bots are always allowed (the clinic wants to be cited).
// Training-only crawlers follow clinic.yaml -> seo.allow_ai_training.
const SEARCH_BOTS = [
  'Googlebot',
  'Bingbot',
  'OAI-SearchBot',
  'ChatGPT-User',
  'PerplexityBot',
  'Claude-SearchBot',
  'Claude-User',
];
const TRAINING_BOTS = ['GPTBot', 'ClaudeBot', 'Google-Extended', 'CCBot'];

export const GET: APIRoute = () => {
  const lines = ['User-agent: *', 'Allow: /', ''];
  for (const bot of SEARCH_BOTS) lines.push(`User-agent: ${bot}`, 'Allow: /', '');
  if (!clinic.seo.allow_ai_training)
    for (const bot of TRAINING_BOTS) lines.push(`User-agent: ${bot}`, 'Disallow: /', '');
  lines.push(`Sitemap: ${abs(clinic, '/sitemap.xml')}`, '');
  return new Response(lines.join('\n'), { headers: { 'Content-Type': 'text/plain; charset=utf-8' } });
};
