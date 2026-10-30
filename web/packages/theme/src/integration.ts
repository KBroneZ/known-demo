// Astro integration: a site only supplies data (clinic.yaml, theme.json, posts) and this
// integration injects every route (pages, sitemap, robots, llms.txt, favicon, og image).
// Validation of the data runs here, before any page is rendered: bad data = failed build.
import type { AstroIntegration } from 'astro';
import { fileURLToPath } from 'node:url';
import { loadSiteData } from './lib/load.ts';

const VIRTUAL = 'virtual:clinic-site';
const RESOLVED = '\0' + VIRTUAL;

const page = (p: string): string => fileURLToPath(new URL(`./pages/${p}`, import.meta.url));

const ROUTES: [pattern: string, file: string][] = [
  ['/', 'index.astro'],
  ['/about', 'about.astro'],
  ['/team', 'team.astro'],
  ['/contact', 'contact.astro'],
  ['/faq', 'faq.astro'],
  ['/services', 'services/index.astro'],
  ['/services/[slug]', 'services/[slug].astro'],
  ['/blog', 'blog/index.astro'],
  ['/blog/[slug]', 'blog/[slug].astro'],
  ['/robots.txt', 'robots.txt.ts'],
  ['/sitemap.xml', 'sitemap.xml.ts'],
  ['/llms.txt', 'llms.txt.ts'],
  ['/favicon.svg', 'favicon.svg.ts'],
  ['/og.png', 'og.png.ts'],
];

export default function clinicSite(): AstroIntegration {
  return {
    name: 'clinic-site',
    hooks: {
      'astro:config:setup': ({ config, injectRoute, updateConfig, logger }) => {
        const root = fileURLToPath(config.root);
        const data = loadSiteData(root);
        logger.info(`clinic.yaml + theme.json valid for "${data.clinic.name}"`);
        for (const [pattern, file] of ROUTES) injectRoute({ pattern, entrypoint: page(file), prerender: true });
        updateConfig({
          site: data.clinic.website,
          trailingSlash: 'never',
          build: { format: 'file', inlineStylesheets: 'always' },
          vite: {
            plugins: [
              {
                name: 'clinic-site-data',
                resolveId: (id: string) => (id === VIRTUAL ? RESOLVED : null),
                load: (id: string) => (id === RESOLVED ? `export default ${JSON.stringify(data)};` : null),
              },
            ],
          },
        });
      },
    },
  };
}
