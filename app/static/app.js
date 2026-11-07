// AquaGuard dashboard: plain JavaScript client for the /api/v1 contract.
// Text from the API is inserted with textContent only (never as HTML).
const $ = (id) => document.getElementById(id);
let token = null, me = null, conversation = crypto.randomUUID(), selectedCase = null;

async function api(path, opts = {}) {
  const res = await fetch('/api/v1' + path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}) },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error ? body.error.message : res.statusText);
  return body;
}

function addMsg(box, author, text, note) {
  const d = document.createElement('div');
  d.className = 'msg ' + author;
  d.textContent = text;
  if (note) { const s = document.createElement('small'); s.textContent = note; d.appendChild(s); }
  box.appendChild(d); box.scrollTop = box.scrollHeight;
  return d;
}

function addFeedback(msgEl, messageId) {
  const bar = document.createElement('div'); bar.className = 'fb';
  const mk = (label, helpful) => {
    const b = document.createElement('button'); b.className = 'ghost tiny'; b.textContent = label;
    b.onclick = async () => {
      try {
        await api(`/messages/${messageId}/feedback`, { method: 'POST', body: JSON.stringify({ helpful }) });
        bar.textContent = 'Thanks — feedback sent for review.';
      } catch (e) { bar.textContent = e.message; }
    };
    return b;
  };
  bar.append(mk('Helpful', true), mk('Not helpful', false));
  msgEl.appendChild(bar);
}

$('signin').onclick = async () => {
  try {
    const t = await api('/auth/token', { method: 'POST', body: JSON.stringify({ username: $('u').value, password: $('p').value }) });
    token = t.access_token; me = await api('/me');
    $('login').hidden = true; $('who').textContent = me.username + ' · ' + me.role;
    if (me.role === 'agent') { $('agent').hidden = false; loadCases(); setInterval(loadCases, 5000); }
    else { $('customer').hidden = false; fillTanks(); }
  } catch (e) { $('loginerr').textContent = e.message; }
};

function fillTanks() {
  $('tank').innerHTML = '';
  me.tanks.forEach((t) => { const o = document.createElement('option'); o.value = t.tank_id; o.textContent = t.name; $('tank').appendChild(o); });
  $('tank').onchange = () => { conversation = crypto.randomUUID(); $('log').innerHTML = ''; refresh(); };
  refresh(); setInterval(refresh, 5000);
}

async function refresh() {
  const tank = $('tank').value; if (!tank) return;
  const h = await api(`/tanks/${tank}/readings?limit=60`);
  const items = h.items.slice().reverse();
  const last = items[items.length - 1];
  $('stats').innerHTML = '';
  const add = (v, l) => { const d = document.createElement('div'); d.className = 'stat'; const b = document.createElement('b'); b.textContent = v; const s = document.createElement('span'); s.textContent = l; d.append(b, s); $('stats').appendChild(d); };
  add(last ? last.temperature_c.toFixed(1) + ' °C' : '—', 'Temperature');
  add(last ? last.ph.toFixed(2) : '—', 'pH');
  add(last ? last.water_level_pct.toFixed(0) + '%' : '—', 'Water level');
  add(String(h.items.length), 'Readings shown');
  const badge = $('badge'); badge.className = 'badge ' + (last ? last.threshold_status : '');
  badge.textContent = last ? (last.threshold_status === 'alert' ? 'Threshold alert' : 'Within limits') : 'No data';
  draw(items);
}

function draw(items) {
  const c = $('chart'), g = c.getContext('2d'), W = c.width, H = c.height, pad = 34;
  g.clearRect(0, 0, W, H);
  if (items.length < 2) { g.fillStyle = '#8fb0c2'; g.fillText('Waiting for readings…', 20, 30); return; }
  const ys = items.map((r) => r.temperature_c);
  const lo = Math.min(...ys, 23) - 0.5, hi = Math.max(...ys, 28) + 0.5;
  const X = (i) => pad + (i / (items.length - 1)) * (W - pad - 10), Y = (v) => H - pad + 10 - ((v - lo) / (hi - lo)) * (H - pad - 20);
  g.fillStyle = 'rgba(46,196,182,.10)'; g.fillRect(pad, Y(27), W - pad - 10, Y(24) - Y(27));
  g.strokeStyle = '#1c3a4f'; g.fillStyle = '#8fb0c2'; g.font = '11px system-ui';
  for (let v = Math.ceil(lo); v <= hi; v++) { g.beginPath(); g.moveTo(pad, Y(v)); g.lineTo(W - 10, Y(v)); g.stroke(); g.fillText(v + '°', 4, Y(v) + 4); }
  g.strokeStyle = '#2ec4b6'; g.lineWidth = 2.5; g.beginPath();
  items.forEach((r, i) => (i ? g.lineTo(X(i), Y(r.temperature_c)) : g.moveTo(X(i), Y(r.temperature_c)))); g.stroke();
  items.forEach((r, i) => { if (r.threshold_status === 'alert') { g.fillStyle = '#ef476f'; g.beginPath(); g.arc(X(i), Y(r.temperature_c), 3.5, 0, 7); g.fill(); } });
}

async function ask(text) {
  addMsg($('log'), 'customer', text);
  try {
    const r = await api(`/tanks/${$('tank').value}/messages`, { method: 'POST', body: JSON.stringify({ message_id: crypto.randomUUID(), conversation_id: conversation, text }) });
    $('model').textContent = r.model_version + ' · ' + r.anomaly_status.replace('_', ' ');
    const el = addMsg($('log'), 'assistant', r.reply, r.handoff_required ? 'Escalated to a human agent (case ' + r.case_id.slice(0, 8) + ')' : 'Trend: ' + r.anomaly_status.replace('_', ' '));
    if (r.model_version !== 'fallback') addFeedback(el, r.assistant_message_id);
  } catch (e) { addMsg($('log'), 'assistant', 'Error: ' + e.message); }
}
$('send').onclick = () => { const t = $('q').value.trim(); if (t) { $('q').value = ''; ask(t); } };
$('q').onkeydown = (e) => { if (e.key === 'Enter') $('send').onclick(); };
$('human').onclick = () => ask('Please have a human agent review this.');

async function loadCases() {
  const r = await api('/cases?status=open');
  $('cases').innerHTML = '';
  if (!r.items.length) { const li = document.createElement('li'); li.textContent = 'No open cases'; $('cases').appendChild(li); }
  r.items.forEach((c) => {
    const li = document.createElement('li'); li.textContent = c.reason;
    const s = document.createElement('small'); s.textContent = new Date(c.created_at).toLocaleString() + ' · ' + c.case_id.slice(0, 8); li.appendChild(s);
    if (selectedCase && selectedCase.case_id === c.case_id) li.className = 'sel';
    li.onclick = () => { selectedCase = c; loadTranscript(); loadCases(); };
    $('cases').appendChild(li);
  });
}
async function loadTranscript() {
  const r = await api(`/conversations/${selectedCase.conversation_id}/messages`);
  $('tlog').innerHTML = ''; r.items.forEach((m) => addMsg($('tlog'), m.author, m.text, m.author));
}
$('rsend').onclick = async () => {
  if (!selectedCase || !$('rtext').value.trim()) return;
  await api(`/cases/${selectedCase.case_id}/replies`, { method: 'POST', body: JSON.stringify({ reply_id: crypto.randomUUID(), text: $('rtext').value.trim(), close_case: $('close').checked }) });
  $('rtext').value = ''; await loadTranscript(); if ($('close').checked) selectedCase = null; loadCases();
};
