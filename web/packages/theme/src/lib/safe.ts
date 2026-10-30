// Serialisation helpers for data that is written into <script> and <style> blocks.

/**
 * JSON for a <script type="application/ld+json"> block. JSON.stringify does not escape
 * "</script>" or "<!--", so every "<" (and the JS line separators) is written as a unicode escape:
 * clinic.yaml or post text can never close the block and inject markup.
 */
export function safeJson(value: unknown): string {
  return JSON.stringify(value)
    .replace(/</g, '\\u003c')
    .replace(new RegExp('\u2028', 'g'), '\\u2028')
    .replace(new RegExp('\u2029', 'g'), '\\u2029');
}

/** CSS custom properties for :root. Values are allow-list validated by ThemeSchema; "<" is stripped as defence in depth. */
export function cssTokens(vars: Record<string, string>): string {
  const body = Object.entries(vars)
    .map(([k, v]) => `--${k}:${v}`)
    .join(';');
  return `:root{${body}}`.replace(/</g, '');
}
