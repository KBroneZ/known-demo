import { defineConfig } from 'astro/config';
import clinicSite from '@demo/theme';

// Everything else (site URL, routes, sitemap, robots, llms.txt) comes from clinic.yaml via the theme.
export default defineConfig({ integrations: [clinicSite()] });
