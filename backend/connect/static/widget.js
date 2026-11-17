/* Adion Connect widget: add a scoped AI assistant to any website.
 *   <script src="https://YOUR-ADION/api/connect/widget.js"></script>
 *   <script>Adion.init({ key: "pk_...", getTicket: async () => "...", getUserToken: () => "..." })</script>
 * Everything runs in a Shadow DOM, so it cannot clash with the page's styles. */
(function () {
  'use strict';
  var script = document.currentScript || (function () { var s = document.getElementsByTagName('script'); return s[s.length - 1]; })();
  var BASE = (function () { try { var u = new URL(script.src); return u.origin + '/api/connect/v1'; } catch (e) { return '/api/connect/v1'; } })();
  var actions = {};
  var state = { cfg: null, opts: null, conv: '', busy: false, open: false, pending: [], listening: false, speak: false };
  var root, panel, list, input, pendBox, btn, micBtn, spkBtn;

  function api(path, body) {
    return fetch(BASE + path, { method: body ? 'POST' : 'GET', headers: { 'Authorization': 'Bearer ' + state.opts.key, 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined }).then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'Request failed'); return j; }); });
  }
  function ids() {
    var o = state.opts;
    return Promise.all([o.getTicket ? o.getTicket() : null, o.getUserToken ? o.getUserToken() : null]).then(function (v) {
      var out = { conversationId: state.conv || undefined };
      if (v[0]) out.ticket = v[0]; if (v[1]) out.userToken = v[1];
      return out;
    });
  }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  function add(role, text) {
    var m = el('div', 'm ' + role, text); list.appendChild(m); list.scrollTop = list.scrollHeight;
    if (role === 'assistant' && state.speak && text) say(text);
    return m;
  }
  function say(text) {
    try { if (!('speechSynthesis' in window)) return; window.speechSynthesis.cancel(); var u = new SpeechSynthesisUtterance(text); if (state.lang) u.lang = state.lang; window.speechSynthesis.speak(u); } catch (e) { /* no voice */ }
  }
  function setBusy(b) { state.busy = b; if (btn_send) btn_send.disabled = b; panel.classList.toggle('busy', b); }

  function renderPending() {
    pendBox.innerHTML = '';
    state.pending.filter(function (p) { return p.needsConfirm; }).forEach(function (p) {
      var card = el('div', 'card'); card.appendChild(el('div', 'ct', 'Please confirm')); card.appendChild(el('div', 'cs', p.summary));
      var row = el('div', 'row');
      var ok = el('button', 'ok', 'Confirm'); var no = el('button', 'no', 'Cancel');
      ok.onclick = function () { decide(p, true); }; no.onclick = function () { decide(p, false); };
      row.appendChild(ok); row.appendChild(no); card.appendChild(row); pendBox.appendChild(card);
    });
  }

  function handle(res) {
    state.conv = res.conversationId || state.conv; if (res.lang) state.lang = res.lang;
    if (res.reply) add('assistant', res.reply);
    var open = res.pending || [];
    var auto = open.filter(function (p) { return p.kind === 'client' && !p.needsConfirm; });
    if (!auto.length) { state.pending = open; renderPending(); return Promise.resolve(); }
    return Promise.all(auto.map(function (p) {
      var fn = actions[p.name];
      if (!fn) return { callId: p.callId, error: 'This app has no handler for ' + p.name };
      return Promise.resolve().then(function () { return fn(p.args); }).then(function (r) { return { callId: p.callId, result: r }; },
        function (e) { return { callId: p.callId, error: String((e && e.message) || e) }; });
    })).then(function (results) { return ids().then(function (id) { id.results = results; return api('/chat/result', id); }); }).then(handle);
  }

  function send(text) {
    text = (text || input.value).trim(); if (!text || state.busy) return;
    input.value = ''; add('user', text); setBusy(true); state.pending = []; renderPending();
    var typing = add('assistant typing', '…');
    ids().then(function (id) { id.message = text; return api('/chat', id); }).then(function (res) { typing.remove(); return handle(res); })
      .catch(function (e) { typing.remove(); add('assistant err', e.message); }).then(function () { setBusy(false); });
  }

  function decide(p, approve) {
    state.pending = []; renderPending(); setBusy(true);
    var run = (p.kind === 'client' && approve)
      ? Promise.resolve().then(function () { return actions[p.name](p.args); }).then(function (r) { return { callId: p.callId, result: r }; }, function (e) { return { callId: p.callId, error: String((e && e.message) || e) }; })
          .then(function (d) { return ids().then(function (id) { id.results = [d]; return api('/chat/result', id); }); })
      : ids().then(function (id) { id.decisions = [{ callId: p.callId, approve: approve }]; return api('/chat/confirm', id); });
    run.then(handle).catch(function (e) { add('assistant err', e.message); }).then(function () { setBusy(false); });
  }

  function listen() {
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { add('assistant err', 'Voice input is not supported in this browser.'); return; }
    var r = new SR(); r.lang = (state.cfg && state.cfg.language && state.cfg.language !== 'auto') ? state.cfg.language : (navigator.language || 'en-US');
    r.interimResults = false; state.listening = true; micBtn.classList.add('on');
    r.onresult = function (e) { send(e.results[0][0].transcript); };
    r.onend = function () { state.listening = false; micBtn.classList.remove('on'); }; r.onerror = r.onend;
    try { r.start(); } catch (e) { r.onend(); }
  }

  var CSS = ':host{all:initial}*{box-sizing:border-box;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif}' +
    '.fab{position:fixed;bottom:20px;right:20px;width:56px;height:56px;border-radius:50%;border:0;cursor:pointer;color:#fff;font-size:24px;box-shadow:0 6px 24px rgba(0,0,0,.35);z-index:2147483000}' +
    '.panel{position:fixed;bottom:88px;right:20px;width:min(380px,calc(100vw - 24px));height:min(560px,calc(100vh - 110px));background:#0f172a;color:#e2e8f0;border:1px solid #334155;border-radius:16px;display:none;flex-direction:column;overflow:hidden;box-shadow:0 12px 40px rgba(0,0,0,.45);z-index:2147483000}' +
    '.panel.open{display:flex}.hd{padding:12px 14px;border-bottom:1px solid #1e293b;display:flex;align-items:center;gap:8px;font-weight:600;font-size:14px}.hd span{flex:1}' +
    '.hd button{background:none;border:0;color:#94a3b8;cursor:pointer;font-size:16px}.hd button.on{color:#f43f5e}' +
    '.list{flex:1;overflow:auto;padding:12px;display:flex;flex-direction:column;gap:8px}.m{max-width:86%;padding:8px 12px;border-radius:14px;font-size:14px;line-height:1.45;white-space:pre-wrap}' +
    '.m.user{align-self:flex-end;color:#fff}.m.assistant{align-self:flex-start;background:#1e293b}.m.typing{opacity:.6}.m.err{background:#450a0a;color:#fecaca}' +
    '.card{margin:8px 12px;padding:10px 12px;border:1px solid #f59e0b;border-radius:12px;background:#1c1917}.ct{font-size:12px;color:#fbbf24;margin-bottom:4px}.cs{font-size:13px;margin-bottom:8px}' +
    '.row{display:flex;gap:8px}.row button{flex:1;border:0;border-radius:8px;padding:7px;cursor:pointer;font-size:13px;color:#fff}.ok{background:#059669}.no{background:#475569}' +
    '.ft{display:flex;gap:6px;padding:10px;border-top:1px solid #1e293b}.ft input{flex:1;background:#020617;border:1px solid #334155;color:#e2e8f0;border-radius:10px;padding:9px 11px;font-size:14px;outline:none}' +
    '.ft button{border:0;border-radius:10px;padding:0 14px;color:#fff;cursor:pointer}.ft button:disabled{opacity:.5}.ft .mic{background:#334155;padding:0 10px}.ft .mic.on{background:#e11d48}' +
    '.pw{font-size:10px;text-align:center;color:#64748b;padding:0 0 6px}';

  function build() {
    var color = state.opts.color || '#0891b2';
    var host = document.createElement('div'); document.body.appendChild(host);
    root = host.attachShadow({ mode: 'open' });
    var st = el('style'); st.textContent = CSS + '.fab,.m.user,.ft .send{background:' + color + '}'; root.appendChild(st);
    btn = el('button', 'fab', '💬'); btn.title = 'Chat'; root.appendChild(btn);
    panel = el('div', 'panel'); root.appendChild(panel);
    var hd = el('div', 'hd'); hd.appendChild(el('span', '', state.cfg.name || 'Assistant'));
    spkBtn = el('button', '', '🔈'); spkBtn.title = 'Speak replies'; spkBtn.onclick = function () { state.speak = !state.speak; spkBtn.textContent = state.speak ? '🔊' : '🔈'; if (!state.speak && window.speechSynthesis) window.speechSynthesis.cancel(); };
    var nw = el('button', '', '＋'); nw.title = 'New chat'; nw.onclick = function () { state.conv = ''; list.innerHTML = ''; state.pending = []; renderPending(); greet(); };
    var x = el('button', '', '✕'); x.onclick = function () { toggle(false); };
    hd.appendChild(spkBtn); hd.appendChild(nw); hd.appendChild(x); panel.appendChild(hd);
    list = el('div', 'list'); panel.appendChild(list);
    pendBox = el('div'); panel.appendChild(pendBox);
    var ft = el('div', 'ft'); input = el('input'); input.placeholder = 'Type or press the mic…';
    input.onkeydown = function (e) { if (e.key === 'Enter') send(); };
    micBtn = el('button', 'mic', '🎤'); micBtn.onclick = listen;
    var sb = el('button', 'send', 'Send'); sb.onclick = function () { send(); }; btn_send = sb;
    ft.appendChild(input); ft.appendChild(micBtn); ft.appendChild(sb); panel.appendChild(ft);
    panel.appendChild(el('div', 'pw', 'Powered by Adion'));
    btn.onclick = function () { toggle(); };
    greet();
  }
  var btn_send;
  function greet() { add('assistant', state.cfg.greeting || ('Hi! I can help you with ' + (state.cfg.name || 'this app') + '.')); }
  function toggle(v) { state.open = v == null ? !state.open : v; panel.classList.toggle('open', state.open); if (state.open) input.focus(); }

  window.Adion = {
    init: function (opts) {
      if (!opts || !opts.key) { console.error('Adion.init needs a key'); return; }
      state.opts = opts;
      fetch(BASE + '/config', { headers: { 'Authorization': 'Bearer ' + opts.key } }).then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || 'Adion could not start'); return j; }); })
        .then(function (cfg) { state.cfg = cfg; build(); }).catch(function (e) { console.error('Adion:', e.message); });
    },
    registerAction: function (name, fn) { actions[name] = fn; },
    open: function () { if (panel) toggle(true); }, close: function () { if (panel) toggle(false); }, send: function (t) { send(t); }
  };
})();
