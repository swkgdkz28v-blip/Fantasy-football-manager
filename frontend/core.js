/* Fantasy Manager — core.js (v10.33)
   Loaded first. Holds: React shortcuts, API, shared result components, the feature registry,
   and the app shell (tabs, lists, feature screens, settings). Tab files (tabs/*.js) register their
   features with FF.tab(...) and are loaded after this file. */

const { useState, useEffect, useCallback, useRef } = React;
const e = React.createElement;
const APP_VERSION = 'v10.33';

// ── STORAGE (never throws — private mode / blocked storage just means no memory) ─
const store = {
  get(k, d) { try { const v = localStorage.getItem('ff.' + k); return v == null ? d : JSON.parse(v); } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem('ff.' + k, JSON.stringify(v)); } catch (_) {} },
};

// ── API ───────────────────────────────────────────────────────────────────────
const API = {
  async req(method, path, body) {
    const r = await fetch(`/api${path}`, {
      method, headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!r.ok) { let d = ''; try { d = (await r.json()).detail || ''; } catch (_) {} throw new Error(d || `Server error ${r.status}`); }
    return r.json();
  },
  post(path, body) { return this.req('POST', path, body); },
  get(path) { return this.req('GET', path); },
};

// ── SHARED RESULT COMPONENTS (used by the feature screens in tabs/*.js) ──────
// ── HELPERS ───────────────────────────────────────────────────────────────────
const POS_CLASS = pos => ({ QB:'pos-QB', RB:'pos-RB', WR:'pos-WR', TE:'pos-TE', K:'pos-K', DEF:'pos-DEF', DL:'pos-DL', LB:'pos-LB', DB:'pos-DB' }[pos] || '');

const POS_COLORS = { QB:'var(--accent4)', RB:'var(--accent)', WR:'var(--purple)', TE:'var(--accent3)', K:'var(--accent2)', DEF:'var(--text3)' };

function PosBadge({ pos }) {
  return e('span', { className: `pos ${POS_CLASS(pos)}` }, pos);
}

function Tag({ color, children }) {
  return e('span', { className: `tag tag-${color}` }, children);
}

function Card({ children, style, borderColor }) {
  return e('div', {
    className: 'card',
    style: { ...(borderColor ? { borderLeft: `3px solid ${borderColor}` } : {}), ...style }
  }, children);
}

function StatTile({ value, label, color }) {
  return e('div', { className: 'stat-tile' },
    e('div', { className: 'val', style: { color: color || 'var(--text)' } }, value),
    e('div', { className: 'lbl' }, label)
  );
}

function BarRow({ label, score, color, maxScore = 5 }) {
  return e('div', { className: 'bar-row' },
    e('span', { className: 'bar-label' }, label),
    e('div', { className: 'bar-track' },
      e('div', { className: 'bar-fill', style: { width: `${(score / maxScore) * 100}%`, background: color } })
    ),
    e('span', { className: 'bar-score', style: { color } }, score)
  );
}

function PlayerRow({ player, showYtd }) {
  const ptColor = player.pts >= 20 ? 'var(--accent)' : player.pts >= 10 ? 'var(--text2)' : 'var(--accent2)';
  return e('div', { className: 'player-row' },
    e(PosBadge, { pos: player.position }),
    e('span', { className: 'player-name' }, player.name),
    e('span', { className: 'player-team' }, player.team),
    player.injury_status && e(Tag, { color: 'red' }, player.injury_status.toUpperCase()),
    e('span', { className: 'player-pts', style: { color: ptColor } },
      showYtd && player.ytd_avg ? `${player.pts}/${player.ytd_avg}` : player.pts
    )
  );
}

function Loading({ message }) {
  return e('div', { className: 'loading' },
    e('div', { className: 'spinner' }),
    e('div', { className: 'loading-msg' }, message || 'Loading…')
  );
}

function Alert({ type, title, children }) {
  return e('div', { className: `alert alert-${type || 'info'}` },
    title && e('h3', null, title),
    children
  );
}

// Renders lineup moves from the backend as stacked, phone-readable rows.
// ptsKey = main number; subKey = season average (shown with ±sd and GP when present).
function MovesList({ moves, ptsKey = 'pts', subKey, title = '🔄 Moves To Make', verb }) {
  if (!moves?.length) return null;
  const v = verb || { start: 'START', move: 'MOVE', bench: 'BENCH' };
  const STYLE = {
    start: { bg: 'rgba(0,229,160,0.06)',  border: 'rgba(0,229,160,0.35)',  color: 'var(--accent)',  icon: '▲' },
    move:  { bg: 'rgba(92,158,255,0.06)', border: 'rgba(92,158,255,0.35)', color: 'var(--accent4)', icon: '↔' },
    bench: { bg: 'rgba(255,92,92,0.06)',  border: 'rgba(255,92,92,0.35)',  color: 'var(--accent2)', icon: '▼' },
  };
  const stat = (label, value, color) => e('div', { style: { display: 'flex', flexDirection: 'column', minWidth: 54 } },
    e('span', { style: { fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: 0.5 } }, label),
    e('span', { style: { fontSize: 15, fontWeight: 700, color: color || 'var(--text)' } }, value));
  return e('div', { style: { marginBottom: 12 } },
    e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent3)', marginBottom: 6 } }, title),
    moves.map((m, i) => {
      const st = STYLE[m.type] || STYLE.move;
      const p = m.player;
      const where = m.type === 'start' ? `into ${m.to_slot}` : m.type === 'move' ? `${m.from_slot} → ${m.to_slot}` : `out of ${m.from_slot}`;
      const main = p[ptsKey] ?? p.pts;
      const hasAvg = subKey && p[subKey] != null && p.gp > 0;
      return e('div', { key: i, style: { padding: '10px 12px', background: st.bg, border: `1px solid ${st.border}`, borderRadius: 10, marginBottom: 6 } },
        // line 1: action + player
        e('div', { style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 } },
          e('span', { style: { fontSize: 11, fontWeight: 800, color: st.color, padding: '2px 7px', border: `1px solid ${st.color}`, borderRadius: 5, whiteSpace: 'nowrap' } }, `${st.icon} ${v[m.type]}`),
          e(PosBadge, { pos: p.position }),
          e('span', { style: { fontSize: 15, fontWeight: 700, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name)
        ),
        // line 2: team + slot route
        e('div', { style: { fontSize: 12, color: 'var(--text2)', marginBottom: hasAvg || main != null ? 8 : 0 } }, `${p.team || 'FA'} · ${where}`),
        // line 3: numbers, spaced out
        e('div', { style: { display: 'flex', gap: 18, flexWrap: 'wrap' } },
          main != null && stat(subKey ? 'Proj' : 'Pts', main, st.color),
          hasAvg && stat('Avg', `${p[subKey]}${p.std != null ? ` ±${p.std}` : ''}`),
          hasAvg && stat('Games', p.gp),
          subKey && p.gp === 0 && stat('Games', '0'),
          subKey && p.blended != null && hasAvg && stat('Floor', p.blended, 'var(--accent3)')
        )
      );
    })
  );
}

// ── shared small helpers for the offseason/portfolio views ───────────────────
const secTitle = (text, color) => e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: color || 'var(--text3)', marginBottom: 8 } }, text);

const lineRow = (key, left, right, rightColor) => e('div', { key, style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, padding: '6px 0', borderBottom: '1px solid var(--border)' } },
  e('span', { style: { flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, left),
  e('span', { style: { whiteSpace: 'nowrap', fontWeight: 700, color: rightColor || 'var(--text2)' } }, right));

function GenericView({ data, title }) {
  return e('pre', { style: { fontSize: 11, color: 'var(--text2)', overflow: 'auto', whiteSpace: 'pre-wrap' } }, JSON.stringify(data, null, 2));
}


// ── FEATURE REGISTRY ──────────────────────────────────────────────────────────
// Each tab file calls FF.tab({ id, label, icon, groups: [{ label, features: [...] }] }).
// A feature: { id, title, sub, icon, tint, endpoint, view, viewProps?, needs?: 'league'|'player', badge?: data => {n, color} }
const FF = {
  tabs: [],
  tab(def) { this.tabs.push(def); },
  feature(id) {
    for (const t of this.tabs) for (const g of t.groups) for (const f of g.features) if (f.id === id) return { ...f, tabId: t.id };
    return null;
  },
};
const TAB_ORDER = ['today', 'lineups', 'roster', 'dynasty', 'leagues'];
// Badge helper for tab files: count → coloured pill on the list row (only after the feature has run this session)
const cnt = (n, color) => n == null ? null : (n === 0 ? { n: '✓', color: 'green' } : { n, color });


const NEEDS = {
  league: { field: 'league_name', label: 'Which league?', placeholder: 'League name (full or partial)' },
  player: { field: 'player_name', label: 'Which player?', placeholder: 'e.g. Bijan Robinson' },
};
const resultKey = (f, week, input) => `${f.id}|${week}|${(input || '').trim().toLowerCase()}`;

// ── SMALL SHELL PIECES ────────────────────────────────────────────────────────
function Avatar({ me, username, onClick }) {
  const initials = ((me && me.display_name) || username || '?').slice(0, 2).toUpperCase();
  return e('div', { className: 'avatar', onClick, role: 'button', 'aria-label': 'Settings' },
    me && me.avatar ? e('img', { src: `https://sleepercdn.com/avatars/thumbs/${me.avatar}`, alt: '' }) : initials);
}

function FeatureRow({ f, badge, onOpen }) {
  return e('button', { className: 'row', onClick: () => onOpen(f) },
    e('div', { className: `row-icon tint-${f.tint || 'blue'}` }, f.icon),
    e('div', { className: 'row-text' },
      e('span', { className: 'row-title' }, f.title),
      f.sub && e('span', { className: 'row-sub' }, f.sub)),
    badge && badge.n != null && e('span', { className: `row-badge badge-${badge.color || 'gray'}` }, badge.n),
    e('span', { className: 'row-chev' }, '›'));
}

function Sheet({ onClose, children }) {
  return e('div', { className: 'sheet-backdrop', onClick: onClose },
    e('div', { className: 'sheet', onClick: ev => ev.stopPropagation() }, e('div', { className: 'sheet-grip' }), children));
}

function WeekSheet({ week, currentWeek, onPick, onClose }) {
  return e(Sheet, { onClose },
    e('div', { className: 'sheet-title' }, 'Week'),
    e('div', { className: 'week-grid' },
      Array.from({ length: 18 }, (_, i) => i + 1).map(w => e('button', {
        key: w, className: `week-cell${w === week ? ' on' : ''}${w === currentWeek ? ' now' : ''}`,
        onClick: () => { onPick(w); onClose(); },
      }, w))),
    e('div', { className: 'sheet-note' }, `Blue outline = this week (${currentWeek}). Every feature uses the week you pick here.`));
}

function SettingsSheet({ username, me, onSave, onClearCache, onClose }) {
  const [name, setName] = useState(username || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const save = async () => {
    if (!name.trim()) return;
    setBusy(true); setErr(null);
    try { await onSave(name.trim()); onClose(); } catch (ex) { setErr(ex.message); } finally { setBusy(false); }
  };
  return e(Sheet, { onClose },
    e('div', { className: 'sheet-title' }, 'Settings'),
    e('div', { className: 'sheet-section' },
      e('div', { className: 'ask', style: { marginBottom: 0 } },
        e('label', null, 'Sleeper username'),
        e('div', { className: 'ask-row' },
          e('input', { className: 'field', value: name, autoCapitalize: 'none', autoCorrect: 'off', spellCheck: false,
                       onChange: ev => setName(ev.target.value), onKeyDown: ev => ev.key === 'Enter' && save() }),
          e('button', { className: 'primary', onClick: save, disabled: busy }, busy ? '…' : 'Save')),
        err && e('div', { style: { color: 'var(--accent2)', fontSize: 13, marginTop: 8 } }, err),
        me && e('div', { className: 'sheet-note' }, `Signed in as ${me.display_name} · ${me.leagues} leagues in ${me.season}`))),
    e('div', { className: 'sheet-section' },
      e('button', { className: 'secondary', style: { width: '100%' }, onClick: () => { onClearCache(); onClose(); } }, 'Clear saved results'),
      e('div', { className: 'sheet-note' }, 'Results are kept while the app is open so switching tabs is instant. Pull fresh data with ↻ on any screen.')),
    e('div', { className: 'sheet-note' }, 'Tip: in Safari tap Share → Add to Home Screen to open this full-screen like an app.'),
    e('div', { className: 'version' }, `Fantasy Manager ${APP_VERSION}`));
}

// ── FEATURE SCREEN ────────────────────────────────────────────────────────────
function FeatureScreen({ f, week, entry, input, setInput, onRun, onBack, isFav, onToggleFav, leagues }) {
  const need = f.needs ? NEEDS[f.needs] : null;
  const View = f.view;
  const body = () => {
    if (!entry) return need ? null : e(Loading, { message: 'Starting…' });
    if (entry.loading) return e(Loading, { message: `Checking ${leagues ? leagues + ' leagues' : 'your leagues'}…\nWeek ${week}` });
    if (entry.error) return e(Alert, { type: 'error', title: 'Something went wrong' },
      e('p', null, entry.error),
      e('button', { className: 'secondary', style: { marginTop: 10 }, onClick: onRun }, 'Try again'));
    if (!entry.data) return null;
    return View ? e(View, { data: entry.data, ...(f.viewProps || {}) }) : e(GenericView, { data: entry.data });
  };
  return e('div', null,
    e('div', { className: 'nav-header' },
      e('button', { className: 'nav-btn', onClick: onBack }, '‹ Back'),
      e('div', { className: 'nav-title' }, f.title),
      e('button', { className: 'nav-btn', onClick: onToggleFav, 'aria-label': 'Favorite' }, isFav ? '★' : '☆'),
      e('button', { className: 'nav-btn', onClick: onRun, disabled: !!(entry && entry.loading) || (need && !input.trim()), 'aria-label': 'Refresh' }, '↻')),
    e('div', { className: 'screen' },
      need && e('form', { className: 'ask', onSubmit: ev => { ev.preventDefault(); if (input.trim()) onRun(); } },
        e('label', null, need.label),
        e('div', { className: 'ask-row' },
          e('input', { className: 'field', value: input, placeholder: need.placeholder, autoCapitalize: 'words', autoCorrect: 'off',
                       onChange: ev => setInput(ev.target.value) }),
          e('button', { className: 'primary', type: 'submit', disabled: !input.trim() || !!(entry && entry.loading) }, 'Go'))),
      entry && entry.at && !entry.loading && e('div', { className: 'screen-meta' },
        `Week ${week} · updated ${new Date(entry.at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`),
      body()));
}

// ── TAB ROOT (grouped list) ───────────────────────────────────────────────────
function TabRoot({ tab, me, username, week, onWeek, onSettings, onOpen, badgeFor, favorites }) {
  const favFeatures = tab.id === 'today' ? favorites.map(id => FF.feature(id)).filter(Boolean) : [];
  return e('div', null,
    e('div', { className: 'big-header' },
      e('div', { className: 'big-title' }, tab.label),
      e(Avatar, { me, username, onClick: onSettings })),
    e('div', { className: 'chips' },
      e('button', { className: 'chip on', onClick: onWeek }, `Week ${week} ▾`),
      me && e('div', { className: 'chip' }, `${me.leagues} leagues`),
      me && e('div', { className: 'chip' }, me.display_name)),
    favFeatures.length > 0 && e('div', null,
      e('div', { className: 'group-label' }, '★ Favorites'),
      e('div', { className: 'group' }, favFeatures.map(f => e(FeatureRow, { key: f.id, f, badge: badgeFor(f), onOpen })))),
    tab.groups.map(g => e('div', { key: g.label },
      e('div', { className: 'group-label' }, g.label),
      e('div', { className: 'group' }, g.features.map(f => e(FeatureRow, { key: f.id, f, badge: badgeFor(f), onOpen }))))),
    e('div', { className: 'version' }, `Fantasy Manager ${APP_VERSION}`));
}

function Welcome({ onSave }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const go = async ev => {
    ev.preventDefault(); if (!name.trim()) return;
    setBusy(true); setErr(null);
    try { await onSave(name.trim()); } catch (ex) { setErr(ex.message); setBusy(false); }
  };
  return e('div', { className: 'welcome' },
    e('div', { style: { fontSize: 54, marginBottom: 6 } }, '🏈'),
    e('h1', null, 'Fantasy Manager'),
    e('p', null, 'Enter your Sleeper username to load your leagues. It’s saved on this device.'),
    e('form', { className: 'ask', onSubmit: go },
      e('label', null, 'Sleeper username'),
      e('div', { className: 'ask-row' },
        e('input', { className: 'field', value: name, autoFocus: true, autoCapitalize: 'none', autoCorrect: 'off', spellCheck: false,
                     onChange: ev => setName(ev.target.value) }),
        e('button', { className: 'primary', type: 'submit', disabled: busy }, busy ? '…' : 'Go'))),
    err && e('div', { style: { color: 'var(--accent2)', fontSize: 14 } }, err),
    e('div', { className: 'version' }, APP_VERSION));
}

// ── APP ───────────────────────────────────────────────────────────────────────
function App() {
  const [username, setUsername] = useState(() => store.get('username', ''));
  const [me, setMe] = useState(null);
  const [currentWeek, setCurrentWeek] = useState(null);
  const [week, setWeek] = useState(null);
  const [tab, setTab] = useState(() => { const t = store.get('tab', 'today'); return TAB_ORDER.includes(t) ? t : 'today'; });
  const [open, setOpen] = useState({});                    // tabId -> featureId currently open
  const [inputs, setInputs] = useState(() => store.get('inputs', {}));   // 'league'/'player' -> last text
  const [results, setResults] = useState({});              // resultKey -> { loading, data, error, at }
  const [favorites, setFavorites] = useState(() => store.get('favorites', []));
  const [sheet, setSheet] = useState(null);                // 'week' | 'settings' | null
  const scrollMemo = useRef({});

  // Current NFL week, once
  useEffect(() => {
    API.get('/state').then(s => { setCurrentWeek(s.week); setWeek(w => w || s.week); })
      .catch(() => { setCurrentWeek(1); setWeek(w => w || 1); });
  }, []);
  // Who am I (league count, avatar)
  useEffect(() => {
    if (!username) return;
    API.post('/me', { username }).then(setMe).catch(() => setMe(null));
  }, [username]);
  useEffect(() => { store.set('tab', tab); }, [tab]);
  // Phone/browser back closes the open feature
  useEffect(() => {
    const onPop = () => setOpen(o => ({ ...o, [tab]: null }));
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, [tab]);

  const saveUsername = async name => {
    const info = await API.post('/me', { username: name });   // throws a readable error if unknown
    store.set('username', name); setUsername(name); setMe(info); setResults({});
  };

  const run = useCallback(async (f, input) => {
    if (!username || !week) return;
    const key = resultKey(f, week, f.needs ? input : '');
    setResults(r => ({ ...r, [key]: { ...(r[key] || {}), loading: true, error: null } }));
    try {
      const body = { username, week };
      if (f.needs) body[NEEDS[f.needs].field] = input.trim();
      const data = await API.post(f.endpoint, body);
      setResults(r => ({ ...r, [key]: { loading: false, data, error: null, at: Date.now() } }));
    } catch (ex) {
      setResults(r => ({ ...r, [key]: { loading: false, data: null, error: ex.message, at: Date.now() } }));
    }
  }, [username, week]);

  const openFeature = f => {
    scrollMemo.current[tab] = window.scrollY;
    setOpen(o => ({ ...o, [tab]: f.id }));
    try { window.history.pushState({ ff: f.id }, ''); } catch (_) {}
    window.scrollTo(0, 0);
    if (!f.needs) {
      const k = resultKey(f, week, '');
      if (!results[k]) run(f, '');
    } else if ((inputs[f.needs] || '').trim()) {
      const k = resultKey(f, week, inputs[f.needs]);
      if (!results[k]) run(f, inputs[f.needs]);
    }
  };
  const closeFeature = () => {
    if (window.history.state && window.history.state.ff) { window.history.back(); }
    else setOpen(o => ({ ...o, [tab]: null }));
    const y = scrollMemo.current[tab] || 0;
    setTimeout(() => window.scrollTo(0, y), 0);
  };
  const switchTab = id => {
    if (id === tab && open[id]) { closeFeature(); return; }    // tap active tab = back to its list
    setTab(id); window.scrollTo(0, 0);
  };
  const setInput = (kind, v) => setInputs(prev => { const n = { ...prev, [kind]: v }; store.set('inputs', n); return n; });
  const toggleFav = id => setFavorites(prev => { const n = prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]; store.set('favorites', n); return n; });
  const badgeFor = f => {
    if (!f.badge || f.needs) return null;
    const entry = results[resultKey(f, week, '')];
    if (!entry || !entry.data) return null;
    try { return f.badge(entry.data); } catch (_) { return null; }
  };

  if (!username) return e('div', { className: 'shell' }, e(Welcome, { onSave: saveUsername }));
  if (!week) return e('div', { className: 'shell' }, e(Loading, { message: 'Loading…' }));

  const tabDefs = TAB_ORDER.map(id => FF.tabs.find(t => t.id === id)).filter(Boolean);
  const currentTab = tabDefs.find(t => t.id === tab) || tabDefs[0];
  const openId = open[currentTab.id];
  const f = openId ? FF.feature(openId) : null;
  const input = f && f.needs ? (inputs[f.needs] || '') : '';
  const entry = f ? results[resultKey(f, week, input)] : null;

  return e('div', { className: 'shell' },
    f
      ? e(FeatureScreen, {
          f, week, entry, input, leagues: me && me.leagues,
          setInput: v => setInput(f.needs, v),
          onRun: () => run(f, input), onBack: closeFeature,
          isFav: favorites.includes(f.id), onToggleFav: () => toggleFav(f.id),
        })
      : e(TabRoot, {
          tab: currentTab, me, username, week, favorites, badgeFor,
          onWeek: () => setSheet('week'), onSettings: () => setSheet('settings'), onOpen: openFeature,
        }),
    e('nav', { className: 'tabbar' }, e('div', { className: 'tabbar-inner' },
      tabDefs.map(t => e('button', { key: t.id, className: `tab${t.id === currentTab.id ? ' on' : ''}`, onClick: () => switchTab(t.id) },
        e('span', { className: 'tab-icon' }, t.icon), t.label)))),
    sheet === 'week' && e(WeekSheet, { week, currentWeek, onPick: setWeek, onClose: () => setSheet(null) }),
    sheet === 'settings' && e(SettingsSheet, { username, me, onSave: saveUsername, onClearCache: () => setResults({}), onClose: () => setSheet(null) }));
}
