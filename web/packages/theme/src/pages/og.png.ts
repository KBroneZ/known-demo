import type { APIRoute } from 'astro';
import sharp from 'sharp';
import { clinic, theme } from '../lib/site.ts';

const esc = (s: string): string => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

// Default social image, rendered at build time from the theme tokens and clinic name.
export const GET: APIRoute = async () => {
  const c = theme.colors;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
<rect width="1200" height="630" fill="${c.primary}"/>
<rect x="0" y="560" width="1200" height="70" fill="${c.accent}"/>
<text x="80" y="290" font-family="Georgia,serif" font-size="76" font-weight="700" fill="${c.primaryContrast}">${esc(clinic.name)}</text>
<text x="80" y="370" font-family="Arial,sans-serif" font-size="38" fill="${c.primaryContrast}">${esc(clinic.tagline)}</text>
<text x="80" y="605" font-family="Arial,sans-serif" font-size="28" fill="${c.primary}">Fictional demo clinic · ${esc(clinic.nap.city)}, ${esc(clinic.nap.state)}</text>
</svg>`;
  const png = await sharp(Buffer.from(svg)).png({ compressionLevel: 9, palette: true }).toBuffer();
  return new Response(new Uint8Array(png), { headers: { 'Content-Type': 'image/png' } });
};
