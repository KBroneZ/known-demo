// All structured data is built here, from clinic.yaml and post frontmatter. Nothing is hand-written.
// Deliberately absent: aggregateRating, review, award. No such data exists in clinic.yaml.
import type { Clinic, PostData } from '@demo/schema';
import { isoDay, openingHoursSpec, slugify } from './format.ts';

export type JsonLd = Record<string, unknown>;

export const siteBase = (c: Clinic): string => c.website.replace(/\/$/, '');
export const dentistId = (c: Clinic): string => `${siteBase(c)}/#dentist`;
export const abs = (c: Clinic, p: string): string => (p === '/' ? `${siteBase(c)}/` : `${siteBase(c)}${p}`);

export function dentistLd(c: Clinic): JsonLd {
  const n = c.nap;
  return {
    '@context': 'https://schema.org',
    '@type': 'Dentist',
    '@id': dentistId(c),
    name: c.name,
    description: c.description,
    url: abs(c, '/'),
    telephone: n.phone,
    email: n.email,
    image: abs(c, '/og.png'),
    address: {
      '@type': 'PostalAddress',
      streetAddress: n.suite ? `${n.street}, ${n.suite}` : n.street,
      addressLocality: n.city,
      addressRegion: n.state,
      postalCode: n.zip,
      addressCountry: 'US',
    },
    ...(c.geo ? { geo: { '@type': 'GeoCoordinates', latitude: c.geo.lat, longitude: c.geo.lng } } : {}),
    openingHoursSpecification: openingHoursSpec(c),
    employee: c.dentists.map((d) => ({ '@type': 'Person', name: d.name, jobTitle: `Dentist (${d.credentials})` })),
    ...(c.seo.same_as.length ? { sameAs: c.seo.same_as } : {}),
    knowsAbout: c.services.map((s) => s.name),
  };
}

export function breadcrumbLd(c: Clinic, trail: { name: string; path: string }[]): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: trail.map((t, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: t.name,
      item: abs(c, t.path),
    })),
  };
}

export function faqLd(items: { question: string; answer: string }[]): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((q) => ({
      '@type': 'Question',
      name: q.question,
      acceptedAnswer: { '@type': 'Answer', text: q.answer },
    })),
  };
}

export function blogPostingLd(c: Clinic, p: PostData): JsonLd {
  const url = abs(c, `/blog/${p.slug}`);
  return {
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    headline: p.title,
    description: p.description,
    url,
    mainEntityOfPage: url,
    datePublished: isoDay(p.date),
    dateModified: isoDay(p.updated),
    author: { '@type': 'Person', name: p.author, url: abs(c, `/team#${slugify(p.author)}`) },
    publisher: { '@type': 'Dentist', '@id': dentistId(c), name: c.name, url: abs(c, '/') },
    image: abs(c, '/og.png'),
    inLanguage: 'en-US',
  };
}
