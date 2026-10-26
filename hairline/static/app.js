/* HAIRLINE front-end. Vanilla JS, no build step, CSP-safe (no inline scripts/styles). */
(() => {
const $ = (s, r = document) => r.querySelector(s);
const app = $('#app');
let me = { role: 'anonymous', name: 'Visitor' };
let health = {};

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const fmt = (n, d = 2) => (n === null || n === undefined ? '-' : Number(n).toFixed(d));
const when = (t) => new Date(t * 1000).toLocaleString();

async function api(path, opts = {}) {
  const o = { method: opts.method || 'GET', headers: { 'X-HL': '1' }, credentials: 'same-origin' };
  if (opts.json !== undefined) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(opts.json); }
  if (opts.form) { o.body = opts.form; }
  if (opts.text !== undefined) { o.headers['Content-Type'] = 'text/csv'; o.body = opts.text; }
  const r = await fetch(path, o);
  let data = null;
  try { data = await r.json(); } catch (e) { /* non-json */ }
  if (!r.ok) {
    const msg = (data && (data.decision ? data.decision.reason : data.error)) || ('HTTP ' + r.status);
    const err = new Error(msg); err.status = r.status; throw err;
  }
  return data;
}

let toastT;
function toast(msg, bad = false) {
  const t = $('#toast'); t.textContent = msg; t.className = 'toast show' + (bad ? ' err' : '');
  clearTimeout(toastT); toastT = setTimeout(() => (t.className = 'toast'), 4200);
}
const busy = (el, on) => { if (el) { el.disabled = on; el.dataset.t = el.dataset.t || el.textContent; el.innerHTML = on ? '<span class="spin"></span> Working' : esc(el.dataset.t); } };

/* ---------------------------------------------------------------- shell */
function renderWho() {
  const w = $('#who');
  if (me.role === 'anonymous') {
    w.innerHTML = '<span class="pill">Read-only visitor</span><button class="btn small primary" id="signin">Sign in (demo)</button>';
    $('#signin').onclick = () => $('#login').showModal();
  } else {
    w.innerHTML = '<span class="pill demo">DEMO AUTH</span><span class="pill">' + esc(me.name) + ' / ' + esc(me.role) + '</span><button class="btn small" id="signout">Sign out</button>';
    $('#signout').onclick = async () => { await api('/api/logout', { method: 'POST', json: {} }); await loadMe(); route(); };
  }
}
async function loadMe() { me = await api('/api/me'); renderWho(); }
$('#login-form').addEventListener('submit', async (e) => {
  const v = e.submitter && e.submitter.value;
  if (v !== 'ok') return;
  try {
    await api('/api/login', { method: 'POST', json: { role: $('#login-role').value, name: $('#login-name').value } });
    await loadMe(); route(); toast('Signed in as ' + me.role);
  } catch (err) { toast(err.message, true); }
});

async function countVisit() {
  try {
    const s = await api('/api/visit', { method: 'POST', json: {} });
    $('#vc').textContent = s.unique_visitors.toLocaleString(); $('#pv').textContent = s.page_views.toLocaleString();
  } catch (e) { /* counter is best-effort */ }
}
async function loadHealth() {
  try { health = await api('/api/health'); $('#build').textContent = 'v' + health.version + ' | OpenCV ' + health.opencv + ' | planner ' + health.planner + ' | ' + health.store + (health.release ? ' | build ' + health.release.slice(0, 8) : ''); } catch (e) { /* ignore */ }
}

/* ---------------------------------------------------------------- shared renderers */
const statusChip = (s) => '<span class="status s-' + esc(s) + '">' + esc(String(s).replace(/_/g, ' ')) + '</span>';
const sevChip = (s) => '<span class="status sev-' + esc(s) + '">' + esc(s) + '</span>';

function gatesHtml(q) {
  if (!q || !q.gates) return '';
  return '<ul class="gates">' + q.gates.map((g) => {
    const cls = g.pass ? 'ok' : (g.level === 'block' ? 'bad' : 'warn');
    const sym = g.pass ? 'ok' : (g.level === 'block' ? 'x' : '!');
    const val = g.value === null ? '' : ' <span class="mono">' + esc(g.value) + (g.threshold !== null && g.threshold !== undefined ? ' / limit ' + esc(g.threshold) : '') + '</span>';
    return '<li><span class="tick ' + cls + '" aria-hidden="true">' + sym + '</span><span><b>' + esc(g.name.replace(/_/g, ' ')) + '</b> ' + (g.pass ? 'passed' : (g.level === 'block' ? 'blocked' : 'warning')) + val + (g.pass ? '' : '<br>' + esc(g.advice)) + '</span></li>';
  }).join('') + '</ul>';
}
function traceHtml(trace) {
  return '<ol class="trace">' + (trace || []).map((t) => {
    const obs = Object.entries(t.observation || {}).map(([k, v]) => k + '=' + (Array.isArray(v) ? '[' + v.join(',') + ']' : (typeof v === 'number' ? Number(v.toFixed ? v.toFixed(3) : v) : v))).join('  ');
    return '<li><span class="tool">' + esc(t.step + '. ' + t.tool) + '</span><span class="status act">' + esc(t.action) + '</span><div class="obs">' + esc(obs) + '</div><div>' + esc(t.reason) + (t.note ? ' <i>(' + esc(t.note) + ')</i>' : '') + ' <span class="mono">' + esc(t.t_ms) + ' ms, ' + esc(t.planner) + '</span></div></li>';
  }).join('') + '</ol>';
}
function metricsHtml(m) {
  if (!m) return '';
  if (!m.found) return '<div class="notice ok"><b>No crack detected</b> in the monitoring window. That is not proof there is no crack elsewhere.</div>';
  return '<div class="metrics"><div class="metric"><b>' + fmt(m.width_p90_mm) + ' mm</b><span>Width (p90)</span></div>' +
    '<div class="metric"><b>&plusmn;' + fmt(m.uncertainty_mm) + '</b><span>Uncertainty mm</span></div>' +
    '<div class="metric"><b>' + fmt(m.length_mm, 0) + ' mm</b><span>Length</span></div>' +
    '<div class="metric"><b>' + fmt(m.width_med_mm) + '</b><span>Median width mm</span></div></div>';
}
function decisionCard(r) {
  const cls = r.status === 'NEEDS_RESHOOT' ? 'notice' : (r.status === 'REVIEW_REQUESTED' ? 'notice bad' : 'notice ok');
  return '<div class="' + cls + '"><div class="row">' + statusChip(r.status) + (r.severity && r.severity !== 'unknown' ? sevChip(r.severity) : '') + '</div><p><b>' + esc(r.guidance) + '</b></p></div>';
}

/* ---------------------------------------------------------------- pages */
async function pageTry() {
  const samples = await api('/api/samples').catch(() => []);
  app.innerHTML = `
  <section class="hero">
    <div>
      <h1>Measure the crack.<br><span class="hl">Know when to look again.</span></h1>
      <p class="lead">Print one marker. Take one photo. HAIRLINE rectifies the wall with OpenCV, measures the crack in <b>millimetres</b> with an error bar, and if the photo is not good enough it tells you <b>exactly how to retake it</b>. Serious or growing cracks become a review request for an engineer. Nothing is sent automatically.</p>
    </div>
    <div class="zig" aria-hidden="true"></div>
  </section>
  <section class="grid g2">
    <div class="card">
      <h2>1. Pick a photo</h2>
      <p class="fine">Try a bundled sample (synthetic, known crack width) or use your phone camera with the printed marker.</p>
      <div class="chips" id="samples" role="group" aria-label="Sample photos">${samples.map((s) => '<button class="chip" data-s="' + esc(s.file) + '" aria-pressed="false">' + esc(s.label) + '</button>').join('')}</div>
      <p></p>
      <div class="drop">
        <label>Or take / upload a photo
          <input type="file" id="file" accept="image/*" capture="environment"></label>
        <p class="fine">Max ${12} MB. EXIF/GPS is stripped. <a href="/api/marker.png?id=7" target="_blank" rel="noopener">Download printable marker (50 mm)</a></p>
      </div>
      <p><button class="btn primary" id="go">Assess photo</button></p>
    </div>
    <div class="card" id="result"><h2>2. Agent result</h2><p class="fine">The result, the quality gates and the agent trace appear here.</p></div>
  </section>`;
  let chosen = null;
  app.querySelectorAll('#samples .chip').forEach((b) => (b.onclick = () => {
    chosen = b.dataset.s; $('#file').value = '';
    app.querySelectorAll('#samples .chip').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  }));
  $('#file').onchange = () => { chosen = null; app.querySelectorAll('#samples .chip').forEach((x) => x.setAttribute('aria-pressed', 'false')); };
  $('#go').onclick = async () => {
    const f = $('#file').files[0];
    if (!chosen && !f) { toast('Pick a sample or a photo first', true); return; }
    const fd = new FormData(); if (chosen) fd.append('sample', chosen); else fd.append('image', f);
    busy($('#go'), true);
    $('#result').innerHTML = '<h2>2. Agent result</h2><p><span class="spin"></span> Running OpenCV pipeline</p>';
    try {
      const r = await api('/api/assess', { method: 'POST', form: fd });
      $('#result').innerHTML = '<h2>2. Agent result</h2>' + decisionCard(r) +
        (r.overlay ? '<div class="imgbox"><img src="' + r.overlay + '" alt="Rectified wall with detected crack in coral, skeleton in cyan, marker outlined, 50 millimetre scale bar"></div>' : '') +
        metricsHtml(r.measurement) + '<h3>Quality gates</h3>' + gatesHtml(r.quality) +
        '<details open><summary>Agent trace: perception, decision, action</summary>' + traceHtml(r.trace) + '</details>';
    } catch (e) { $('#result').innerHTML = '<h2>2. Agent result</h2><div class="notice bad">' + esc(e.message) + '</div>'; }
    busy($('#go'), false);
  };
}

async function pageCases() {
  const cases = await api('/api/cases');
  const cnt = (f) => cases.filter(f).length;
  const canCreate = me.role !== 'anonymous';
  app.innerHTML = `
  <h1>Cases</h1>
  <p class="lead">Ranked by severity and growth. Closing a case needs <b>engineer authorisation</b> and <b>after-repair photo evidence</b>; residents can <b>dispute</b> a closure. Duplicate reports merge by marker id or within 30 m.</p>
  <div class="tiles">
    <div class="tile"><b>${cases.length}</b>cases</div>
    <div class="tile"><b>${cnt((c) => c.status === 'REVIEW_REQUESTED')}</b>awaiting engineer</div>
    <div class="tile"><b>${cnt((c) => c.status === 'AUTHORISED')}</b>repair authorised</div>
    <div class="tile"><b>${cnt((c) => c.status === 'DISPUTED')}</b>disputed</div>
    <div class="tile"><b>${cnt((c) => c.status === 'CLOSED')}</b>closed</div>
  </div>
  <div class="cases">${cases.map((c) => {
    const sc = c.priority_score || 0; const cls = c.severity === 'urgent' ? 'u' : (c.severity === 'priority' ? 'p' : (sc ? '' : 'z'));
    const last = [...c.visits].reverse().find((v) => v.measurement && v.measurement.found);
    return '<a class="card case ' + (c.simulated ? 'sim' : '') + '" href="#/case/' + esc(c.id) + '"><div class="score ' + cls + '" title="Priority score (estimated triage heuristic)">' + sc + '</div><div><h3>' + esc(c.site) + '</h3><div class="meta">' + statusChip(c.status) + sevChip(c.severity) + (c.simulated ? '<span class="status">simulated</span>' : '') + (last ? '<span class="mono">' + fmt(last.measurement.width_p90_mm) + ' &plusmn; ' + fmt(last.measurement.uncertainty_mm) + ' mm</span>' : '') + (c.duplicate_reports.length ? '<span class="mono">' + c.duplicate_reports.length + ' merged reports</span>' : '') + '</div></div><span class="go" aria-hidden="true">&rarr;</span></a>';
  }).join('') || '<p>No cases yet.</p>'}</div>
  <section class="grid g2" id="forms">
    <div class="card"><h2>New case</h2>${canCreate ? `
      <form class="stack" id="newcase">
        <label>Site / location <input name="site" required maxlength="120" placeholder="Stairwell wall, Block B"></label>
        <label>Description <textarea name="description" maxlength="500" placeholder="What did you notice?"></textarea></label>
        <div class="row"><label>Marker id (0-49, optional)<input name="marker_id" type="number" min="0" max="49"></label>
        <label>Latitude<input name="lat" id="lat" inputmode="decimal"></label><label>Longitude<input name="lon" id="lon" inputmode="decimal"></label></div>
        <div class="row"><button type="button" class="btn small" id="geo">Use my location</button><button class="btn primary" type="submit">Create case</button></div>
        <p class="fine">Same marker id merges into the open case. Reports within 30 m are flagged as possible duplicates.</p>
      </form>` : '<p>Sign in (demo) as a resident or engineer to report a crack.</p>'}</div>
    <div class="card"><h2>Import complaints (engineer)</h2>${me.role === 'engineer' ? `
      <p class="fine">Paste CSV with columns <span class="mono">site,description,lat,lon,marker_id</span>. Duplicates within 30 m merge automatically.</p>
      <textarea id="csv" placeholder="site,description,lat,lon,marker_id"></textarea>
      <p><button class="btn violet" id="imp">Import</button></p>` : '<p>Engineers can bulk-import a ward or society complaint register. This is the path from real municipal data into HAIRLINE.</p>'}</div>
  </section>`;
  const nc = $('#newcase');
  if (nc) {
    $('#geo').onclick = () => navigator.geolocation ? navigator.geolocation.getCurrentPosition((p) => { $('#lat').value = p.coords.latitude.toFixed(5); $('#lon').value = p.coords.longitude.toFixed(5); }, () => toast('Location unavailable', true)) : toast('No geolocation', true);
    nc.onsubmit = async (e) => {
      e.preventDefault(); const d = Object.fromEntries(new FormData(nc));
      try { const c = await api('/api/cases', { method: 'POST', json: d }); toast(c.merged ? 'Merged into existing case (same marker)' : 'Case created'); location.hash = '#/case/' + c.id; }
      catch (err) { toast(err.message, true); }
    };
  }
  const imp = $('#imp');
  if (imp) imp.onclick = async () => {
    try { const r = await api('/api/import', { method: 'POST', text: $('#csv').value }); toast('Created ' + r.created + ', merged ' + r.merged_duplicates + (r.errors.length ? ', errors ' + r.errors.length : '')); pageCases(); }
    catch (err) { toast(err.message, true); }
  };
}

function chartSvg(visits) {
  const pts = visits.filter((v) => v.measurement && v.measurement.found);
  if (pts.length < 1) return '<p class="fine">No measured visits yet.</p>';
  const W = 560, H = 220, pl = 46, pr = 14, pt = 16, pb = 34;
  const max = Math.max(1, ...pts.map((v) => v.measurement.width_p90_mm + v.measurement.uncertainty_mm)) * 1.15;
  const x = (i) => pl + (pts.length === 1 ? (W - pl - pr) / 2 : i * (W - pl - pr) / (pts.length - 1));
  const y = (v) => H - pb - (v / max) * (H - pt - pb);
  let s = '<svg class="chart" viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="Crack width over visits with uncertainty bars">';
  for (let k = 0; k <= 4; k++) { const v = max * k / 4; s += '<line x1="' + pl + '" x2="' + (W - pr) + '" y1="' + y(v) + '" y2="' + y(v) + '" stroke="#ddd"/><text x="4" y="' + (y(v) + 4) + '" font-size="11" font-family="monospace">' + v.toFixed(1) + '</text>'; }
  s += '<polyline fill="none" stroke="#111" stroke-width="3" points="' + pts.map((v, i) => x(i) + ',' + y(v.measurement.width_p90_mm)).join(' ') + '"/>';
  pts.forEach((v, i) => {
    const m = v.measurement;
    s += '<line x1="' + x(i) + '" x2="' + x(i) + '" y1="' + y(m.width_p90_mm + m.uncertainty_mm) + '" y2="' + y(Math.max(0, m.width_p90_mm - m.uncertainty_mm)) + '" stroke="#FF5A6E" stroke-width="4"/>';
    s += '<circle cx="' + x(i) + '" cy="' + y(m.width_p90_mm) + '" r="7" fill="#D7FF3F" stroke="#111" stroke-width="3"/>';
    s += '<text x="' + x(i) + '" y="' + (H - 12) + '" text-anchor="middle" font-size="11" font-family="monospace">' + esc(v.kind.replace('_', ' ')) + '</text>';
  });
  return s + '<text x="' + (W - pr) + '" y="12" text-anchor="end" font-size="11" font-family="monospace">p90 width, mm (bars = uncertainty)</text></svg>';
}

async function pageCase(id) {
  let c;
  try { c = await api('/api/cases/' + id); } catch (e) { app.innerHTML = '<div class="notice bad">' + esc(e.message) + '</div>'; return; }
  const A = c.allowed;
  const btn = (act, label, cls, path, body) => {
    const a = A[act]; if (!a) return '';
    return '<button class="btn ' + cls + '" data-act="' + esc(act) + '" data-path="' + esc(path) + '" data-body="' + esc(JSON.stringify(body || {})) + '" ' + (a.allow ? '' : 'disabled') + ' title="' + esc(a.reason) + '">' + esc(label) + '</button>';
  };
  const showClose = me.role === 'engineer' && ['AUTHORISED', 'REPAIR_EVIDENCE_OK', 'REVIEW_REQUESTED', 'MEASURED'].includes(c.status);
  const actions = [
    A['review.request'].allow ? btn('review.request', 'Request engineer review', 'warn', 'review', { reason: 'Requested from case page' }) : '',
    A['review.authorise'].allow ? btn('review.authorise', 'Authorise repair', 'violet', 'authorise', { note: 'Authorised from case page' }) : '',
    showClose ? btn('case.close', 'Close ticket', 'primary', 'close', { note: 'Closed after evidence review' }) : '',
    A['dispute.open'].allow ? '<button class="btn danger" id="dispute-open">Dispute this closure</button>' : '',
    A['dispute.resolve'].allow ? btn('dispute.resolve', 'Uphold dispute (reopen)', 'danger', 'dispute/resolve', { decision: 'uphold', note: 'Upheld' }) + btn('dispute.resolve', 'Reject dispute', 'btn', 'dispute/resolve', { decision: 'reject', note: 'Rejected' }) : '',
  ].join('');
  const gov = [];
  if (c.review) gov.push('<li><b>Review requested</b> by ' + esc(c.review.requested_by) + ': ' + esc(c.review.reason) + ' <span class="mono">' + when(c.review.requested_at) + '</span></li>');
  if (c.authorisation) gov.push('<li><b>Authorised</b> by ' + esc(c.authorisation.name) + ': ' + esc(c.authorisation.note) + '</li>');
  gov.push('<li><b>After-repair evidence</b>: ' + (c.repair_evidence_ok ? 'verified (visual)' : 'not yet') + '</li>');
  if (c.dispute) gov.push('<li><b>Dispute</b> by ' + esc(c.dispute.opened_by) + ': ' + esc(c.dispute.reason) + (c.dispute.evidence_confirms_crack === true ? ' <b>(new photo confirms a crack)</b>' : c.dispute.evidence_confirms_crack === false ? ' (new photo shows no crack)' : '') + (c.dispute.resolution ? ' | resolved: ' + esc(c.dispute.resolution.decision) : '') + '</li>');
  const canVisit = A['visit.add'].allow;
  app.innerHTML = `
  <p><a href="#/cases">&larr; All cases</a></p>
  <div class="row"><h1>${esc(c.site)}</h1></div>
  <div class="row">${statusChip(c.status)}${sevChip(c.severity)}${c.simulated ? '<span class="status">simulated demo data</span>' : ''}<span class="mono">marker id ${esc(c.marker_id)} | priority ${c.priority_score} (estimated)</span></div>
  <p>${esc(c.description)}</p>
  <section class="grid g2">
    <div class="card"><h2>Governance</h2><ul class="audit">${gov.join('')}</ul><div class="row" id="actions">${actions || '<span class="fine">No actions available for your role right now.</span>'}</div>
      <p class="fine">Buttons are enabled by the server policy (default deny). Hover a disabled button to see why.</p>
      <div id="dispute-box"></div></div>
    <div class="card"><h2>Width over time</h2>${chartSvg(c.visits)}</div>
  </section>
  <h2>Visits</h2>
  <div id="visits">${[...c.visits].reverse().map((v) => `
    <div class="card visit ${c.simulated ? 'sim' : ''}">
      <div class="imgbox">${v.overlay_key ? '<img loading="lazy" src="/api/blob/' + esc(v.overlay_key) + '" alt="Rectified overlay for the ' + esc(v.kind) + ' visit">' : (v.photo_key ? '<img loading="lazy" src="/api/blob/' + esc(v.photo_key) + '" alt="Photo for the ' + esc(v.kind) + ' visit">' : '')}</div>
      <div><div class="row">${statusChip(v.status)}${sevChip(v.severity)}<span class="status">${esc(v.kind.replace('_', ' '))}</span><span class="mono">${when(v.at)} by ${esc(v.by)}</span></div>
      <p><b>${esc(v.guidance)}</b></p>${metricsHtml(v.measurement)}
      ${v.compare ? '<p class="mono">vs previous: width ' + (v.compare.delta_width_mm >= 0 ? '+' : '') + fmt(v.compare.delta_width_mm) + ' mm (&plusmn;' + fmt(v.compare.uncertainty_mm) + '), new crack length ' + fmt(v.compare.new_crack_length_mm, 0) + ' mm' + (v.compare.significant ? ' <b>significant</b>' : '') + '</p>' : ''}
      ${v.repair ? '<p class="mono">repair check: ' + esc(v.repair.explanation) + '</p>' : ''}
      <details><summary>Quality gates and agent trace</summary>${gatesHtml(v.quality)}${traceHtml(v.trace)}</details></div>
    </div>`).join('') || '<p>No visits yet. Add the first photo below.</p>'}</div>
  <section class="grid g2">
    <div class="card"><h2>Add a visit</h2>${canVisit ? `
      <form class="stack" id="visitform">
        <label>Kind <select name="kind"><option value="${c.visits.length ? 'followup' : 'baseline'}">${c.visits.length ? 'Follow-up' : 'Baseline'}</option>${c.authorisation ? '<option value="after_repair">After repair (evidence)</option>' : ''}${c.status === 'DISPUTED' ? '<option value="dispute" selected>Dispute photo</option>' : ''}</select></label>
        <label>Photo (marker id ${esc(c.marker_id)} must be in frame) <input type="file" name="image" accept="image/*" capture="environment" required></label>
        <label>Note <input name="note" maxlength="300"></label>
        <button class="btn primary" type="submit">Upload and assess</button>
      </form>
      <p class="fine"><a href="/api/marker.png?id=${esc(c.marker_id)}" target="_blank" rel="noopener">Print marker ${esc(c.marker_id)}</a> at 100% scale and check the black square is 50 mm.</p>` : '<p>Sign in (demo) to add photos.</p>'}</div>
    <div class="card dark"><h2>Audit log</h2>${c.audit.length ? '<ul class="audit">' + [...c.audit].reverse().map((a) => '<li>' + (a.allowed ? '' : '<b>DENIED </b>') + esc(a.action) + ' | ' + esc(a.name) + ' (' + esc(a.role) + ') | ' + esc(a.reason) + ' <span class="mono">' + when(a.at) + '</span></li>').join('') + '</ul>' : '<p>Sign in to see the audit trail of real cases.</p>'}</div>
  </section>`;
  app.querySelectorAll('#actions button[data-act]').forEach((b) => (b.onclick = async () => {
    try { await api('/api/cases/' + id + '/' + b.dataset.path, { method: 'POST', json: JSON.parse(b.dataset.body) }); toast('Done'); pageCase(id); }
    catch (e) { toast(e.message, true); pageCase(id); }
  }));
  const d = $('#dispute-open');
  if (d) d.onclick = () => {
    $('#dispute-box').innerHTML = '<form class="stack" id="dform"><label>Why do you dispute the closure?<textarea name="reason" required></textarea></label><button class="btn danger" type="submit">Open dispute</button></form>';
    $('#dform').onsubmit = async (e) => { e.preventDefault(); try { await api('/api/cases/' + id + '/dispute', { method: 'POST', json: { reason: new FormData(e.target).get('reason') } }); toast('Dispute opened. Add a new photo.'); pageCase(id); } catch (err) { toast(err.message, true); } };
  };
  const vf = $('#visitform');
  if (vf) vf.onsubmit = async (e) => {
    e.preventDefault(); const b = vf.querySelector('button'); busy(b, true);
    try { const r = await api('/api/cases/' + id + '/visits', { method: 'POST', form: new FormData(vf) }); toast(r.visit.status.replace(/_/g, ' ')); pageCase(id); }
    catch (err) { toast(err.message, true); busy(b, false); }
  };
}

async function pageAbout() {
  const [t, pol] = await Promise.all([api('/api/transparency'), api('/api/policy')]);
  const li = (a) => '<ul>' + a.map((x) => '<li>' + esc(x) + '</li>').join('') + '</ul>';
  app.innerHTML = `
  <h1>How HAIRLINE works</h1>
  <section class="grid g3">
    <div class="card"><h3>1. Marker</h3><p>A printed 50 mm ArUco marker gives true scale and a fixed reference frame on the wall. OpenCV detects it and builds a homography.</p></div>
    <div class="card"><h3>2. Gates</h3><p>Resolution, tilt, sharpness, glare, exposure and coverage are measured first. A blocking gate stops the measurement and the agent says how to retake the photo.</p></div>
    <div class="card"><h3>3. Measure</h3><p>The wall is rectified to millimetres, cracks are segmented, and width comes from a distance transform on the skeleton with a half-maximum refinement.</p></div>
    <div class="card"><h3>4. Compare</h3><p>Because the marker defines the frame, visit A and visit B overlay directly. Growth beyond the error bar escalates.</p></div>
    <div class="card"><h3>5. Govern</h3><p>The agent drafts a review request. Only an engineer can authorise, and closing needs after-repair evidence. Residents can dispute.</p></div>
    <div class="card"><h3>6. Prove</h3><p>Every action is in an audit log, including denied ones. The policy below is enforced by the server.</p></div>
  </section>
  <section class="grid g2">
    <div class="card"><h2>Simulated vs estimated</h2><h3>Simulated</h3>${li(t.simulated)}<h3>Estimated</h3>${li(t.estimated)}<h3>Not done yet</h3>${li(t.not_done)}</div>
    <div class="card dark"><h2>Authorisation policy</h2><p class="fine">Default deny. Forbid beats permit.</p><ul>${pol.rules.map((r) => '<li><span class="mono">' + esc(r.id) + '</span> ' + esc(r.effect) + ' ' + esc((r.roles || []).join('/')) + ' &rarr; ' + esc(r.actions.join(', ')) + (r.when ? ' when ' + esc(r.when.join(' + ')) : '') + (r.unless ? ' unless ' + esc(r.unless.join(' + ')) : '') + '</li>').join('')}</ul></div>
  </section>
  <section class="card"><h2>Runtime</h2><p class="mono">OpenCV ${esc(health.opencv)} (major ${esc(health.opencv_major)}) | planner ${esc(health.planner)} | store ${esc(health.store)} | blobs ${esc(health.blobs)} | auth ${esc(health.auth_mode)}${health.release ? ' | build ' + esc(health.release) : ''}</p></section>`;
}

/* ---------------------------------------------------------------- router */
async function route() {
  const h = location.hash || '#/try';
  document.querySelectorAll('nav a').forEach((a) => a.removeAttribute('aria-current'));
  let page = 'try';
  try {
    if (h.startsWith('#/cases') || h.startsWith('#/case/')) { page = 'cases'; }
    else if (h.startsWith('#/about')) { page = 'about'; }
    const n = document.querySelector('nav a[data-nav="' + page + '"]'); if (n) n.setAttribute('aria-current', 'page');
    app.innerHTML = '<p><span class="spin"></span> Loading</p>';
    if (h.startsWith('#/case/')) await pageCase(h.slice(7));
    else if (page === 'cases') await pageCases();
    else if (page === 'about') await pageAbout();
    else await pageTry();
  } catch (e) { app.innerHTML = '<div class="notice bad">' + esc(e.message) + '</div>'; }
  window.scrollTo(0, 0);
}
window.addEventListener('hashchange', route);
(async () => { await Promise.all([loadMe(), loadHealth(), countVisit()]); route(); })();
})();
