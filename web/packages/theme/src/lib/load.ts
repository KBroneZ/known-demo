// Reads and validates a site's data files. Used by the Astro integration (build time)
// and by the tools/ scripts, so both see exactly the same validation.
import fs from 'node:fs';
import path from 'node:path';
import { parse } from 'yaml';
import { ClinicSchema, ThemeSchema, formatIssues } from '@demo/schema';
import type { Clinic, Theme } from '@demo/schema';

export interface SiteData {
  clinic: Clinic;
  theme: Theme;
}

export function loadSiteData(root: string): SiteData {
  const clinicFile = path.join(root, 'clinic.yaml');
  const themeFile = path.join(root, 'theme.json');
  const clinicParsed = ClinicSchema.safeParse(parse(fs.readFileSync(clinicFile, 'utf8')));
  const themeParsed = ThemeSchema.safeParse(JSON.parse(fs.readFileSync(themeFile, 'utf8')));
  const problems: string[] = [];
  if (!clinicParsed.success) problems.push(formatIssues(clinicParsed.error, 'clinic.yaml'));
  if (!themeParsed.success) problems.push(formatIssues(themeParsed.error, 'theme.json'));
  if (!clinicParsed.success || !themeParsed.success) {
    throw new Error(`Invalid site data in ${root}:\n${problems.join('\n')}`);
  }
  return { clinic: clinicParsed.data, theme: themeParsed.data };
}
