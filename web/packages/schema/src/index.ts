// Single source of truth for everything a site is made of:
//   clinic.yaml  -> ClinicSchema
//   theme.json   -> ThemeSchema
//   posts/*.md   -> PostSchema (frontmatter)
// Written in plain TS (no enums, no parameter properties) so Node can import it
// directly through type stripping, from build tools as well as from Astro.
import { z } from 'zod';

const kebab = z.string().regex(/^[a-z0-9]+(-[a-z0-9]+)*$/, 'must be kebab-case (a-z, 0-9, dashes)');
const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'must be YYYY-MM-DD');
const time = z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'must be HH:MM (24h)');

export const DAYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'] as const;

const QA = z.strictObject({
  question: z.string().min(8),
  answer: z.string().min(20),
});

const Service = z.strictObject({
  name: z.string().min(3),
  aliases: z.array(z.string()).default([]),
  // A service with a slug gets its own page. Without one it is only listed.
  slug: kebab.optional(),
  summary: z.string().min(40).max(200).optional(),
  body: z.array(z.string().min(40)).optional(),
  faq: z.array(QA).default([]),
  price_key: z.string().optional(),
  lead_dentist: z.string().optional(),
});

export const ClinicSchema = z
  .strictObject({
    id: kebab,
    // Guard rail: the demo may only ever contain invented clinics.
    fictional: z.literal(true, { error: 'demo clinics must set fictional: true' }),
    name: z.string().min(3),
    tagline: z.string().min(10).max(90),
    description: z.string().min(60).max(220),
    website: z.url().refine((u) => new URL(u).protocol === 'https:' && new URL(u).hostname.endsWith('.example'), {
      error: 'website must be https and use the reserved .example TLD',
    }),
    updated: isoDate,
    nap: z.strictObject({
      phone: z.string().regex(/^\(\d{3}\) 555-01\d{2}$/, 'must be a fictional 555-01xx number'),
      email: z.email(),
      street: z.string(),
      suite: z.string().optional(),
      city: z.string(),
      state: z.string().length(2),
      zip: z.string().regex(/^\d{5}$/),
    }),
    geo: z.strictObject({ lat: z.number().min(-90).max(90), lng: z.number().min(-180).max(180) }).optional(),
    about: z.strictObject({
      headline: z.string(),
      paragraphs: z.array(z.string().min(40)).min(1),
    }),
    dentists: z
      .array(
        z.strictObject({
          name: z.string(),
          credentials: z.string(),
          focus: z.string(),
          bio: z.string().min(40).optional(),
        }),
      )
      .min(1),
    hours: z.array(z.strictObject({ days: z.array(z.enum(DAYS)).min(1), open: time, close: time })),
    emergency_line: z.string().optional(),
    services: z.array(Service).min(1),
    prices: z.record(z.string(), z.string()).default({}),
    insurance_accepted: z.array(z.string()).default([]),
    testimonials_on_file: z.array(z.unknown()).max(0, 'no testimonials may be invented').default([]),
    awards: z.array(z.unknown()).max(0, 'no awards may be invented').default([]),
    faq: z.array(QA).default([]),
    seo: z
      .strictObject({
        allow_ai_training: z.boolean().default(false),
        same_as: z.array(z.url()).default([]),
      })
      .default({ allow_ai_training: false, same_as: [] }),
    home_variant: z.enum(['split', 'centered']).default('split'),
    // Optional contract used by the QA gate: the exact set of routes the site must expose.
    pages: z.array(z.string()).optional(),
  })
  .superRefine((c, ctx) => {
    const names = new Set(c.dentists.map((d) => d.name));
    const slugs = new Set<string>();
    c.services.forEach((s, i) => {
      if (s.slug) {
        if (slugs.has(s.slug))
          ctx.addIssue({ code: 'custom', path: ['services', i, 'slug'], message: 'duplicate service slug' });
        slugs.add(s.slug);
        if (!s.summary || !s.body?.length)
          ctx.addIssue({
            code: 'custom',
            path: ['services', i],
            message: 'a service with a slug needs summary and body',
          });
      }
      if (s.price_key && !(s.price_key in c.prices))
        ctx.addIssue({
          code: 'custom',
          path: ['services', i, 'price_key'],
          message: `unknown price key "${s.price_key}"`,
        });
      if (s.lead_dentist && !names.has(s.lead_dentist))
        ctx.addIssue({
          code: 'custom',
          path: ['services', i, 'lead_dentist'],
          message: `unknown dentist "${s.lead_dentist}"`,
        });
    });
    if (!c.services.some((s) => s.slug))
      ctx.addIssue({ code: 'custom', path: ['services'], message: 'at least one service needs a slug (own page)' });
  });

const fontStack = z
  .string()
  .regex(/^[A-Za-z0-9 ,'"-]{1,200}$/, 'font stack may only contain letters, digits, spaces, commas, dashes and quotes');
const hex = z.string().regex(/^#[0-9a-fA-F]{6}$/, 'must be a #rrggbb color');

export const ThemeSchema = z.strictObject({
  colors: z.strictObject({
    primary: hex,
    primaryContrast: hex,
    accent: hex,
    bg: hex,
    surface: hex,
    text: hex,
    muted: hex,
    border: hex,
  }),
  // allow-lists: these values are written into a <style> block, so no markup or CSS-breaking characters
  fonts: z.strictObject({ heading: fontStack, body: fontStack }),
  radius: z.string().regex(/^\d+(\.\d+)?(px|rem|em)$/, 'must look like 8px or 0.5rem'),
});

export const PostSchema = z
  .strictObject({
    title: z.string().min(10).max(90),
    description: z.string().min(60).max(170),
    slug: kebab,
    date: z.coerce.date(),
    updated: z.coerce.date(),
    author: z.string(),
    reviewed_by: z.string().optional(),
    category: kebab,
    service: kebab.optional(),
    faq: z.array(QA).default([]),
  })
  .refine((p) => p.updated >= p.date, { error: 'updated must not be before date', path: ['updated'] })
  .refine((p) => p.updated.getTime() <= Date.now(), { error: 'dates must not be in the future', path: ['updated'] });

export type Clinic = z.infer<typeof ClinicSchema>;
export type Theme = z.infer<typeof ThemeSchema>;
export type PostData = z.infer<typeof PostSchema>;
export type ServiceData = z.infer<typeof ClinicSchema>['services'][number];

export function formatIssues(err: z.ZodError, file: string): string {
  return err.issues.map((i) => `  ${file}: ${i.path.join('.') || '(root)'} - ${i.message}`).join('\n');
}
