// Add a client: clinic.yaml in, compiling website out.
//   node tools/add-client.mjs path/to/clinic.yaml [--theme theme.json] [--posts dir] [--build] [--force]
// 1. validates clinic.yaml with the Zod schema (stops with readable errors)
// 2. scaffolds sites/<id>/ (5 tiny config files + the data) - no page code is copied
// 3. theme.json: yours, or a palette derived from the clinic id (contrast-checked)
// 4. with --build: builds the site and runs the JSON-LD and link/SEO checks on it
import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'yaml';
import { ClinicSchema, ThemeSchema, PostSchema, formatIssues } from '@demo/schema';
import { siteDir, WEB_ROOT } from './lib.mjs';

const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n) => (args.includes(n) ? args[args.indexOf(n) + 1] : undefined);
const src = args.find((a, i) => !a.startsWith('--') && !['--theme', '--posts'].includes(args[i - 1]));
if (!src) {
  console.error(
    'usage: node tools/add-client.mjs <clinic.yaml> [--theme theme.json] [--posts dir] [--build] [--force]',
  );
  process.exit(2);
}

// ---- 1. validate
const parsed = ClinicSchema.safeParse(parse(fs.readFileSync(src, 'utf8')));
if (!parsed.success) {
  console.error(`clinic.yaml is not valid:\n${formatIssues(parsed.error, src)}`);
  process.exit(1);
}
const clinic = parsed.data;
const dir = siteDir(clinic.id);
if (fs.existsSync(dir) && !flag('--force')) {
  console.error(`sites/${clinic.id} already exists (use --force to overwrite)`);
  process.exit(1);
}

// ---- 3. theme (derived palette when none given)
function hslHex(h, s, l) {
  s /= 100;
  l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => Math.round(255 * (l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))));
  return '#' + [f(0), f(8), f(4)].map((x) => x.toString(16).padStart(2, '0')).join('');
}
function derivedTheme(id) {
  const hue = [...id].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
  return {
    colors: {
      primary: hslHex(hue, 55, 26),
      primaryContrast: '#ffffff',
      accent: hslHex((hue + 150) % 360, 60, 38),
      bg: '#ffffff',
      surface: hslHex(hue, 35, 96),
      text: hslHex(hue, 30, 12),
      muted: hslHex(hue, 15, 33),
      border: hslHex(hue, 25, 85),
    },
    fonts: {
      heading: "Georgia, 'Times New Roman', serif",
      body: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
    },
    radius: '8px',
  };
}
const theme = opt('--theme') ? JSON.parse(fs.readFileSync(opt('--theme'), 'utf8')) : derivedTheme(clinic.id);
const themeCheck = ThemeSchema.safeParse(theme);
if (!themeCheck.success) {
  console.error(`theme.json is not valid:\n${formatIssues(themeCheck.error, 'theme.json')}`);
  process.exit(1);
}

// ---- posts are validated before anything is written, so a bad post cannot leave a half-built site folder
const postFiles = opt('--posts') ? fs.readdirSync(opt('--posts')).filter((x) => x.endsWith('.md')) : [];
const names = new Set(clinic.dentists.map((d) => d.name));
const services = new Set(clinic.services.map((x) => x.slug).filter(Boolean));
const postProblems = [];
for (const f of postFiles) {
  const raw = fs.readFileSync(path.join(opt('--posts'), f), 'utf8').replace(/\r\n/g, '\n');
  const m = raw.match(/^---\n([\s\S]*?)\n---/);
  if (!m) {
    postProblems.push(`  ${f}: no frontmatter block`);
    continue;
  }
  const fm = PostSchema.safeParse(parse(m[1]));
  if (!fm.success) {
    postProblems.push(formatIssues(fm.error, f));
    continue;
  }
  if (!names.has(fm.data.author))
    postProblems.push(`  ${f}: author "${fm.data.author}" is not a dentist in clinic.yaml`);
  if (fm.data.service && !services.has(fm.data.service))
    postProblems.push(`  ${f}: service "${fm.data.service}" has no page in clinic.yaml`);
}
if (postProblems.length) {
  console.error(`posts are not valid:\n${postProblems.join('\n')}`);
  process.exit(1);
}

// ---- 2. scaffold
if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true }); // only reachable with --force: start clean, no stale posts or dist
const write = (rel, text) => {
  const p = path.join(dir, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, text);
};
write(
  'package.json',
  JSON.stringify(
    {
      name: `@demo/site-${clinic.id}`,
      version: '0.1.0',
      private: true,
      type: 'module',
      scripts: { dev: 'astro dev', build: 'astro build' },
      dependencies: { '@demo/schema': '*', '@demo/theme': '*', astro: '7.4.4' },
    },
    null,
    2,
  ) + '\n',
);
write(
  'astro.config.mjs',
  "import { defineConfig } from 'astro/config';\nimport clinicSite from '@demo/theme';\n\nexport default defineConfig({ integrations: [clinicSite()] });\n",
);
write('src/content.config.ts', "export { collections } from '@demo/theme/content';\n");
write(
  'tsconfig.json',
  '{ "extends": "astro/tsconfigs/strict", "include": [".astro/types.d.ts", "**/*"], "exclude": ["dist"] }\n',
);
fs.copyFileSync(src, path.join(dir, 'clinic.yaml'));
write('theme.json', JSON.stringify(theme, null, 2) + '\n');
fs.mkdirSync(path.join(dir, 'src/content/posts'), { recursive: true });
let posts = 0;
if (opt('--posts')) {
  for (const f of postFiles) {
    fs.copyFileSync(path.join(opt('--posts'), f), path.join(dir, 'src/content/posts', f));
    posts++;
  }
} else {
  write('src/content/posts/.gitkeep', '');
}
console.log(`scaffolded sites/${clinic.id} (${posts} posts, ${opt('--theme') ? 'given' : 'derived'} theme)`);

// ---- 4. build + checks
if (flag('--build')) {
  const { buildSite } = await import('./build-all.mjs');
  const { checkJsonLd } = await import('./check-jsonld.mjs');
  const { checkLinks } = await import('./check-links.mjs');
  const { checkWeight } = await import('./check-weight.mjs');
  const t0 = performance.now();
  const b = buildSite(clinic.id);
  console.log(`built ${clinic.id}: ${b.htmlPages} pages in ${b.seconds}s`);
  const results = [checkJsonLd(clinic.id), checkLinks(clinic.id), checkWeight(clinic.id)];
  console.log(`total (scaffold excluded) ${((performance.now() - t0) / 1000).toFixed(1)}s`);
  const total = Number((performance.now() / 1000).toFixed(2)); // whole process: validation + scaffold + build + gates
  fs.mkdirSync(path.join(WEB_ROOT, 'reports'), { recursive: true });
  fs.writeFileSync(
    path.join(WEB_ROOT, 'reports', 'add-client.json'),
    JSON.stringify(
      {
        at: new Date().toISOString(),
        site: clinic.id,
        pages: b.htmlPages,
        posts,
        buildSeconds: b.seconds,
        totalSeconds: total,
        gatesPassed: results.every((r) => r.ok),
      },
      null,
      2,
    ),
  );
  console.log(`whole add-client run (validate, scaffold, build, 3 gates): ${total}s`);
  if (!results.every((r) => r.ok)) process.exit(1);
}
console.log(
  `next: npm install (registers the new workspace in the lockfile), then npm run build -w @demo/site-${clinic.id}`,
);
