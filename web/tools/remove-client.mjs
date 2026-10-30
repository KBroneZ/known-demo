// Remove a client site and its golden snapshots: node tools/remove-client.mjs <id>
import fs from 'node:fs';
import path from 'node:path';
import { siteDir, WEB_ROOT } from './lib.mjs';

const id = process.argv[2];
if (!id || !/^[a-z0-9-]+$/.test(id)) {
  console.error('usage: node tools/remove-client.mjs <site-id>');
  process.exit(2);
}
for (const p of [siteDir(id), path.join(WEB_ROOT, 'golden', id)]) {
  if (fs.existsSync(p)) {
    fs.rmSync(p, { recursive: true, force: true });
    console.log('removed ' + path.relative(WEB_ROOT, p));
  }
}
