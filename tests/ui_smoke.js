// Runtime smoke test of static/app.js with a minimal fake DOM and recorded API responses (no browser needed).
// Usage: node tests/ui_smoke.js /tmp/ui   (directory of JSON dumped from the real API)
const fs = require('fs');
const dir = process.argv[2] || '/tmp/ui';
const J = (n) => JSON.parse(fs.readFileSync(`${dir}/${n}.json`, 'utf8'));
function el() {
  const e = { style: {}, dataset: {}, _h: '', classList: { add() {}, remove() {} }, value: '', files: [], textContent: '',
    set innerHTML(v) { this._h = String(v); }, get innerHTML() { return this._h; },
    querySelector: () => el(), querySelectorAll: () => [], addEventListener() {}, setAttribute() {}, removeAttribute() {}, showModal() {}, appendChild() {}, focus() {}, click() {} };
  return e;
}
const appEl = el();
const nodes = { '#app': appEl };
global.document = { querySelector: (s) => nodes[s] || (nodes[s] = el()), querySelectorAll: () => [] };
let hashHandler = null;
global.window = { addEventListener: (t, f) => { if (t === 'hashchange') hashHandler = f; }, scrollTo() {} };
global.location = { hash: '' };
global.navigator = {};
global.FormData = class { constructor() { this.d = {}; } append(k, v) { this.d[k] = v; } get(k) { return this.d[k]; } };
global.Object.fromEntries = Object.fromEntries;
let who = process.env.WHO || 'anon';   // run once per role: the app reads /api/me at load
let caseKey = null;
global.fetch = async (path, opts = {}) => {
  const p = path.split('?')[0];
  const body = (() => {
    if (p === '/api/me') return J('me_' + who);
    if (p === '/api/health') return J('health');
    if (p === '/api/samples') return J('samples');
    if (p === '/api/transparency') return J('transparency');
    if (p === '/api/policy') return J('policy');
    if (p === '/api/visit') return J('stats');
    if (p === '/api/cases') return J('cases_' + who);
    if (p.startsWith('/api/cases/')) return J(`case_${caseKey}_${who}`);
    throw new Error('unmocked ' + p);
  })();
  return { ok: true, status: 200, json: async () => body };
};
let errors = 0;
const orig = console.error; console.error = (...a) => { errors++; orig(...a); };
const files = require('fs').readFileSync(__dirname + '/../hairline/static/app.js', 'utf8');
(0, eval)(files);
const wait = () => new Promise((r) => setTimeout(r, 30));
(async () => {
  await wait();
  const checks = [];
  async function visit(hash, expect, w = 'anon', ck = null) {
    if (w !== who) return;   // only exercise pages for the role this process was started as
    caseKey = ck; location.hash = hash; hashHandler && (await hashHandler()); await wait(); await wait();
    const html = appEl.innerHTML;
    const ok = expect.every((s) => html.includes(s)) && !html.includes('undefined') && !html.includes('NaN');
    checks.push([ok, `${hash} as ${w}${ck ? ' (' + ck + ')' : ''}`, ok ? '' : `missing ${expect.filter((s) => !html.includes(s))} undefined=${html.includes('undefined')} NaN=${html.includes('NaN')} len=${html.length} head=${html.slice(0, 160)}`]);
  }
  await visit('#/try', ['Measure the crack', 'sample'], 'anon');
  await visit('#/cases', ['Cases', 'awaiting engineer', 'simulated'], 'anon');
  await visit('#/cases', ['New case', 'Import complaints'], 'eng');
  await visit('#/about', ['How HAIRLINE works', 'Authorisation policy', 'F-CLOSE-NEEDS-EVIDENCE'], 'anon');
  for (const st of ['AUTHORISED', 'REVIEW_REQUESTED', 'DISPUTED', 'MEASURED', 'NEEDS_RESHOOT', 'CLOSED']) {
    for (const w of ['anon', 'eng', 'res']) {
      const id = J('id_' + st);
      await visit('#/case/' + id, ['Governance', 'Width over time', 'Audit log'], w, st);
    }
  }
  await visit('#/case/' + J('id_AUTHORISED'), ['Close ticket'], 'eng', 'AUTHORISED');
  await visit('#/case/' + J('id_DISPUTED'), ['Uphold dispute'], 'eng', 'DISPUTED');
  await visit('#/case/' + J('id_CLOSED'), ['Dispute this closure'], 'res', 'CLOSED');
  let bad = 0;
  for (const [ok, name, why] of checks) { if (!ok) bad++; console.log(ok ? 'PASS' : 'FAIL', name, why); }
  console.log(`[${who}] ${checks.length - bad}/${checks.length} page renders passed; console errors: ${errors}`);
  process.exit(bad || errors ? 1 : 0);
})();
