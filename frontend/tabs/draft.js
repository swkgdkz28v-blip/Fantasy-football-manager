/* Fantasy Manager — tabs/draft.js
   The Draft tab (added v11.0): drafts happening now and coming up, the rookie draft board, and age profiles
   for planning. Needs core.js loaded first. */

// ── DRAFT PICKS VIEW ──────────────────────────────────────────────────────────
function DraftPicksView({ data }) {
  const [yr, setYr] = useState('all');
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No draft pick data found.'));
  const sm = data.summary || {};
  const years = [...new Set(data.results.flatMap(r => r.seasons || []))].sort();
  const pick = (p, i) => e('div', { key: i, style: { padding: '6px 10px', background: 'var(--surface2)', border: `1px solid ${p.round === 1 ? 'var(--accent)' : 'var(--border)'}`, borderRadius: 8, fontSize: 12 } },
    e('div', { style: { fontWeight: 700, color: p.round === 1 ? 'var(--accent)' : 'var(--accent4)' } }, (p.pick || `Round ${p.round}`)),
    e('div', { style: { fontSize: 10, color: p.own ? 'var(--text3)' : 'var(--purple)' } }, p.own ? 'Own' : `From ${p.original_owner}`));
  const gone = (p, k) => e('div', { key: k, style: { padding: '6px 10px', background: 'transparent', border: '1px dashed var(--accent2)', borderRadius: 8, fontSize: 12, opacity: 0.7 } },
    e('div', { style: { fontWeight: 700, color: 'var(--text3)', textDecoration: 'line-through' } }, (p.pick || `Round ${p.round}`)),
    e('div', { style: { fontSize: 10, color: 'var(--accent2)', fontWeight: 700 } }, `Traded → ${p.to}`));
  const pill = (on, label, onClick) => e('button', { key: label, onClick, style: { flex: 1, padding: '7px 4px', fontSize: 12, fontWeight: 700, borderRadius: 8, border: `1px solid ${on ? 'var(--accent)' : 'var(--border)'}`, background: on ? 'var(--surface2)' : 'transparent', color: on ? 'var(--text)' : 'var(--text3)' } }, label);
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.picks ?? 0, label: 'Picks Held', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.firsts ?? 0, label: '1st Rounders', color: 'var(--accent)' }),
      e(StatTile, { value: sm.acquired ?? 0, label: 'Acquired', color: 'var(--purple)' }),
      e(StatTile, { value: sm.traded_away ?? 0, label: 'Traded Away', color: 'var(--accent2)' })),
    years.length > 1 && e('div', { style: { display: 'flex', gap: 6, marginBottom: 10 } },
      pill(yr === 'all', 'All', () => setYr('all')), years.map(y => pill(yr === y, y, () => setYr(y)))),
    data.results.map(r => {
      const held = r.upcoming_picks.filter(p => yr === 'all' || p.season === yr);
      const away = (r.traded_away || []).filter(p => yr === 'all' || p.season === yr);
      return e(Card, { key: r.league },
        e('div', { className: 'card-header', style: { marginBottom: 8 } },
          e('div', { style: { minWidth: 0 } }, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
          e(Tag, { color: held.length ? 'blue' : 'red' }, `${held.length} pick${held.length === 1 ? '' : 's'}`)),
        // one light box per draft year: its picks, then anything traded away from that year
        (r.seasons || []).filter(y => yr === 'all' || y === yr).map(y => {
          const h = held.filter(p => p.season === y), a = away.filter(p => p.season === y);
          const yc = ['var(--accent4)', 'var(--purple)', 'var(--accent3)'][years.indexOf(y) % 3];   // each draft year keeps its own color
          return e('div', { key: y, style: { border: '1px solid var(--border)', borderLeft: `3px solid ${yc}`, background: 'rgba(255,255,255,0.025)', borderRadius: 10, padding: '8px 10px', marginTop: 8 } },
            e('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 } },
              e('span', { style: { fontFamily: 'Bebas Neue', fontSize: '1.25rem', letterSpacing: 1, color: yc } }, `${y} Draft`),
              e('span', { style: { fontSize: 11, color: 'var(--text3)' } }, `${(r.order_set || []).includes(y) ? 'Order set · ' : ''}${h.length} pick${h.length === 1 ? '' : 's'}`)),
            h.length + a.length === 0
              ? e('div', { style: { fontSize: 12, color: 'var(--text3)' } }, 'No picks held')
              : e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
                  // held and traded-away picks together, in round order; traded ones are dashed, faded and struck through
                  [...h.map(p => ({ ...p, held: true })), ...a.map(p => ({ ...p, held: false }))]
                    .sort((x, z) => x.round - z.round || ((x.overall || 999) - (z.overall || 999)) || (z.held - x.held))
                    .map((p, i) => p.held ? pick(p, i) : gone(p, 'x' + i))),
            h.length === 0 && a.length > 0 && e('div', { style: { fontSize: 11, color: 'var(--text3)', marginTop: 6 } }, 'No picks held this year'));
        }));
    }),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

// ── DRAFT DATES VIEW ──────────────────────────────────────────────────────────
function DraftDatesView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No draft data found.'));
  const STATUS_COLOR = { drafting: 'var(--accent2)', paused: 'var(--accent3)', pre_draft: 'var(--accent4)', complete: 'var(--text3)' };
  const STATUS_LABEL = { drafting: '🔴 In Progress', paused: '⏸ Paused', pre_draft: '📅 Scheduled', complete: '✅ Complete' };
  const grouped = {};
  data.results.forEach(r => {
    const s = r.status || 'unknown';
    if (!grouped[s]) grouped[s] = [];
    grouped[s].push(r);
  });
  const statusOrder = ['drafting', 'paused', 'pre_draft', 'complete'];

  return e('div', null,
    statusOrder.filter(s => grouped[s]).map(status =>
      e('div', { key: status, style: { marginBottom: 16 } },
        e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: STATUS_COLOR[status] || 'var(--text3)', marginBottom: 8 } }, STATUS_LABEL[status] || status.toUpperCase()),
        grouped[status].map(r => e('div', { key: r.draft_id, style: { padding: '10px 14px', background: 'var(--surface)', border: `1px solid ${STATUS_COLOR[status] || 'var(--border)'}`, borderRadius: 10, marginBottom: 6 } },
          e('div', { style: { fontWeight: 700, fontSize: 13 } }, r.league),
          e('div', { style: { fontSize: 11, color: 'var(--text3)', marginTop: 3 } },
            r.type ? `${r.type} · ` : '',
            r.start_time ? new Date(r.start_time).toLocaleString() : 'Date TBD'
          )
        ))
      )
    )
  );
}

// ── LIVE DRAFT VIEW ───────────────────────────────────────────────────────────
function LiveDraftView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info', title: 'No Active Drafts' }, e('p', null, 'No drafts currently in progress across your leagues.'));
  return e('div', null,
    data.results.map(r => e(Card, { key: r.draft_id, borderColor: 'var(--accent2)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), e('div', { className: 'card-subtitle' }, `${r.team ? r.team + ' · ' : ''}${r.status === 'drafting' ? '🔴 Live' : '⏸ Paused'}`)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.4rem', color: 'var(--accent2)' } }, `Pick ${r.current_pick}`),
          e('div', { style: { fontSize: 11, color: 'var(--text2)' } }, `On clock: ${r.picks_on_clock}`)
        )
      ),
      r.my_next_picks?.length > 0 && e('div', { style: { padding: '10px 12px', background: 'rgba(0,229,160,0.06)', border: '1px solid rgba(0,229,160,0.25)', borderRadius: 8, marginBottom: 12 } },
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 5 } }, 'Your Next Picks'),
        e('div', { style: { display: 'flex', gap: 8 } },
          r.my_next_picks.map(pick => e('div', { key: pick, style: { padding: '6px 14px', background: 'var(--surface2)', borderRadius: 20, fontSize: 13, fontWeight: 700, color: 'var(--accent)' } }, `#${pick}`))
        )
      ),
      r.recent_picks?.length > 0 && e('div', null,
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6 } }, 'Recent Picks'),
        r.recent_picks.map(p => e('div', { key: p.pick_no, className: 'player-row' },
          e('span', { style: { fontSize: 10, color: 'var(--text3)', minWidth: 32 } }, `#${p.pick_no}`),
          p.position && e(PosBadge, { pos: p.position }),
          e('span', { className: 'player-name' }, p.player_name),
          e('span', { style: { fontSize: 10, color: 'var(--text3)' } }, p.picked_by ? `by ${p.picked_by}` : '')
        ))
      )
    ))
  );
}

// ── AGE PROFILE VIEW ──────────────────────────────────────────────────────────
function AgeProfileView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No leagues found.'));
  const sm = data.summary || {};
  const WIN = { Closing: 'var(--accent2)', 'Win now': 'var(--accent3)', Open: 'var(--accent4)', Rising: 'var(--accent)' };
  const pl = arr => arr.map(x => `${x.name} (${x.position} ${x.age})`).join(', ');
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.avg_core_age ?? '—', label: 'Avg Core Age', color: 'var(--text)' }),
      e(StatTile, { value: sm.closing ?? 0, label: 'Window Closing', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.rising ?? 0, label: 'Rising', color: 'var(--accent)' }),
      e(StatTile, { value: sm.cliff_next_year ?? 0, label: 'Hit Cliff Next Yr', color: 'var(--accent3)' })),
    e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 } },
      ['Closing', 'Win now', 'Open', 'Rising'].map(w => e('span', { key: w, style: { fontSize: 11, padding: '3px 8px', borderRadius: 6, border: `1px solid ${WIN[w]}`, color: 'var(--text2)' } },
        `${w}: ${sm[w === 'Win now' ? 'win_now' : w.toLowerCase()] ?? 0}`))),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 10 } }, 'Oldest core first. Tap a league for cliff details.'),
    data.results.map(r => e('details', { key: r.league, style: { padding: '10px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${WIN[r.window]}`, borderRadius: 8, marginBottom: 6 } },
      e('summary', { style: { cursor: 'pointer', listStyle: 'none' } },
        e('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
          e('div', { style: { flex: 1, minWidth: 0 } },
            e('div', { style: { fontWeight: 700, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.league),
            e('div', { style: { fontSize: 11, color: 'var(--text2)' } }, `${r.team} · ${r.aging_points_pct}% of core pts aging · ${r.young_assets} players ≤24`)),
          r.record && e('div', { style: { textAlign: 'center', minWidth: 46 } },
            e('div', { style: { fontSize: 14, fontWeight: 800, color: r.win_pct == null ? 'var(--text2)' : r.win_pct > 0.5 ? 'var(--accent)' : r.win_pct < 0.5 ? 'var(--accent2)' : 'var(--text2)' } }, r.record),
            e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, 'record')),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontSize: 16, fontWeight: 800 } }, r.core_age),
            e('div', { style: { fontSize: 10, fontWeight: 700, color: WIN[r.window] } }, r.window)))),
      e('div', { style: { fontSize: 12, color: 'var(--text2)', marginTop: 8, lineHeight: 1.6 } },
        e('div', null, 'By position: ', Object.entries(r.pos_age).map(([k, v]) => `${k} ${v}`).join(' · ')),
        r.past_cliff.length > 0 && e('div', { style: { color: 'var(--accent2)' } }, `Past cliff: ${pl(r.past_cliff)}`),
        r.cliff_next_year.length > 0 && e('div', { style: { color: 'var(--accent3)' } }, `Hits cliff next year: ${pl(r.cliff_next_year)}`),
        r.cliff_in_two.length > 0 && e('div', null, `In two years: ${pl(r.cliff_in_two)}`))
    )),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

// ── ROOKIE BOARD VIEW ─────────────────────────────────────────────────────────
function RookieBoardView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No leagues found.'));
  const sm = data.summary || {};
  const TIER = { Early: 'var(--accent)', Mid: 'var(--accent4)', Late: 'var(--text3)' };
  const withPicks = data.results.filter(r => r.picks.length), none = data.results.filter(r => !r.picks.length);
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.total_picks ?? 0, label: 'Picks Held', color: 'var(--text)' }),
      e(StatTile, { value: sm.firsts ?? 0, label: '1st Rounders', color: 'var(--accent)' }),
      e(StatTile, { value: sm.early_firsts ?? 0, label: 'Early 1sts', color: 'var(--accent)' }),
      e(StatTile, { value: sm.no_picks ?? 0, label: 'Leagues w/o Picks', color: 'var(--accent2)' })),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 10 } }, 'Sorted by your earliest projected pick. Slots move as standings change.'),
    withPicks.map(r => e(Card, { key: r.league, borderColor: TIER[r.picks[0].tier] },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), e('div', { className: 'card-subtitle' }, `${r.team} · ${r.draft_season} draft · ${r.teams} teams${r.superflex ? ' · SF' : ''}${r.te_premium ? ' · TE prem' : ''}`)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', lineHeight: 1, color: TIER[r.picks[0].tier] } }, r.first_pick),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, 'first pick'))),
      e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 } },
        r.picks.map((pk, i) => e('span', { key: i, style: { fontSize: 13, fontWeight: 700, padding: '4px 9px', borderRadius: 6, border: `1px solid ${TIER[pk.tier]}`, color: 'var(--text)' } },
          pk.label, pk.via ? e('span', { style: { fontSize: 10, fontWeight: 400, color: 'var(--text3)' } }, ` via ${pk.via}`) : null))),
      e('div', { style: { fontSize: 13, marginBottom: 4 } }, 'Target: ', e('b', { style: { color: 'var(--accent)' } }, r.targets.join(' then '))),
      e('div', { style: { fontSize: 11, color: 'var(--text3)', lineHeight: 1.6 } },
        r.needs.map(n => `${n.position}: ${n.rostered} rostered, ${n.young} young, ${n.aging} aging`).join(' · ')))),
    none.length > 0 && e(Card, { borderColor: 'var(--accent2)' },
      secTitle(`No ${data.results[0]?.draft_season || ''} picks (${none.length})`, 'var(--accent2)'),
      none.map(r => lineRow(r.league, r.league, `needs ${r.targets.join('/')}`))),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

// ── shared bits for the rookie-draft tools ───────────────────────────────────
const dPill = (on, label, onClick) => e('button', { key: label, onClick, style: { flex: 1, padding: '7px 4px', fontSize: 12, fontWeight: 700, borderRadius: 8, border: `1px solid ${on ? 'var(--accent)' : 'var(--border)'}`, background: on ? 'var(--surface2)' : 'transparent', color: on ? 'var(--text)' : 'var(--text3)' } }, label);
const dNote = t => t && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, t);
const dFold = (title, color, items) => items?.length > 0 && e('details', { className: 'card', style: { borderLeft: `3px solid ${color}` } },
  e('summary', { style: { cursor: 'pointer', fontSize: 13, fontWeight: 700, color } }, title),
  items.map((t, i) => e('div', { key: i, style: { fontSize: 12, padding: '6px 0', borderBottom: '1px solid var(--border)', color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, t)));
const dHead = (title, sub, right) => e('div', { className: 'card-header', style: { marginBottom: 6 } },
  e('div', { style: { minWidth: 0 } }, e('div', { className: 'card-title' }, title), sub && e('div', { className: 'card-subtitle' }, sub)), right);

// ── ROSTER CRUNCH VIEW ────────────────────────────────────────────────────────
function RosterCrunchView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const box = (v, l, c) => e('div', { style: { flex: 1, textAlign: 'center', padding: '6px 2px', background: 'var(--surface2)', borderRadius: 8 } },
    e('div', { style: { fontSize: 18, fontWeight: 800, color: c } }, v), e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, l));
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.need_cuts ?? 0, label: 'Leagues Need Cuts', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.cuts_total ?? 0, label: 'Cuts / Trades', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.tight ?? 0, label: 'Exactly Full', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.room ?? 0, label: 'Room to Spare', color: 'var(--accent)' })),
    !data.results?.length && e(Alert, { type: 'success', title: '✅ Room everywhere' }, e('p', null, 'You have enough open spots for every pick you hold.')),
    data.results?.map(r => e(Card, { key: r.league, borderColor: r.status === 'cuts' ? 'var(--accent2)' : 'var(--accent3)' },
      dHead(r.league, r.team, e(Tag, { color: r.status === 'cuts' ? 'red' : 'orange' }, r.status === 'cuts' ? `${r.short} CUT${r.short === 1 ? '' : 'S'}` : 'FULL')),
      e('div', { style: { display: 'flex', gap: 6, marginBottom: 8 } },
        box(r.picks, `${r.draft_year} picks`, 'var(--accent4)'),
        box(r.open_active, `open roster (${r.active_used}/${r.active_cap})`, r.open_active > 0 ? 'var(--accent)' : 'var(--text3)'),
        box(r.taxi_slots ? r.open_taxi : '—', r.taxi_slots ? `open taxi (of ${r.taxi_slots})` : 'no taxi', r.open_taxi > 0 ? 'var(--accent)' : 'var(--text3)')),
      r.must_promote?.length > 0 && e('div', { style: { fontSize: 11, color: 'var(--accent3)', marginBottom: 6 } }, `Likely aging off taxi: ${r.must_promote.join(', ')}`),
      r.status === 'cuts' && !r.cut_candidates?.length && e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, 'Every active player is in your best lineup — trade a pick, or 2-for-1 to open a spot.'),
      r.cut_candidates?.length > 0 && e('div', null,
        e('div', { style: { fontSize: 10, fontWeight: 800, color: 'var(--text3)', letterSpacing: 0.5, marginBottom: 2 } }, 'LOWEST-VALUE BENCH (CUT CANDIDATES)'),
        r.cut_candidates.map(c => e('div', { key: c.id, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' } },
          e(PosBadge, { pos: c.position || '—' }),
          e('span', { style: { flex: 1, fontSize: 13, fontWeight: 600, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, c.name),
          e('span', { style: { fontSize: 11, color: 'var(--text3)' } }, `${c.team}${c.age ? ` · ${c.age}` : ''}`)))))),
    dFold(`✅ Room to spare (${data.room?.length || 0})`, 'var(--accent)', (data.room || []).map(r => `${r.league} · ${r.picks} picks · ${r.spare} extra spot${r.spare === 1 ? '' : 's'}`)),
    dNote(data.note));
}

// ── DRAFT-FOR GUIDE VIEW ──────────────────────────────────────────────────────
function DraftForView({ data }) {
  const [pos, setPos] = useState('all');
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No leagues found.'));
  const by = data.summary?.by_target || {};
  const GC = { Target: 'var(--accent2)', Depth: 'var(--accent3)', Set: 'var(--accent)' };
  const keys = ['QB', 'RB', 'WR', 'TE', 'BPA'].filter(k => by[k]);
  const list = data.results.filter(r => pos === 'all' || r.targets.includes(pos));
  return e('div', null,
    e('div', { className: 'stat-row' }, keys.slice(0, 4).map(k => e(StatTile, { key: k, value: by[k], label: `Target ${k}`, color: 'var(--accent4)' }))),
    e('div', { style: { display: 'flex', gap: 6, marginBottom: 10 } }, dPill(pos === 'all', 'All', () => setPos('all')), keys.map(k => dPill(pos === k, k, () => setPos(k)))),
    list.map(r => e(Card, { key: r.league },
      dHead(r.league, `${r.team}${r.window ? ` · ${r.window}` : ''}${r.core_age ? ` · core ${r.core_age}` : ''}`,
        e('div', { style: { display: 'flex', gap: 4 } }, r.targets.map(t => e(Tag, { key: t, color: t === 'BPA' ? 'blue' : 'red' }, t)))),
      r.positions.map(x => e('div', { key: x.position, style: { display: 'flex', gap: 8, alignItems: 'flex-start', padding: '5px 0', borderTop: '1px solid var(--border)' } },
        e(PosBadge, { pos: x.position }),
        e('div', { style: { flex: 1, minWidth: 0 } },
          e('div', { style: { fontSize: 12, fontWeight: 800, color: GC[x.grade] } }, `${x.grade} · start ${x.starters} · have ${x.rostered}`),
          e('div', { style: { fontSize: 11, color: 'var(--text3)', lineHeight: 1.35 } }, x.why)))))),
    dNote(data.note));
}

// ── ON THE CLOCK VIEW ─────────────────────────────────────────────────────────
function OnTheClockView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, data?.note || 'No drafts in progress right now.'));
  const sm = data.summary || {};
  const mmss = s => s == null ? null : s >= 3600 ? `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m` : `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  const pk = (p, i) => e('div', { key: i, style: { display: 'flex', gap: 8, alignItems: 'center', padding: '3px 0', fontSize: 12 } },
    e('span', { style: { color: 'var(--text3)', minWidth: 34 } }, p.pick), e(PosBadge, { pos: p.position || '—' }),
    e('span', { style: { flex: 1, fontWeight: 600, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name),
    p.by && e('span', { style: { fontSize: 10, color: 'var(--text3)', maxWidth: 90, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.by));
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.on_clock ?? 0, label: 'On the Clock', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.up_within_3 ?? 0, label: 'Up within 3', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.live ?? 0, label: 'Live Drafts', color: 'var(--accent4)' })),
    data.results.map(r => e(Card, { key: r.league, borderColor: r.on_clock ? 'var(--accent2)' : r.picks_until != null && r.picks_until <= 3 ? 'var(--accent3)' : undefined },
      dHead(r.league, r.team, r.on_clock
        ? e('span', { style: { fontSize: 12, fontWeight: 800, color: '#fff', background: 'var(--accent2)', borderRadius: 6, padding: '3px 8px' } }, '⏰ YOU’RE UP')
        : e(Tag, { color: r.status === 'paused' ? 'orange' : 'blue' }, r.status === 'paused' ? 'PAUSED' : r.picks_until == null ? 'NO PICKS LEFT' : `${r.picks_until} until you`)),
      e('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 6, gap: 8 } },
        e('span', { style: { color: 'var(--text2)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, `Now: ${r.current} · ${r.on_clock ? 'You' : r.up}`),
        r.secs_left != null && e('span', { style: { fontWeight: 800, color: r.on_clock ? 'var(--accent2)' : 'var(--text3)', whiteSpace: 'nowrap' } }, `⏱ ${mmss(r.secs_left)}`)),
      r.next_picks?.length > 0 && e('div', { style: { fontSize: 11, color: 'var(--accent4)', marginBottom: 6 } }, `Your next: ${r.next_picks.join(' · ')}${r.picks_left_total > r.next_picks.length ? ` (+${r.picks_left_total - r.next_picks.length} more)` : ''}`),
      r.recent?.length > 0 && e('div', null, e('div', { style: { fontSize: 10, fontWeight: 800, color: 'var(--text3)', marginTop: 4 } }, 'LAST PICKS'), r.recent.map(pk)),
      r.my_picks?.length > 0 && e('details', { style: { marginTop: 6 } },
        e('summary', { style: { fontSize: 11, color: 'var(--accent)', cursor: 'pointer', fontWeight: 700 } }, `Your picks so far (${r.my_picks.length})`),
        r.my_picks.map((p, i) => pk({ ...p, by: '' }, i))),
      e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 6 } }, `${r.made} of ${r.total} picks made`))),
    dNote(data.note));
}

// ── ROOKIE EXPOSURE VIEW ──────────────────────────────────────────────────────
function RookieExposureView({ data }) {
  const [pos, setPos] = useState('all');
  const [open, setOpen] = useState(null);
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No first-year players on your rosters.'));
  const sm = data.summary || {};
  const poss = ['QB', 'RB', 'WR', 'TE'].filter(p => sm.by_position?.[p]);
  const list = data.results.filter(r => pos === 'all' || r.position === pos);
  const max = Math.max(...data.results.map(r => r.shares), 1);
  const RC = { start: 'var(--accent)', bench: 'var(--accent3)', taxi: 'var(--purple)', ir: 'var(--accent2)' };
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.rookies ?? 0, label: 'Rookies Owned', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.shares ?? 0, label: 'Total Shares', color: 'var(--text)' }),
      e(StatTile, { value: sm.leagues ?? 0, label: 'Leagues', color: 'var(--text3)' })),
    e('div', { style: { display: 'flex', gap: 6, marginBottom: 10 } }, dPill(pos === 'all', 'All', () => setPos('all')), poss.map(p => dPill(pos === p, `${p} (${sm.by_position[p]})`, () => setPos(p)))),
    list.map(r => e('div', { key: r.id, onClick: () => setOpen(open === r.id ? null : r.id), style: { background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '8px 12px', marginBottom: 6, cursor: 'pointer' } },
      e('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
        e(PosBadge, { pos: r.position || '—' }),
        e('div', { style: { flex: 1, minWidth: 0 } },
          e('div', { style: { fontSize: 14, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.name),
          e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, `${r.team}${r.age ? ` · ${r.age}` : ''} · ${['start', 'bench', 'taxi', 'ir'].filter(k => r[k]).map(k => `${r[k]} ${k}`).join(' · ')}`)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontSize: 18, fontWeight: 800, color: 'var(--accent4)' } }, r.shares),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${r.pct}%`))),
      e('div', { style: { height: 4, background: 'var(--surface2)', borderRadius: 2, marginTop: 6 } }, e('div', { style: { width: `${100 * r.shares / max}%`, height: 4, background: 'var(--accent4)', borderRadius: 2 } })),
      open === r.id && e('div', { style: { marginTop: 6 } }, r.leagues.map((l, i) => e('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, padding: '3px 0', borderTop: '1px solid var(--border)' } },
        e('span', { style: { color: 'var(--text2)', minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, l.league),
        e('span', { style: { color: RC[l.role], fontWeight: 700, textTransform: 'capitalize', marginLeft: 8 } }, l.role)))))),
    dNote(data.note));
}

// ── DRAFT RECAP VIEW ──────────────────────────────────────────────────────────
function DraftRecapView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No completed rookie drafts found in your leagues this season.'));
  const sm = data.summary || {};
  const VC = { Value: 'var(--accent)', Reach: 'var(--accent2)', 'On par': 'var(--text2)' };
  const sign = v => v == null ? '' : `${v > 0 ? '+' : ''}${v}`;
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.values ?? 0, label: 'Values', color: 'var(--accent)' }),
      e(StatTile, { value: sm.reaches ?? 0, label: 'Reaches', color: 'var(--accent2)' }),
      e(StatTile, { value: sign(sm.net ?? 0), label: 'Net picks of value', color: (sm.net ?? 0) >= 0 ? 'var(--accent)' : 'var(--accent2)' }),
      e(StatTile, { value: sm.drafts ?? 0, label: 'Drafts', color: 'var(--text3)' })),
    data.results.map(r => e(Card, { key: r.league },
      dHead(r.league, `${r.team} · ${r.season} · ${r.teams} teams`,
        r.net != null && e(Tag, { color: r.net >= 0 ? 'green' : 'red' }, `${sign(r.net)} net`)),
      r.picks.map((p, i) => e('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0', borderTop: '1px solid var(--border)' } },
        e('span', { style: { fontSize: 12, fontWeight: 800, color: 'var(--accent4)', minWidth: 34 } }, p.pick),
        e(PosBadge, { pos: p.position || '—' }),
        e('div', { style: { flex: 1, minWidth: 0 } },
          e('div', { style: { fontSize: 13, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, p.adp ? `Your-league ADP ${p.adp} · ${p.samples} drafts` : 'Only drafted in this league')),
        p.verdict && e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontSize: 11, fontWeight: 800, color: VC[p.verdict] } }, p.verdict),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, sign(p.delta))))))),
    dNote(data.note));
}

// ── DRAFT TAB LIST ───────────────────────────────────────────────────────────
FF.tab({ id: 'draft', label: 'Draft', icon: '🎓', groups: [
  { label: 'Drafts', features: [
    { id: 'draft-dates', title: 'Draft Dates', sub: 'Upcoming draft schedule', icon: '📅', tint: 'purple',
      endpoint: '/analysis/draft-dates', view: DraftDatesView },
    { id: 'on-the-clock', title: 'On the Clock', sub: 'Every live draft: who’s up and picks until you', icon: '⏰', tint: 'red',
      endpoint: '/analysis/on-the-clock', view: OnTheClockView, badge: d => d.summary && d.summary.live ? cnt(d.summary.on_clock, 'red') : null },
    { id: 'draft-picks', title: 'All Draft Picks', sub: 'Picks you own by league', icon: '📋', tint: 'blue',
      endpoint: '/analysis/draft-picks', view: DraftPicksView },
  ]},
  { label: 'Planning', features: [
    { id: 'roster-crunch', title: 'Roster Crunch', sub: 'Picks vs open roster + taxi spots', icon: '🧮', tint: 'orange',
      endpoint: '/analysis/roster-crunch', view: RosterCrunchView, badge: d => d.summary && cnt(d.summary.need_cuts, 'red') },
    { id: 'draft-for', title: 'Draft-For Guide', sub: 'Positions to target in each league', icon: '🎯', tint: 'green',
      endpoint: '/analysis/draft-for', view: DraftForView },
    { id: 'rookie-board', title: 'Rookie Draft Board', sub: 'Your picks and what to target', icon: '🎓', tint: 'green',
      endpoint: '/analysis/rookie-board', view: RookieBoardView },
    { id: 'age-profile', title: 'Age Profile', sub: 'Core age and players near the cliff', icon: '⏳', tint: 'orange',
      endpoint: '/analysis/age-profile', view: AgeProfileView },
  ]},
  { label: 'After the draft', features: [
    { id: 'rookie-exposure', title: 'Rookie Exposure', sub: 'Shares of each rookie across leagues', icon: '📊', tint: 'blue',
      endpoint: '/analysis/rookie-exposure', view: RookieExposureView },
    { id: 'draft-recap', title: 'Draft Recap', sub: 'Your picks vs your-league ADP', icon: '📝', tint: 'purple',
      endpoint: '/analysis/draft-recap', view: DraftRecapView },
  ]},
]});
