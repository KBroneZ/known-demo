// Runtime view of the site inside Astro: validated clinic data + posts + one route table
// that feeds pages, sitemap, llms.txt and navigation, so none of them can disagree.
import { getCollection } from 'astro:content';
import site from 'virtual:clinic-site';
import type { PostData, ServiceData } from '@demo/schema';
import { hoursSentence, endSentence, isoDay, slugify, addressLine, formatDate } from './format.ts';

export const { clinic, theme } = site;

export interface Post {
  id: string;
  data: PostData;
  body: string;
  entry: Awaited<ReturnType<typeof getCollection<'posts'>>>[number];
}

export async function getPosts(): Promise<Post[]> {
  const entries = await getCollection('posts');
  const names = new Set(clinic.dentists.map((d) => d.name));
  const serviceSlugs = new Set(clinic.services.map((s) => s.slug).filter(Boolean));
  const posts = entries.map((e) => ({ id: e.data.slug, data: e.data as PostData, body: e.body ?? '', entry: e }));
  for (const p of posts) {
    const where = `post "${p.id}"`;
    if (!names.has(p.data.author))
      throw new Error(`${where}: author "${p.data.author}" is not a dentist in clinic.yaml`);
    if (p.data.reviewed_by && !names.has(p.data.reviewed_by))
      throw new Error(`${where}: reviewed_by "${p.data.reviewed_by}" is not a dentist in clinic.yaml`);
    if (p.data.service && !serviceSlugs.has(p.data.service))
      throw new Error(`${where}: service "${p.data.service}" has no page in clinic.yaml`);
  }
  return posts.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());
}

export const servicePages = (): ServiceData[] => clinic.services.filter((s) => s.slug);
export const dentistSlug = (name: string): string => slugify(name);

/** FAQ entries derived from the data (hours, insurance, prices) plus the hand-written ones. */
export function generalFaq(): { question: string; answer: string }[] {
  const derived: { question: string; answer: string }[] = [
    {
      question: `What are the hours at ${clinic.name}?`,
      answer: `We are open ${endSentence(hoursSentence(clinic))} ${clinic.emergency_line ?? ''}`.trim(),
    },
    {
      question: 'Where is the office and how do I book?',
      answer: `We are at ${addressLine(clinic)}. Call ${clinic.nap.phone} or email ${clinic.nap.email} to book.`,
    },
  ];
  if (clinic.insurance_accepted.length) {
    const list = clinic.insurance_accepted;
    derived.push({
      question: 'Which dental insurance plans do you accept?',
      answer: `We are in network with ${list.slice(0, -1).join(', ')}${list.length > 1 ? ' and ' : ''}${list[list.length - 1]}. Our front desk can check your benefits before you come in.`,
    });
  }
  return [...derived, ...clinic.faq];
}

const excerpt = (s: string, max = 155): string => {
  if (s.length <= max) return s;
  const cut = s.slice(0, max - 1);
  return cut.slice(0, cut.lastIndexOf(' ')).replace(/[,.;:]$/, '') + '…';
};

export interface RouteMeta {
  path: string;
  title: string;
  description: string;
  lastmod: string;
  kind: 'home' | 'about' | 'team' | 'contact' | 'faq' | 'services' | 'service' | 'blog' | 'post';
  name: string; // short label for nav / breadcrumbs / llms.txt
}

export async function routeTable(): Promise<RouteMeta[]> {
  const posts = await getPosts();
  const city = `${clinic.nap.city}, ${clinic.nap.state}`;
  const base = clinic.updated;
  const latestPost = posts.length ? isoDay(new Date(Math.max(...posts.map((p) => p.data.updated.getTime())))) : base;
  const t = (s: string): string => `${s} | ${clinic.name}`;
  const rows: RouteMeta[] = [
    { path: '/', kind: 'home', name: 'Home', title: t(clinic.tagline), description: clinic.description, lastmod: base },
    {
      path: '/about',
      kind: 'about',
      name: 'About us',
      title: t(`About us`),
      description: excerpt(clinic.about.paragraphs[0]),
      lastmod: base,
    },
    {
      path: '/team',
      kind: 'team',
      name: 'Our dentists',
      title: t('Our dentists'),
      description: `Meet ${clinic.dentists.map((d) => d.name).join(' and ')}, dentists at ${clinic.name} in ${city}.`,
      lastmod: base,
    },
    {
      path: '/services',
      kind: 'services',
      name: 'Services',
      title: t(`Dental services in ${city}`),
      description: `Dental care at ${clinic.name} in ${city}: ${clinic.services
        .slice(0, 4)
        .map((s) => s.name.toLowerCase())
        .join(', ')} and more.`,
      lastmod: base,
    },
    ...servicePages().map(
      (s): RouteMeta => ({
        path: `/services/${s.slug}`,
        kind: 'service',
        name: s.name,
        title: t(`${s.name} in ${city}`),
        description: s.summary!,
        lastmod: base,
      }),
    ),
    {
      path: '/blog',
      kind: 'blog',
      name: 'Blog',
      title: t('Dental health blog'),
      description: `Plain-language dental advice from the dentists at ${clinic.name} in ${city}.`,
      lastmod: latestPost,
    },
    ...posts.map(
      (p): RouteMeta => ({
        path: `/blog/${p.data.slug}`,
        kind: 'post',
        name: p.data.title,
        title: t(p.data.title),
        description: p.data.description,
        lastmod: isoDay(p.data.updated),
      }),
    ),
    {
      path: '/faq',
      kind: 'faq',
      name: 'FAQ',
      title: t('Frequently asked questions'),
      description: `Answers about hours, insurance, booking and care at ${clinic.name} in ${city}.`,
      lastmod: base,
    },
    {
      path: '/contact',
      kind: 'contact',
      name: 'Contact and hours',
      title: t('Contact and hours'),
      description: `Call ${clinic.nap.phone} or visit us at ${addressLine(clinic)}. See our opening hours and how to reach us.`,
      lastmod: base,
    },
  ];
  return rows;
}

export async function metaFor(path: string): Promise<RouteMeta> {
  const row = (await routeTable()).find((r) => r.path === path);
  if (!row) throw new Error(`no route metadata for ${path}`);
  return row;
}

export const NAV: { path: string; label: string }[] = [
  { path: '/services', label: 'Services' },
  { path: '/team', label: 'Our dentists' },
  { path: '/blog', label: 'Blog' },
  { path: '/faq', label: 'FAQ' },
  { path: '/contact', label: 'Contact' },
];

export { formatDate };
