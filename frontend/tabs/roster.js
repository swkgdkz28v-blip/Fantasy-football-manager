/* Fantasy Manager — tabs/roster.js (v10.33)
   The Roster tab: its result screens and the list that opens them. Needs core.js loaded first. */

// ── IR-ELIGIBLE VIEW ──────────────────────────────────────────────────────────
function IrEligibleView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const withElig = (data.results || []).filter(r => r.eligible?.length);
  const onlyNot = (data.results || []).filter(r => !r.eligible?.length && r.not_eligible?.length);
  const row = (p, color) => e('div', { key: p.id, className: 'player-row' },
    e('span', { style: { fontSize: 9, color: p.role === 'starter' ? 'var(--accent3)' : 'var(--text3)', minWidth: 46, textAlign: 'center', fontWeight: p.role === 'starter' ? 700 : 400 } }, p.role.toUpperCase()),
    e(PosBadge, { pos: p.position }),
    e('span', { className: 'player-name' }, p.name, p.injury ? e('span', { style: { fontSize: 10, color: 'var(--text3)' } }, ` · ${p.injury}`) : null),
    e('span', { className: 'player-team' }, p.team),
    e(Tag, { color }, p.status));
  if (!withElig.length && !onlyNot.length) return e(Alert, { type: 'success', title: '✅ All Clear' }, e('p', null, 'No IR-eligible players sitting outside the IR slot.'));
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.eligible_players ?? 0, label: 'IR-Eligible, Not On IR', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.can_move_now ?? 0, label: 'Can Move Now', color: 'var(--accent)' }),
      e(StatTile, { value: sm.ir_full ?? 0, label: 'IR Full', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.no_ir_slot ?? 0, label: 'No IR Slot', color: 'var(--text3)' })
    ),
    withElig.map(r => e(Card, { key: r.league, borderColor: r.ir_open > 0 ? 'var(--accent)' : 'var(--accent2)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontSize: 12, fontWeight: 800, color: r.ir_open > 0 ? 'var(--accent)' : 'var(--accent2)' } }, `IR ${r.ir_used}/${r.ir_slots}`),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `allows ${r.allowed_statuses.join(', ')}`))
      ),
      e('div', { style: { fontSize: 11, color: 'var(--text2)', marginBottom: 8, fontWeight: 700 } }, r.action),
      r.eligible.map(p => row(p, 'red')),
      r.not_eligible?.length > 0 && e('details', { style: { marginTop: 6 } },
        e('summary', { style: { fontSize: 10, color: 'var(--text3)', cursor: 'pointer' } }, `${r.not_eligible.length} out but not IR-eligible here`),
        r.not_eligible.map(p => row(p, 'yellow')))
    )),
    onlyNot.length > 0 && e(Card, { borderColor: 'var(--text3)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6 } }, `Out but not IR-eligible (${onlyNot.length} leagues) — hold or drop`),
      onlyNot.map(r => e('div', { key: r.league, style: { fontSize: 11, padding: '4px 0', borderBottom: '1px solid var(--border)' } },
        e('b', null, r.league), e('span', { style: { color: 'var(--text3)' } }, ` · ${r.not_eligible.map(p => `${p.name} (${p.status}${p.role === 'starter' ? ', starting!' : ''})`).join(', ')}`)))
    ),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── ILLEGAL IR VIEW ───────────────────────────────────────────────────────────
function IrIneligibleView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  if (!data.results?.length) return e(Alert, { type: 'success', title: '✅ All Clear' },
    e('p', null, `Checked ${sm.leagues_checked ?? 0} leagues (${sm.leagues_with_ir ?? 0} with someone on IR) — every IR player is eligible.`));
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.leagues_flagged ?? 0, label: 'Leagues Locked', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.players ?? 0, label: 'Ineligible On IR', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.need_drop ?? 0, label: 'Need A Drop', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.leagues_checked ?? 0, label: 'Leagues Checked', color: 'var(--text3)' })),
    e(Alert, { type: 'warning' }, e('p', null, 'Sleeper blocks adds, drops and trades in these leagues until the player is moved out of IR.')),
    data.results.map(r => e(Card, { key: r.league, borderColor: 'var(--accent2)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { fontSize: 11, color: 'var(--text3)', textAlign: 'right' } }, `IR allows ${r.allowed_statuses.join(', ')}`)),
      r.ineligible.map(p => e('div', { key: p.id, style: { padding: '8px 0', borderBottom: '1px solid var(--border)' } },
        e('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
          e(PosBadge, { pos: p.position }),
          e('span', { style: { fontSize: 14, fontWeight: 700, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name),
          e(Tag, { color: p.status === 'HEALTHY' ? 'green' : 'yellow' }, p.status)),
        e('div', { style: { fontSize: 11, color: 'var(--text3)', marginTop: 2 } }, `${p.team} · ${p.why}${p.proj > 0 ? ` · proj ${p.proj} this week` : ''}`))),
      e('div', { style: { fontSize: 13, fontWeight: 700, color: 'var(--text)', margin: '10px 0 4px' } }, `Fix: ${r.fix}`),
      r.drop_candidates.length > 0 && e('div', { style: { fontSize: 12, color: 'var(--text2)' } },
        'Weakest bench to drop: ', r.drop_candidates.map(d => `${d.name} (${d.position}, ${d.proj})`).join(', ')),
      r.swap_in.length > 0 && e('div', { style: { fontSize: 12, color: 'var(--text2)', marginTop: 4 } },
        'Could take the IR slot: ', r.swap_in.map(d => `${d.name} (${d.status})`).join(', '))
    )),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

function PositionNeedsView({ data }) {
  if (!data?.needs_by_pos || !Object.keys(data.needs_by_pos).length) return e(Alert, { type: 'success', title: '✅ All Positions Covered' }, e('p', null, 'Every position has at least starter depth.'));
  const GRADE_COLOR = { Empty: '#ff3333', Underfilled: 'var(--accent2)', 'No Depth': 'var(--accent3)', Thin: 'var(--accent4)', 'Flex Short': 'var(--accent2)' };
  return e('div', null,
    Object.entries(data.needs_by_pos).map(([pos, needs]) =>
      e(Card, { key: pos, borderColor: POS_COLORS[pos] },
        e('div', { style: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 } },
          e(PosBadge, { pos }),
          e('span', { style: { fontSize: 14, fontWeight: 700, color: POS_COLORS[pos] } }, `${pos} — ${needs.length} league${needs.length > 1 ? 's' : ''} need attention`)
        ),
        needs.map(n => e('div', { key: n.league, style: { padding: '9px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderLeft: `3px solid ${GRADE_COLOR[n.grade] || 'var(--text3)'}`, borderRadius: 8, marginBottom: 6 } },
          e('div', { style: { display: 'flex', justifyContent: 'space-between', marginBottom: 5 } },
            e('div', null, e('div', { style: { fontWeight: 700, fontSize: 13 } }, n.league), n.team && e('div', { style: { fontSize: 11, color: 'var(--text2)' } }, n.team)),
            e('div', { style: { textAlign: 'right' } },
              e('div', { style: { fontSize: 11, fontWeight: 700, color: GRADE_COLOR[n.grade] } }, n.grade),
              e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${n.owned} owned · need ${n.min_needed ?? n.needed} (${n.needed} slot${n.needed !== 1 ? 's' : ''}${n.flex_need ? ` + ${n.flex_need} flex` : ''}${n.min_needed > (n.needed + (n.flex_need || 0)) ? ` + ${n.min_needed - n.needed - (n.flex_need || 0)} depth` : ''})`)
            )
          ),
          n.format_notes?.length > 0 && e('div', { style: { display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 5 } },
            n.format_notes.map((note, i) => e(Tag, { key: i, color: 'blue' }, note))
          ),
          n.players?.length > 0
            ? e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 4 } },
                n.players.map(p => e('span', { key: p.id, style: { display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 8px', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 5, fontSize: 11 } }, p.name, e('span', { style: { color: 'var(--text3)' } }, p.team)))
              )
            : e('div', { style: { fontSize: 11, color: 'var(--accent2)' } }, `No ${pos} players on roster`)
        ))
      )
    )
  );
}

// ── BYE PLANNER VIEW ──────────────────────────────────────────────────────────
function ByePlannerView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const maxW = Math.max(...(sm.by_week || []).map(w => w.leagues), 1);
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.leagues_with_holes ?? 0, label: "Can't Fill A Week", color: 'var(--accent2)' }),
      e(StatTile, { value: sm.leagues_thin ?? 0, label: 'Thin Weeks Only', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.worst_week ? `Wk ${sm.worst_week}` : '—', label: 'Worst Week', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.leagues ?? 0, label: 'Leagues', color: 'var(--text3)' })),
    (sm.by_week || []).length > 0 && e(Card, null,
      secTitle(`Leagues that can't field a lineup, week ${data.from_week} onward`),
      (sm.by_week || []).map(w => e('div', { key: w.week, style: { marginBottom: 8 } },
        e('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 } },
          e('b', null, `Week ${w.week}`), e('span', { style: { color: 'var(--text3)' } }, `${w.leagues} league${w.leagues === 1 ? '' : 's'} · byes: ${w.bye_teams.join(', ')}`)),
        e('div', { className: 'bar-track' }, e('div', { className: 'bar-fill', style: { width: `${(w.leagues / maxW) * 100}%`, background: w.leagues ? 'var(--accent2)' : 'var(--accent)' } }))))),
    !data.results?.length && e(Alert, { type: 'success', title: '✅ Covered' }, e('p', null, 'Every league can field a full lineup through the remaining bye weeks.')),
    (data.results || []).map(r => e(Card, { key: r.league, borderColor: r.cant_fill ? 'var(--accent2)' : 'var(--accent3)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { fontSize: 12, fontWeight: 700, color: r.cant_fill ? 'var(--accent2)' : 'var(--accent3)' } }, `First: Wk ${r.first_problem}`)),
      r.weeks.map(w => e('div', { key: w.week, style: { padding: '8px 0', borderBottom: '1px solid var(--border)' } },
        e('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' } },
          e('b', { style: { fontSize: 14 } }, `Week ${w.week}`),
          e(Tag, { color: w.empty_slots.length ? 'red' : 'yellow' }, w.severity)),
        w.empty_slots.length > 0 && e('div', { style: { fontSize: 12, color: 'var(--accent2)', marginTop: 3 } }, `No one for: ${w.empty_slots.join(', ')}`),
        w.starters_on_bye.length > 0 && e('div', { style: { fontSize: 11, color: 'var(--text3)', marginTop: 2 } }, `Starters on bye: ${w.starters_on_bye.join(', ')}`)))
    )),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

// ── EXPOSURE VIEW ─────────────────────────────────────────────────────────────
function ExposureView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const [tab, setTab] = useState('risk');
  const list = tab === 'risk' ? data.biggest_risk : data.most_owned;
  const btn = (id, label) => e('button', { key: id, onClick: () => setTab(id), style: { flex: 1, padding: '8px 4px', fontSize: 12, fontWeight: 700, borderRadius: 8, border: `1px solid ${tab === id ? 'var(--accent)' : 'var(--border)'}`, background: tab === id ? 'var(--surface2)' : 'transparent', color: tab === id ? 'var(--text)' : 'var(--text3)' } }, label);
  const maxTeam = Math.max(...(data.teams || []).map(t => t.pct), 1);
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.leagues ?? 0, label: 'Leagues', color: 'var(--text2)' }),
      e(StatTile, { value: sm.unique_players ?? 0, label: 'Unique Players', color: 'var(--accent4)' }),
      e(StatTile, { value: `${sm.top5_share ?? 0}%`, label: 'Top-5 Share', color: 'var(--accent3)' }),
      e(StatTile, { value: `${sm.injured_exposure ?? 0}%`, label: 'On Injured Players', color: 'var(--accent2)' })),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 10 } }, `Top-5 share: ${sm.top5_share}% of all your projected starting points this week come from 5 players.`),
    e('div', { style: { display: 'flex', gap: 6, marginBottom: 10 } }, btn('risk', '⚠️ Biggest share'), btn('owned', '📦 Most owned'), btn('teams', '🏈 NFL teams')),
    tab !== 'teams' && e(Card, null,
      list.map(p => e('details', { key: p.id, style: { padding: '8px 0', borderBottom: '1px solid var(--border)' } },
        e('summary', { style: { cursor: 'pointer', listStyle: 'none' } },
          e('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
            e(PosBadge, { pos: p.position }),
            e('div', { style: { flex: 1, minWidth: 0 } },
              e('div', { style: { fontSize: 14, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name,
                p.injury_status ? e('span', { style: { fontSize: 10, color: 'var(--accent2)', marginLeft: 6 } }, p.injury_status.toUpperCase()) : null,
                p.on_bye ? e('span', { style: { fontSize: 10, color: 'var(--accent3)', marginLeft: 6 } }, 'BYE') : null),
              e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, `${p.team}${p.age ? ` · ${p.age}` : ''} · owned ${p.owned} (${p.own_pct}%) · starting ${p.starting}`)),
            e('div', { style: { textAlign: 'right' } },
              e('div', { style: { fontSize: 15, fontWeight: 800, color: tab === 'risk' ? 'var(--accent3)' : 'var(--text)' } }, tab === 'risk' ? `${p.portfolio_share}%` : p.owned),
              e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, tab === 'risk' ? 'of your pts' : 'leagues')))),
        e('div', { style: { fontSize: 11, color: 'var(--text2)', padding: '6px 0 0 8px', lineHeight: 1.6 } },
          p.starting ? `When he starts he's ~${p.avg_lineup_share}% of that lineup. ` : '',
          p.leagues.map(l => `${l.league}${l.starting ? ' ▲' : ''}`).join(' · '))))),
    tab === 'teams' && e(Card, null,
      secTitle('Your starters by NFL team'),
      (data.teams || []).map(t => e('div', { key: t.team, style: { marginBottom: 8 } },
        e('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 2 } },
          e('b', null, t.team, t.on_bye ? e('span', { style: { color: 'var(--accent3)', fontWeight: 400 } }, ' · bye') : null),
          e('span', { style: { color: 'var(--text2)' } }, `${t.starts} starts · ${t.pct}%`)),
        e('div', { className: 'bar-track' }, e('div', { className: 'bar-fill', style: { width: `${(t.pct / maxTeam) * 100}%`, background: 'var(--accent4)' } }))))),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

// ── PLAYER LOOKUP VIEW ────────────────────────────────────────────────────────
function PlayerLookupView({ data }) {
  if (!data) return null;
  if (data.ambiguous) return e(Card, { borderColor: 'var(--accent3)' },
    e('div', { style: { fontSize: 12, marginBottom: 8 } }, `Several players match "${data.query}" — enter the full name:`),
    data.matches.map(m => e('div', { key: m.id, className: 'player-row' }, e(PosBadge, { pos: m.position }), e('span', { className: 'player-name' }, m.name), e('span', { className: 'player-team' }, m.team))));
  const p = data.player, sm = data.summary || {};
  const ROLE = { STARTER: ['var(--accent)', '▲ STARTING'], BENCH: ['var(--accent3)', '▼ BENCH'], TAXI: ['var(--accent4)', '🚕 TAXI'], IR: ['var(--accent2)', '🏥 IR'] };
  const line = (r, right, color) => e('div', { key: r.league, style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, padding: '6px 0', borderBottom: '1px solid var(--border)' } },
    e('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 } }, r.league, e('span', { style: { color: 'var(--text3)', fontSize: 10 } }, ` · ${r.team}`)),
    e('span', { style: { whiteSpace: 'nowrap', fontWeight: 700, color } }, right));
  return e('div', null,
    e(Card, null,
      e('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
        e(PosBadge, { pos: p.position }),
        e('div', { style: { flex: 1 } },
          e('div', { style: { fontSize: 18, fontWeight: 800 } }, p.name),
          e('div', { style: { fontSize: 11, color: 'var(--text2)' } }, `${p.team}${p.age ? ` · age ${p.age}` : ''}${p.years_exp != null ? ` · ${p.years_exp} yr${p.years_exp === 1 ? '' : 's'}` : ''}`)),
        p.injury_status && e(Tag, { color: 'red' }, p.injury_status.toUpperCase()))
    ),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.owned ?? 0, label: `Owned (of ${sm.leagues})`, color: 'var(--text)' }),
      e(StatTile, { value: sm.starting ?? 0, label: 'Starting', color: 'var(--accent)' }),
      e(StatTile, { value: sm.bench ?? 0, label: 'Benched', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.against ?? 0, label: 'Against You', color: 'var(--accent2)' })
    ),
    (sm.taxi > 0 || sm.ir > 0) && e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 10 } }, `${sm.taxi ? `${sm.taxi} on taxi` : ''}${sm.taxi && sm.ir ? ' · ' : ''}${sm.ir ? `${sm.ir} on IR` : ''}`),
    data.owned.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 6 } }, `Your leagues (${data.owned.length}) · week ${data.week}`),
      data.owned.map(r => line(r, `${ROLE[r.role][1]}${r.slot ? ` · ${r.slot}` : ''}`, ROLE[r.role][0]))),
    data.owned.length === 0 && e(Alert, { type: 'info' }, e('p', null, `You don't roster ${p.name} in any league.`)),
    data.against.length > 0 && e(Card, { borderColor: 'var(--accent2)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent2)', marginBottom: 6 } }, `Playing against you this week (${data.against.length})`),
      data.against.map(r => line(r, `${r.owner} · ${r.starting ? 'starting' : 'benched'}`, r.starting ? 'var(--accent2)' : 'var(--text3)'))),
    data.available.length > 0 && e(Card, { borderColor: 'var(--accent4)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent4)', marginBottom: 6 } }, `Free agent in (${data.available.length})`),
      e('div', { style: { fontSize: 11, color: 'var(--text2)', lineHeight: 1.6 } }, data.available.map(r => r.league).join(' · '))),
    data.elsewhere.length > 0 && e('details', { style: { marginTop: 8 } },
      e('summary', { style: { fontSize: 11, color: 'var(--text3)', cursor: 'pointer' } }, `Owned by someone else in ${data.elsewhere.length} league${data.elsewhere.length === 1 ? '' : 's'}`),
      data.elsewhere.map(r => line(r, r.owner, 'var(--text3)')))
  );
}

// ── ROSTER TAB LIST ──────────────────────────────────────────────────────
FF.tab({ id: 'roster', label: 'Roster', icon: '🧩', groups: [
  { label: 'Roster health', features: [
    { id: 'ir-ineligible', title: 'Illegal IR', sub: 'Leagues locked until fixed', icon: '🚫', tint: 'red',
      endpoint: '/alerts/ir-ineligible', view: IrIneligibleView, badge: d => d.summary && cnt(d.summary.leagues_flagged, 'red') },
    { id: 'ir-eligible', title: 'Move To IR', sub: 'Injured players taking a roster spot', icon: '🏥', tint: 'orange',
      endpoint: '/alerts/ir-eligible', view: IrEligibleView, badge: d => d.summary && cnt(d.summary.eligible_players, 'orange') },
    { id: 'position-needs', title: 'Position Needs', sub: 'Where each roster is short', icon: '📍', tint: 'orange',
      endpoint: '/analysis/position-needs', view: PositionNeedsView },
    { id: 'bye-planner', title: 'Bye Planner', sub: 'Weeks you can’t field a lineup', icon: '🗓️', tint: 'green',
      endpoint: '/analysis/bye-planner', view: ByePlannerView, badge: d => d.summary && cnt(d.summary.leagues_with_holes, 'red') },
  ]},
  { label: 'Across all leagues', features: [
    { id: 'exposure', title: 'Exposure', sub: 'Players and NFL teams you rely on most', icon: '📦', tint: 'blue',
      endpoint: '/analysis/exposure', view: ExposureView },
    { id: 'player-lookup', title: 'Player Lookup', sub: 'Where you own a player, starting or benched', icon: '🔎', tint: 'purple',
      endpoint: '/analysis/player-lookup', view: PlayerLookupView, needs: 'player' },
  ]},
]});
