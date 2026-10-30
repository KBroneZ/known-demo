import type { APIRoute } from 'astro';
import { clinic, theme } from '../lib/site.ts';

export const GET: APIRoute = () => {
  const esc = (s: string): string => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const initials = esc(
    clinic.name
      .split(/\s+/)
      .slice(0, 2)
      .map((w) => w[0])
      .join(''),
  );
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="${theme.colors.primary}"/><text x="32" y="42" font-family="Arial,sans-serif" font-size="28" font-weight="700" text-anchor="middle" fill="${theme.colors.primaryContrast}">${initials}</text></svg>`;
  return new Response(svg, { headers: { 'Content-Type': 'image/svg+xml' } });
};
