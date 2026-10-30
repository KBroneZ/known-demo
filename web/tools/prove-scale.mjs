// Proof that one template change reaches every site without touching their content.
//   0. build, then diff against the APPROVED golden/ (it is never rewritten here); must be 0
//   1. snapshot the build into a scratch golden (reports/.scale-golden)
//   2. control: rebuild, diff must be 0   (the build is deterministic)
//   3. edit packages/theme Footer.astro, rebuild all sites, diff:
//        expect: only <footer> changed, content text diff = 0, sitemap/robots/llms unchanged
//   4. negative control: edit the CTA (outside the footer): the diff must flag it
//   5. restore every edited file, rebuild, diff must be 0 again
// Edited files are restored in a finally block and on Ctrl-C. The report is written even on failure,
// and an older report is deleted first, so a stale PASS can never survive a broken run.
import fs from 'node:fs';
import path from 'node:path';
import { WEB_ROOT, listSites } from './lib.mjs';
import { buildSite } from './build-all.mjs';
import { snapshot, diffSite, diffFailed, summarize, GOLDEN } from './golden.mjs';

const THEME = path.join(WEB_ROOT, 'packages/theme/src/components');
const FOOTER = path.join(THEME, 'Footer.astro');
const CTA = path.join(THEME, 'Cta.astro');
const REPORT = path.join(WEB_ROOT, 'reports', 'scale-proof.json');
const SCRATCH = path.join(WEB_ROOT, 'reports', '.scale-golden');
const sites = listSites();
const originals = new Map([FOOTER, CTA].map((f) => [f, fs.readFileSync(f, 'utf8')]));
const restore = () => {
  for (const [file, text] of originals) fs.writeFileSync(file, text);
};
process.on('SIGINT', () => {
  restore();
  process.exit(130);
});

function buildAll() {
  const t0 = performance.now();
  const r = sites.map(buildSite);
  return {
    seconds: Number(((performance.now() - t0) / 1000).toFixed(2)),
    pages: r.reduce((s, x) => s + x.htmlPages, 0),
  };
}
function diffAll(region, golden) {
  const per = sites.map((s) => diffSite(s, region, golden));
  per.forEach((r) => console.log('   ' + summarize(r, region)));
  return per;
}
const sum = (per, k) => per.reduce((s, r) => s + (typeof r[k] === 'number' ? r[k] : r[k].length), 0);
const changedFiles = (per) => per.reduce((s, r) => s + r.files - r.unchanged, 0);

fs.mkdirSync(path.dirname(REPORT), { recursive: true });
fs.rmSync(REPORT, { force: true });
const proof = { verdict: 'FAIL' };
let failure = null;

try {
  console.log('0. build and compare with the approved golden/');
  proof.baselineBuild = buildAll();
  const approved = diffAll('footer', GOLDEN);
  proof.approvedGoldenFiles = approved.reduce((s, r) => s + r.files, 0);
  proof.approvedGoldenDiffs = approved.filter(diffFailed).length;
  if (approved.some(diffFailed))
    throw new Error('current build differs from the approved golden/ (or golden/ is empty): resolve that first');

  console.log('1. scratch snapshot');
  fs.rmSync(SCRATCH, { recursive: true, force: true });
  proof.goldenFiles = sites.reduce((s, id) => s + snapshot(id, SCRATCH), 0);

  console.log('2. control: rebuild without changes');
  buildAll();
  const control = diffAll('footer', SCRATCH);
  proof.control = { changedFiles: changedFiles(control) };

  console.log('3. template change: new footer legal block');
  const f = originals
    .get(FOOTER)
    .replace(
      '<p>Fictional demo: {clinic.name} is not a real practice. Names, address, phone and content are invented for a software demonstration.</p>',
      '<p>Fictional demo: {clinic.name} is not a real practice. Names, address, phone and content are invented for a software demonstration.</p>\n    <p>Accessibility: we aim for WCAG 2.2 AA. Telephone for assistance: <a href={telHref(clinic.nap.phone)}>{clinic.nap.phone}</a>. Privacy policy available on request.</p>',
    );
  if (f === originals.get(FOOTER)) throw new Error('footer edit did not apply');
  fs.writeFileSync(FOOTER, f);
  proof.changeBuild = buildAll();
  const change = diffAll('footer', SCRATCH);
  proof.templateChange = {
    sites: sites.length,
    htmlFiles: proof.baselineBuild.pages,
    goldenFilesIncludingXmlTxt: sum(change, 'files'),
    changedFiles: changedFiles(change),
    onlyFooterChanged: sum(change, 'regionOnly'),
    changedOutsideFooter: sum(change, 'outsideChanged'),
    contentTextDiffs: sum(change, 'textChanged'),
    nonHtmlChanged: sum(change, 'otherFilesChanged'),
    footerBytesAddedTotal: sum(change, 'regionBytesDelta'),
  };
  fs.writeFileSync(FOOTER, originals.get(FOOTER));

  console.log('4. negative control: edit the CTA outside the footer; the diff must notice');
  const cta = originals.get(CTA).replace("'Book your visit'", "'Book now'");
  if (cta === originals.get(CTA)) throw new Error('CTA edit did not apply');
  fs.writeFileSync(CTA, cta);
  buildAll();
  const neg = diffAll('footer', SCRATCH);
  proof.negativeControl = {
    pagesFlaggedOutsideFooter: sum(neg, 'outsideChanged'),
    pagesWithContentTextDiff: sum(neg, 'textChanged'),
  };
} catch (e) {
  failure = e;
  proof.error = e.message;
} finally {
  restore();
}

try {
  console.log('5. restore templates, rebuild, diff against the approved golden/ must be 0');
  proof.restoreBuild = buildAll();
  const back = diffAll('footer', GOLDEN);
  proof.restored = { changedFiles: changedFiles(back), failed: back.some(diffFailed) };
} catch (e) {
  failure ??= e;
  proof.error ??= e.message;
}
fs.rmSync(SCRATCH, { recursive: true, force: true });

const t = proof.templateChange;
proof.verdict =
  !failure &&
  proof.control?.changedFiles === 0 &&
  t &&
  t.changedFiles > 0 &&
  t.changedOutsideFooter === 0 &&
  t.contentTextDiffs === 0 &&
  t.nonHtmlChanged === 0 &&
  t.onlyFooterChanged === t.htmlFiles &&
  proof.negativeControl?.pagesFlaggedOutsideFooter > 0 &&
  proof.restored?.changedFiles === 0 &&
  !proof.restored?.failed
    ? 'PASS'
    : 'FAIL';
fs.writeFileSync(REPORT, JSON.stringify(proof, null, 2));
console.log(JSON.stringify(proof, null, 2));
process.exit(proof.verdict === 'PASS' ? 0 : 1);
