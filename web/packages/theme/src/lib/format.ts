import type { Clinic } from '@demo/schema';
import { DAYS } from '@demo/schema';

const DAY_NAMES: Record<string, string> = {
  mon: 'Monday',
  tue: 'Tuesday',
  wed: 'Wednesday',
  thu: 'Thursday',
  fri: 'Friday',
  sat: 'Saturday',
  sun: 'Sunday',
};

export function slugify(s: string): string {
  return s
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/** "08:00" -> "8 a.m.", "13:30" -> "1:30 p.m." */
export function clock(t: string): string {
  const [h, m] = t.split(':').map(Number);
  const suffix = h >= 12 ? 'p.m.' : 'a.m.';
  const hh = h % 12 === 0 ? 12 : h % 12;
  return m === 0 ? `${hh} ${suffix}` : `${hh}:${String(m).padStart(2, '0')} ${suffix}`;
}

function dayRange(days: readonly string[]): string {
  const idx = days.map((d) => DAYS.indexOf(d as (typeof DAYS)[number])).sort((a, b) => a - b);
  const consecutive = idx.every((v, i) => i === 0 || v === idx[i - 1] + 1);
  const names = idx.map((i) => DAY_NAMES[DAYS[i]]);
  if (names.length === 1) return names[0];
  if (consecutive) return `${names[0]} through ${names[names.length - 1]}`;
  return names.slice(0, -1).join(', ') + ' and ' + names[names.length - 1];
}

/** "Monday through Thursday from 8 a.m. to 5 p.m., and on Friday from 8 a.m. to 1 p.m." */
export function hoursSentence(c: Clinic): string {
  const parts = c.hours.map((h) => `${dayRange(h.days)} from ${clock(h.open)} to ${clock(h.close)}`);
  if (parts.length === 1) return parts[0];
  return parts.slice(0, -1).join(', ') + ', and on ' + parts[parts.length - 1];
}

export function hoursRows(c: Clinic): { days: string; time: string }[] {
  const rows = c.hours.map((h) => ({ days: dayRange(h.days), time: `${clock(h.open)} to ${clock(h.close)}` }));
  const open = new Set(c.hours.flatMap((h) => h.days));
  const closed = DAYS.filter((d) => !open.has(d));
  if (closed.length) rows.push({ days: dayRange(closed), time: 'Closed' });
  return rows;
}

export function openingHoursSpec(c: Clinic) {
  return c.hours.map((h) => ({
    '@type': 'OpeningHoursSpecification',
    dayOfWeek: h.days.map((d) => DAY_NAMES[d]),
    opens: h.open,
    closes: h.close,
  }));
}

export function addressLine(c: Clinic): string {
  const n = c.nap;
  return `${n.street}${n.suite ? ', ' + n.suite : ''}, ${n.city}, ${n.state} ${n.zip}`;
}

export function telHref(phone: string): string {
  return 'tel:+1' + phone.replace(/\D/g, '');
}

export function formatDate(d: Date): string {
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
}

export function isoDay(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Append a period unless the text already ends with one (hours end in "p.m."). */
export function endSentence(s: string): string {
  return s.endsWith('.') ? s : s + '.';
}
