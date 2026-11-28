/* Fantasy Manager — tabs/dynasty.js
   The Dynasty tab: its result screens and the list that opens them. Needs core.js loaded first. */

// ── POWER RANKINGS VIEW ───────────────────────────────────────────────────────
// Power-rankings history lives on this device only: { [week]: { at, ranks: { league_id: {rank, score, tier, league} } } }
const PR_KEEP_WEEKS = 25;
const prKey = data => `pr.${data.username || 'me'}.${data.season || ''}`;
function prSave(data) {
  const all = store.get(prKey(data), {});
  const ranks = {};
  data.results.forEach(r => { ranks[r.league_id || r.league] = { rank: r.power_rank, score: r.score, tier: r.tier, league: r.league }; });
  all[data.as_of_week] = { at: Date.now(), ranks };
  const weeks = Object.keys(all).map(Number).sort((x, y) => y - x);
  weeks.slice(PR_KEEP_WEEKS).forEach(w => delete all[w]);
  store.set(prKey(data), all);
}
function prPrevious(data) {
  const all = store.get(prKey(data), {});
  const earlier = Object.keys(all).map(Number).filter(w => w < data.as_of_week).sort((x, y) => y - x);
  return earlier.length ? { week: earlier[0], ...all[earlier[0]] } : null;
}

function PowerRankingsView({ data }) {
  const [open, setOpen] = useState(null);
  const [showAll, setShowAll] = useState(false);
  const prev = data?.results?.length ? prPrevious(data) : null;     // read before this run is saved
  useEffect(() => { if (data?.results?.length && data.as_of_week) prSave(data); }, [data]);
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No leagues found.'));
  const sm = data.summary || {};
  const recColor = p => p > 0.5 ? 'var(--accent)' : p < 0.5 ? 'var(--accent2)' : 'var(--text2)';
  const scoreColor = v => v >= 70 ? 'var(--accent)' : v >= 50 ? 'var(--accent4)' : v >= 35 ? 'var(--accent3)' : 'var(--accent2)';
  const tierChips = Object.entries(sm.tiers || {});

  // Diff against the most recent earlier week saved on this device
  const diff = {};
  if (prev) data.results.forEach(r => {
    const p = prev.ranks[r.league_id || r.league];
    diff[r.league_id || r.league] = p
      ? { move: p.rank - r.power_rank, dScore: Math.round((r.score - p.score) * 10) / 10, tierFrom: p.tier !== r.tier ? p.tier : null }
      : { isNew: true };
  });
  const moves = Object.entries(diff).filter(([, d]) => !d.isNew).map(([k, d]) => ({ k, ...d, r: data.results.find(x => (x.league_id || x.league) === k) }));
  const risers = moves.filter(m => m.move > 0).sort((x, y) => y.move - x.move);
  const fallers = moves.filter(m => m.move < 0).sort((x, y) => x.move - y.move);
  const tierChanges = moves.filter(m => m.tierFrom);
  const dropped = prev ? Object.entries(prev.ranks).filter(([k]) => !data.results.some(r => (r.league_id || r.league) === k)).map(([, v]) => v.league) : [];

  const arrow = d => !d ? null
    : d.isNew ? e('span', { style: { fontSize: 10, fontWeight: 800, color: 'var(--accent4)' } }, 'NEW')
    : d.move > 0 ? e('span', { style: { fontSize: 12, fontWeight: 800, color: 'var(--accent)' } }, `▲${d.move}`)
    : d.move < 0 ? e('span', { style: { fontSize: 12, fontWeight: 800, color: 'var(--accent2)' } }, `▼${-d.move}`)
    : e('span', { style: { fontSize: 12, color: 'var(--text3)' } }, '–');
  const moverLine = (m, up) => e('div', { key: m.k, style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 13, padding: '6px 0', borderBottom: '1px solid var(--border)' } },
    e('span', { style: { flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, m.r.league),
    e('span', { style: { whiteSpace: 'nowrap', color: 'var(--text3)', fontSize: 12 } }, `#${m.r.power_rank + m.move} → #${m.r.power_rank} `),
    e('b', { style: { color: up ? 'var(--accent)' : 'var(--accent2)', minWidth: 34, textAlign: 'right' } }, up ? `▲${m.move}` : `▼${-m.move}`));
  const N = 5;

  return e('div', null,
    e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: 'var(--text2)', marginBottom: 4 } }, `POWER RANKINGS · ${sm.leagues} TEAMS`),
    e('div', { style: { fontSize: 12, color: 'var(--text3)', marginBottom: 10 } },
      data.records_through > 0 ? `Standings through week ${data.records_through} (entering week ${data.as_of_week}).` : 'Before week 1 — roster rating only.'),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.above_500 ?? 0, label: 'Above .500', color: 'var(--accent)' }),
      e(StatTile, { value: sm.in_playoff_spot ?? 0, label: 'In Playoff Spot', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.avg_score ?? 0, label: 'Avg Score', color: scoreColor(sm.avg_score || 0) }),
      e(StatTile, { value: (sm.leagues ?? 0) - (sm.above_500 ?? 0), label: 'At/Below .500', color: 'var(--accent2)' })
    ),
    // ── Movement since the previous saved week ──
    prev
      ? e(Card, { borderColor: 'var(--accent4)' },
          e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent4)', marginBottom: 8 } },
            `Since week ${prev.week} · ${risers.length} up · ${fallers.length} down · ${moves.length - risers.length - fallers.length} same`),
          risers.length === 0 && fallers.length === 0 && e('div', { style: { fontSize: 13, color: 'var(--text2)' } }, 'No rank changes.'),
          risers.length > 0 && e('div', { style: { marginBottom: 8 } },
            e('div', { style: { fontSize: 12, fontWeight: 700, color: 'var(--accent)', margin: '4px 0' } }, '📈 Biggest risers'),
            (showAll ? risers : risers.slice(0, N)).map(m => moverLine(m, true))),
          fallers.length > 0 && e('div', { style: { marginBottom: 4 } },
            e('div', { style: { fontSize: 12, fontWeight: 700, color: 'var(--accent2)', margin: '4px 0' } }, '📉 Biggest fallers'),
            (showAll ? fallers : fallers.slice(0, N)).map(m => moverLine(m, false))),
          (risers.length > N || fallers.length > N) && e('button', { className: 'secondary', style: { width: '100%', marginTop: 8, padding: '8px', minHeight: 0, fontSize: 13 }, onClick: () => setShowAll(!showAll) }, showAll ? 'Show fewer' : 'Show all movers'),
          tierChanges.length > 0 && e('div', { style: { fontSize: 12, color: 'var(--text2)', marginTop: 8, lineHeight: 1.6 } },
            e('b', null, 'Tier changes: '), tierChanges.map(m => `${m.r.league} (${m.tierFrom} → ${m.r.tier})`).join(' · ')),
          dropped.length > 0 && e('div', { style: { fontSize: 11, color: 'var(--text3)', marginTop: 6 } }, `No longer listed: ${dropped.join(', ')}`))
      : e(Alert, { type: 'info' }, e('p', null,
          `Saved this as week ${data.as_of_week}. Movement arrows appear once an earlier week is saved — run this again next week, or set the week chip to ${Math.max(data.as_of_week - 1, 1)} and run it once now.`)),
    tierChips.length > 0 && e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 } },
      tierChips.map(([t, n]) => e('span', { key: t, style: { fontSize: 11, padding: '3px 8px', borderRadius: 6, border: '1px solid var(--border)', color: 'var(--text2)' } }, `${t}: ${n}`))),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 10 } }, 'Best-performing team first. Tap a row for the score breakdown.'),
    data.results.map(r => {
      const d = diff[r.league_id || r.league];
      return e('div', { key: r.league_id || r.league, onClick: () => setOpen(open === r.league ? null : r.league), style: { display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${r.tier_color}`, borderRadius: 8, marginBottom: 6, cursor: 'pointer', flexWrap: 'wrap' } },
        e('div', { style: { minWidth: 30, textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.3rem', color: 'var(--text3)', lineHeight: 1 } }, r.power_rank),
          arrow(d)),
        e('div', { style: { flex: 1, minWidth: 0 } },
          e('div', { style: { fontWeight: 700, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.league),
          e('div', { style: { fontSize: 11, color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, `${r.team} · #${r.rank}/${r.total_teams}${r.in_playoffs ? ' · playoff spot' : ''}`)),
        e('div', { style: { textAlign: 'center', minWidth: 54 } },
          e('div', { style: { fontSize: 13, fontWeight: 700, color: recColor(r.win_pct) } }, r.record),
          e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, 'record')),
        e('div', { style: { textAlign: 'center', minWidth: 84 } },
          e('div', { style: { fontSize: 11, fontWeight: 700, color: r.tier_color } }, `${r.tier_icon} ${r.tier}`),
          e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, `roster ${r.roster_composite}`)),
        e('div', { style: { textAlign: 'right', minWidth: 44 } },
          e('div', { style: { fontSize: 15, fontWeight: 800, color: scoreColor(r.score) } }, r.score),
          e('div', { style: { fontSize: 9, color: d && !d.isNew && d.dScore ? (d.dScore > 0 ? 'var(--accent)' : 'var(--accent2)') : 'var(--text3)' } },
            d && !d.isNew && d.dScore ? `${d.dScore > 0 ? '+' : ''}${d.dScore}` : 'score')),
        open === r.league && e('div', { style: { flexBasis: '100%', fontSize: 11, color: 'var(--text2)', paddingTop: 6, borderTop: '1px solid var(--border)', marginTop: 4 } },
          `Record ${r.record_score} × 50% · Roster ${r.roster_score} × 35% · Standing ${r.standing_score} × 15% · PF ${r.pf} / PA ${r.pa} · starters ${Math.round(r.pts_vs_avg * 100)}% of league avg`,
          d && d.tierFrom ? ` · tier was ${d.tierFrom}` : '')
      );
    }),
    e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } },
      'Rank history is saved on this device (one list per week). Past weeks rebuild records from Sleeper; roster strength always uses today’s rosters.'),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 4 } }, data.note)
  );
}

function OverviewView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No data found.'));
  const totalW = data.results.reduce((s, r) => s + (parseInt(r.record?.split('-')[0]) || 0), 0);
  const totalL = data.results.reduce((s, r) => s + (parseInt(r.record?.split('-')[1]) || 0), 0);
  const avgComp = (data.results.reduce((s, r) => s + r.composite, 0) / data.results.length).toFixed(2);
  const tierCounts = {};
  const stratCounts = {};
  data.results.forEach(r => { tierCounts[r.tier] = (tierCounts[r.tier] || 0) + 1; stratCounts[r.strategy] = (stratCounts[r.strategy] || 0) + 1; });

  const TIER_COLORS = { Juggernaut: 'var(--accent)', Contender: 'var(--accent4)', Fringe: 'var(--accent3)', Rebuild: 'var(--accent2)' };
  const STRAT_COLORS = { 'Win Now': 'var(--accent)', 'Sell High': 'var(--accent4)', Patience: 'var(--accent3)', 'Trust the Process': '#ff8c42', 'Full Rebuild': 'var(--accent2)' };

  return e('div', null,
    e('div', { className: 'grid-2', style: { marginBottom: 16 } },
      e('div', { style: { padding: '14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, textAlign: 'center' } },
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6 } }, 'Overall Record'),
        e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '2rem' } },
          e('span', { style: { color: 'var(--accent)' } }, totalW), e('span', { style: { color: 'var(--text3)' } }, '-'), e('span', { style: { color: 'var(--accent2)' } }, totalL)
        )
      ),
      e('div', { style: { padding: '14px', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 12, textAlign: 'center' } },
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6 } }, 'Avg Score'),
        e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '2rem', color: 'var(--accent4)' } }, avgComp),
        e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, 'out of 5.0')
      )
    ),
    e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 } },
      Object.entries(tierCounts).map(([t, c]) => e('div', { key: t, style: { padding: '5px 12px', borderRadius: 20, border: `1px solid ${TIER_COLORS[t]}`, fontSize: 12, fontWeight: 700, color: TIER_COLORS[t], background: 'rgba(255,255,255,0.04)' } }, `${t}: ${c}`))
    ),
    e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 20 } },
      Object.entries(stratCounts).map(([s, c]) => e('div', { key: s, style: { padding: '5px 12px', borderRadius: 20, border: `1px solid ${STRAT_COLORS[s]}`, fontSize: 12, fontWeight: 700, color: STRAT_COLORS[s], background: 'rgba(255,255,255,0.04)' } }, `${s}: ${c}`))
    ),
    e(Card, { style: { marginBottom: 20 } },
      e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: 'var(--text2)', marginBottom: 12 } }, 'ALL LEAGUES OVERVIEW'),
      data.results.map(r => {
        const bars = [
          { label: 'Roster', score: r.scores?.Roster, color: 'var(--accent4)' },
          { label: 'Draft', score: r.scores?.Draft, color: 'var(--purple)' },
          { label: 'Age', score: r.scores?.Age, color: 'var(--accent3)' },
          { label: 'Depth', score: r.scores?.Depth, color: 'var(--accent)' },
          { label: 'Record', score: r.scores?.Record, color: '#00e5a0' },
        ];
        return e('div', { key: r.league, style: { marginBottom: 14 } },
          e('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 } },
            e('span', { style: { fontWeight: 700 } }, r.league),
            e('span', { style: { color: STRAT_COLORS[r.strategy], fontWeight: 700 } }, `${r.strat_icon} ${r.strategy} · ${r.tier_icon} ${r.tier}`)
          ),
          bars.map(b => e(BarRow, { key: b.label, ...b }))
        );
      })
    ),
    data.results.map(r => e(Card, { key: r.league, borderColor: r.tier_color },
      e('div', { className: 'card-header' },
        e('div', null,
          e('div', { className: 'card-title' }, r.league),
          e('div', { className: 'card-subtitle' }, `${r.team || ''} · ${r.record} · #${r.rank}/${r.total_teams}`)
        ),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.3rem', color: r.tier_color } }, `${r.tier_icon} ${r.tier}`),
          e('div', { style: { fontWeight: 700, color: r.strat_color, fontSize: 13 } }, `${r.strat_icon} ${r.strategy}`),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${r.composite} / 5.0`)
        )
      ),
      e('div', { style: { fontSize: 12, color: 'var(--text2)', marginBottom: 12, fontStyle: 'italic' } }),
      e('div', { className: 'grid-2', style: { marginBottom: 12 } },
        e('div', { style: { padding: '8px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8 } },
          e('div', { style: { fontSize: 9, color: 'var(--text3)', marginBottom: 2 } }, 'Starter Pts'),
          e('div', { style: { fontSize: 13, fontWeight: 700 } }, r.starter_pts, e('span', { style: { fontSize: 10, color: r.pts_vs_avg >= 1 ? 'var(--accent)' : 'var(--accent2)', marginLeft: 4 } }, `${r.pts_vs_avg >= 1 ? '+' : ''}${((r.pts_vs_avg - 1) * 100).toFixed(0)}% vs avg`))
        ),
        e('div', { style: { padding: '8px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8 } },
          e('div', { style: { fontSize: 9, color: 'var(--text3)', marginBottom: 2 } }, 'Avg Age'),
          e('div', { style: { fontSize: 13, fontWeight: 700 } }, r.avg_age)
        )
      ),
      e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6 } }, 'Action Items'),
      r.strat_actions?.map((a, i) => e('div', { key: i, style: { display: 'flex', gap: 8, padding: '6px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderLeft: `2px solid ${r.strat_color}`, borderRadius: 6, marginBottom: 4, fontSize: 12, color: 'var(--text2)' } },
        e('span', { style: { fontFamily: 'Bebas Neue', color: r.strat_color, flexShrink: 0 } }, i + 1), a
      ))
    ))
  );
}

// ── TIER RECORDS VIEW ─────────────────────────────────────────────────────────
function TierRecordsView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No league data found.'));
  const S = data.summary || {};
  const [open, setOpen] = useState(() => new Set(data.results.filter(r => r.flagged).map(r => r.league)));
  const toggle = (k) => setOpen(prev => { const n = new Set(prev); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const rec = r => `${r.wins}-${r.losses}${r.ties ? '-' + r.ties : ''}`;
  const pct = v => v == null ? '—' : `.${String(Math.round(v * 1000)).padStart(3, '0')}`;

  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: S.flagged, label: 'Flagged', color: S.flagged ? 'var(--accent2)' : 'var(--text3)' }),
      e(StatTile, { value: S.fire_sale, label: 'Fire Sale', color: S.fire_sale ? 'var(--accent2)' : 'var(--text3)' }),
      e(StatTile, { value: S.on_track, label: 'On Track', color: 'var(--accent)' }),
      e(StatTile, { value: S.overachieving, label: 'Overachieving', color: 'var(--accent4)' })
    ),
    (S.by_tier || []).map(t => {
      const rows = data.results.filter(r => r.tier === t.tier);
      return e('div', { key: t.tier, style: { marginBottom: 18 } },
        e('div', { style: { display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', padding: '8px 4px', borderBottom: `2px solid ${t.color}`, marginBottom: 8 } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.3rem', letterSpacing: 2, color: t.color } }, `${t.icon} ${t.tier}`),
          e('div', { style: { display: 'flex', gap: 10, alignItems: 'baseline' } },
            e('span', { style: { fontFamily: 'Bebas Neue', fontSize: '1.3rem', color: 'var(--text)' } }, `${t.wins}-${t.losses}${t.ties ? '-' + t.ties : ''}`),
            e('span', { style: { fontSize: 11, color: t.win_pct != null && t.win_pct < 0.5 ? 'var(--accent2)' : 'var(--text3)' } }, pct(t.win_pct)),
            e('span', { style: { fontSize: 11, color: 'var(--text3)' } }, `${t.leagues} league${t.leagues !== 1 ? 's' : ''}`),
            t.flagged > 0 && e(Tag, { color: 'red' }, `🚩 ${t.flagged}`)
          )
        ),
        rows.map(r => {
          const isOpen = open.has(r.league);
          const wpColor = r.games_played === 0 ? 'var(--text3)' : r.win_pct >= 0.5 ? 'var(--accent)' : 'var(--accent2)';
          const luckColor = r.luck == null ? 'var(--text3)' : r.luck <= -1 ? 'var(--accent3)' : r.luck >= 1 ? 'var(--accent4)' : 'var(--text3)';
          const luckLabel = r.luck == null ? '' : r.luck <= -1 ? 'unlucky' : r.luck >= 1 ? 'lucky' : 'fair';
          return e('div', { key: r.league, style: { background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${r.status_color}`, borderRadius: 10, marginBottom: 6, overflow: 'hidden' } },
            e('button', { onClick: () => toggle(r.league), style: { width: '100%', background: 'transparent', border: 'none', textAlign: 'left', cursor: 'pointer', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10 } },
              e('div', { style: { flex: 1, minWidth: 0 } },
                e('div', { style: { fontSize: 13, fontWeight: 700, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.league),
                r.team && e('div', { style: { fontSize: 11, color: 'var(--text2)', marginTop: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.team),
                e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 2 } },
                  `#${r.rank}/${r.total_teams} · ${r.in_playoffs ? 'in playoff spot' : r.games_back > 0 ? `${r.games_back} back` : 'on the line'} · ${r.games_left} left`)
              ),
              e('div', { style: { textAlign: 'right', minWidth: 62 } },
                e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.2rem', color: wpColor, lineHeight: 1 } }, rec(r)),
                e('div', { style: { fontSize: 10, color: wpColor } }, pct(r.games_played ? r.win_pct : null))
              ),
              r.exp_wins != null && e('div', { style: { textAlign: 'right', minWidth: 56 } },
                e('div', { style: { fontSize: 11, fontWeight: 700, color: luckColor } }, `${r.luck > 0 ? '+' : ''}${r.luck}`),
                e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, `${luckLabel} · exp ${r.exp_wins}`)
              ),
              e('span', { style: { fontSize: 10, fontWeight: 800, color: r.status_color, border: `1px solid ${r.status_color}`, borderRadius: 20, padding: '3px 8px', whiteSpace: 'nowrap' } }, `${r.flagged ? '🚩 ' : ''}${r.status}`),
              e('span', { style: { fontSize: 10, color: 'var(--text3)' } }, isOpen ? '▲' : '▼')
            ),
            isOpen && e('div', { style: { padding: '0 12px 12px', borderTop: '1px solid var(--border)' } },
              e('div', { style: { fontSize: 12, color: 'var(--text2)', lineHeight: 1.5, padding: '10px 0 8px' } }, r.headline),
              r.actions?.map((a, i) => e('div', { key: i, style: { display: 'flex', gap: 8, padding: '6px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderLeft: `2px solid ${r.status_color}`, borderRadius: 6, marginBottom: 4, fontSize: 12, color: 'var(--text2)' } },
                e('span', { style: { fontFamily: 'Bebas Neue', color: r.status_color, flexShrink: 0 } }, i + 1), a
              )),
              e('div', { style: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 } },
                e(Tag, { color: 'gray' }, `PF ${r.fpts?.toFixed(0)} · PA ${r.fpa?.toFixed(0)}`),
                e(Tag, { color: 'gray' }, `roster score ${r.roster_composite}/5`),
                r.blended_tier !== r.tier && e(Tag, { color: 'orange' }, `record-adjusted: ${r.blended_tier}`),
                e(Tag, { color: 'gray' }, `avg age ${r.avg_age}`)
              )
            )
          );
        })
      );
    })
  );
}

// ── TEAM DEEP DIVE VIEW ───────────────────────────────────────────────────────
function DeepDiveView({ data }) {
  if (!data?.league) return e(Alert, { type: 'info' }, e('p', null, 'No data.'));
  const [openPos, setOpenPos] = useState(() => new Set(data.position_groups.filter(g => g.need).map(g => g.position)));
  const togglePos = k => setOpenPos(p => { const n = new Set(p); n.has(k) ? n.delete(k) : n.add(k); return n; });
  const v = data.verdict || {};
  const GRADE_COLOR = { A: 'var(--accent)', B: 'var(--accent4)', C: 'var(--accent3)', D: '#ff8c42', F: 'var(--accent2)', '—': 'var(--text3)' };
  const pct = x => x == null ? '—' : `.${String(Math.round(x * 1000)).padStart(3, '0')}`;
  const Section = ({ title, right, children }) => e('div', { style: { marginBottom: 18 } },
    e('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8, paddingBottom: 4, borderBottom: '1px solid var(--border)' } },
      e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.1rem', letterSpacing: 2, color: 'var(--text2)' } }, title),
      right && e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, right)
    ),
    children
  );
  const roleTag = p => p.role === 'starter' ? e(Tag, { color: 'green' }, p.slot || 'STR') : p.role === 'taxi' ? e(Tag, { color: 'gray' }, 'TAXI') : p.role === 'ir' ? e(Tag, { color: 'red' }, 'IR') : e(Tag, { color: 'gray' }, 'BN');
  const PlayerLine = ({ p }) => e('div', { className: 'player-row' },
    roleTag(p),
    e(PosBadge, { pos: p.position }),
    e('div', { style: { flex: 1, minWidth: 0 } },
      e('div', { style: { fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name,
        p.injury_status && e('span', { style: { fontSize: 9, color: 'var(--accent2)', marginLeft: 6, fontWeight: 700 } }, p.injury_status.toUpperCase())),
      e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${p.team}${p.age ? ` · ${p.age}y` : ''}${p.bye_week ? ` · bye ${p.bye_week}` : ''}${p.ytd_gp ? ` · ${p.ytd_avg}/g YTD` : ''}`)
    ),
    e('div', { style: { textAlign: 'right' } },
      e('div', { style: { fontSize: 12, fontWeight: 700, color: p.proj >= 15 ? 'var(--accent)' : p.proj > 0 ? 'var(--text2)' : 'var(--accent2)' } }, p.proj),
      e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, p.has_played ? 'played' : 'proj')
    )
  );

  return e('div', null,
    // ── header ──
    e(Card, { borderColor: data.tier_color },
      e('div', { className: 'card-header' },
        e('div', null,
          e('div', { className: 'card-title', style: { fontSize: 17 } }, data.league.name),
          e('div', { className: 'card-subtitle' }, `${data.team} · ${data.league.format}`)
        ),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.8rem', lineHeight: 1, color: data.win_pct >= 0.5 ? 'var(--accent)' : 'var(--accent2)' } }, data.record),
          e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, `#${data.rank}/${data.total_teams} · ${data.in_playoffs ? 'in playoff spot' : 'outside playoffs'}`)
        )
      ),
      e('div', { style: { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 } },
        e('span', { style: { padding: '4px 10px', borderRadius: 20, border: `1px solid ${data.tier_color}`, color: data.tier_color, fontSize: 11, fontWeight: 700 } }, `${data.tier_icon} ${data.tier} roster`),
        data.blended_tier !== data.tier && e(Tag, { color: 'orange' }, `record-adjusted: ${data.blended_tier}`),
        e('span', { style: { padding: '4px 10px', borderRadius: 20, border: `1px solid ${data.strat_color}`, color: data.strat_color, fontSize: 11, fontWeight: 700 } }, `${data.strat_icon} ${data.strategy}`),
        e(Tag, { color: 'gray' }, `avg age ${data.avg_age}`),
        e(Tag, { color: 'gray' }, `${data.pts_vs_avg >= 1 ? '+' : ''}${((data.pts_vs_avg - 1) * 100).toFixed(0)}% vs league starters`)
      ),
      // verdict banner
      e('div', { style: { padding: '12px 14px', background: 'rgba(255,255,255,0.03)', border: `1px solid ${v.status_color}`, borderLeft: `4px solid ${v.status_color}`, borderRadius: 8 } },
        e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.3rem', letterSpacing: 2, color: v.status_color, marginBottom: 4 } }, `${v.flagged ? '🚩 ' : ''}${v.status}`),
        e('div', { style: { fontSize: 12, color: 'var(--text2)', lineHeight: 1.5, marginBottom: 8 } }, v.headline),
        (data.specifics || []).map((t, i) => e('div', { key: 's' + i, style: { fontSize: 12, color: 'var(--text)', padding: '5px 10px', background: 'rgba(255,179,71,0.08)', border: '1px solid rgba(255,179,71,0.3)', borderRadius: 6, marginBottom: 4 } }, '⚠ ' + t)),
        (v.actions || []).map((a, i) => e('div', { key: i, style: { display: 'flex', gap: 8, padding: '6px 10px', background: 'var(--bg)', border: '1px solid var(--border)', borderLeft: `2px solid ${v.status_color}`, borderRadius: 6, marginBottom: 4, fontSize: 12, color: 'var(--text2)' } },
          e('span', { style: { fontFamily: 'Bebas Neue', color: v.status_color, flexShrink: 0 } }, i + 1), a))
      )
    ),

    // ── tiles ──
    e('div', { className: 'stat-row' },
      e(StatTile, { value: pct(data.win_pct), label: 'Win %', color: data.win_pct >= 0.5 ? 'var(--accent)' : 'var(--accent2)' }),
      e(StatTile, { value: v.luck == null ? '—' : `${v.luck > 0 ? '+' : ''}${v.luck}`, label: `Luck (exp ${v.exp_wins ?? '—'} W)`, color: v.luck == null ? 'var(--text3)' : v.luck <= -1 ? 'var(--accent3)' : v.luck >= 1 ? 'var(--accent4)' : 'var(--text2)' }),
      e(StatTile, { value: data.proj_final, label: 'Proj Final', color: 'var(--accent4)' }),
      e(StatTile, { value: data.total_left_on_bench, label: 'Pts On Bench (season)', color: data.total_left_on_bench >= 20 ? 'var(--accent3)' : 'var(--text2)' })
    ),

    // ── score bars ──
    e(Card, null,
      [['Roster', 'var(--accent4)'], ['Draft', 'var(--purple)'], ['Age', 'var(--accent3)'], ['Depth', 'var(--accent)'], ['Record', '#00e5a0']]
        .map(([k, c]) => e(BarRow, { key: k, label: k, score: data.scores?.[k] ?? 0, color: c })),
      e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 6 } }, `roster score ${data.roster_composite}/5 · with record ${data.composite}/5`)
    ),

    // ── position groups ──
    e(Section, { title: 'POSITION GROUPS', right: 'starter avg vs league starter avg' },
      e('div', { className: 'grid-2' },
        data.position_groups.map(g => {
          const gc = GRADE_COLOR[g.grade] || 'var(--text3)';
          const open = openPos.has(g.position);
          return e('div', { key: g.position, style: { background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${gc}`, borderRadius: 10, overflow: 'hidden' } },
            e('button', { onClick: () => togglePos(g.position), style: { width: '100%', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left', padding: '10px 12px', display: 'flex', alignItems: 'center', gap: 10 } },
              e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '2rem', lineHeight: 1, color: gc, minWidth: 30 } }, g.grade),
              e('div', { style: { flex: 1 } },
                e('div', { style: { display: 'flex', alignItems: 'center', gap: 6 } }, e(PosBadge, { pos: g.position }),
                  e('span', { style: { fontSize: 12, fontWeight: 700, color: 'var(--text)' } }, `${g.my_avg} vs ${g.league_avg}`),
                  g.need && e(Tag, { color: 'red' }, 'NEED'), g.surplus && e(Tag, { color: 'blue' }, 'SURPLUS')),
                e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 2 } }, `${g.count} rostered · ${g.starters} starting (${g.dedicated_slots} slot${g.dedicated_slots !== 1 ? 's' : ''}${g.flex_slots ? ` + ${g.flex_slots} flex` : ''}) · ${g.starter_quality} starter-quality`)
              ),
              e('span', { style: { fontSize: 10, color: 'var(--text3)' } }, open ? '▲' : '▼')
            ),
            open && e('div', { style: { padding: '0 8px 8px' } }, g.players.map(p => e(PlayerLine, { key: p.id, p })))
          );
        })
      )
    ),

    // ── this week's lineup ──
    e(Section, { title: `WEEK ${data.week} LINEUP`, right: `current ${data.lineup.current_pts} → optimal ${data.lineup.optimal_pts}` },
      data.lineup.zero_starters?.length > 0 && e(Alert, { type: 'error' }, e('p', null, `0-point starters: ${data.lineup.zero_starters.map(p => p.name).join(', ')}`)),
      data.lineup.injured_starters?.length > 0 && e(Alert, { type: 'error' }, e('p', null, `Injured starters: ${data.lineup.injured_starters.map(p => `${p.name} (${(p.injury_status || '').toUpperCase()})`).join(', ')}`)),
      data.lineup.moves?.length ? e(MovesList, { moves: data.lineup.moves, ptsKey: 'pts' }) : e('div', { style: { fontSize: 12, color: 'var(--accent)', marginBottom: 8 } }, '✅ Lineup is optimal.'),
      data.lineup.slots.map((sl, i) => sl.player
        ? e('div', { key: i, className: 'player-row', style: { opacity: sl.locked ? 0.6 : 1 } },
            e('span', { style: { fontSize: 9, color: 'var(--text3)', minWidth: 52, textAlign: 'center' } }, sl.locked ? `🔒 ${sl.slot}` : sl.slot),
            e(PosBadge, { pos: sl.player.position }), e('span', { className: 'player-name' }, sl.player.name), e('span', { className: 'player-team' }, sl.player.team),
            e('span', { className: 'player-pts', style: { color: sl.player.pts >= 15 ? 'var(--accent)' : 'var(--text2)' } }, sl.player.pts))
        : e('div', { key: i, className: 'player-row', style: { opacity: 0.5 } }, e('span', { style: { fontSize: 9, color: 'var(--text3)', minWidth: 52, textAlign: 'center' } }, sl.slot), e('span', { style: { fontSize: 11, color: 'var(--accent2)' } }, 'Empty'))
      )
    ),

    // ── season log ──
    e(Section, { title: 'SEASON LOG', right: data.season_log.length ? `avg efficiency ${data.avg_efficiency}% · ${data.games_cost_by_lineup} game${data.games_cost_by_lineup !== 1 ? 's' : ''} lost to lineup` : 'no completed weeks' },
      data.season_log.map(w => {
        const c = w.won ? 'var(--accent)' : w.won === false ? 'var(--accent2)' : 'var(--accent3)';
        const ec = w.efficiency >= 95 ? 'var(--accent)' : w.efficiency >= 85 ? 'var(--accent3)' : 'var(--accent2)';
        return e('div', { key: w.week, style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${c}`, borderRadius: 8, marginBottom: 4 } },
          e('div', { style: { minWidth: 34, fontSize: 10, color: 'var(--text3)' } }, `Wk ${w.week}`),
          e('div', { style: { minWidth: 26, fontWeight: 800, color: c, fontSize: 13 } }, w.won ? 'W' : w.won === false ? 'L' : 'T'),
          e('div', { style: { flex: 1, minWidth: 0 } },
            e('div', { style: { fontSize: 12, fontWeight: 600 } }, `${w.my_pts.toFixed(1)} – ${w.opp_pts?.toFixed(1) ?? '?'}`, e('span', { style: { fontSize: 10, color: 'var(--text3)', fontWeight: 400 } }, ` vs ${w.opp_name}`)),
            e('div', { className: 'bar-track', style: { height: 4, marginTop: 4 } }, e('div', { className: 'bar-fill', style: { width: `${w.efficiency}%`, background: ec } }))
          ),
          e('div', { style: { textAlign: 'right', minWidth: 70 } },
            e('div', { style: { fontSize: 11, fontWeight: 700, color: ec } }, `${w.efficiency}%`),
            e('div', { style: { fontSize: 9, color: w.left_on_bench > 0 ? 'var(--accent3)' : 'var(--text3)' } }, w.left_on_bench > 0 ? `${w.left_on_bench.toFixed(1)} on bench` : 'optimal')
          ),
          w.cost_the_game && e(Tag, { color: 'red' }, 'COST W')
        );
      })
    ),

    // ── schedule ──
    e(Section, { title: 'REMAINING SCHEDULE', right: data.schedule.length ? `${data.exp_remaining_wins} expected wins of ${data.schedule.length} · SOS ${data.schedule_strength} vs lg ${data.league_avg_strength}` : 'regular season over' },
      data.schedule.map(g => {
        const pc = g.win_prob >= 60 ? 'var(--accent)' : g.win_prob >= 40 ? 'var(--accent3)' : 'var(--accent2)';
        return e('div', { key: g.week, style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', background: g.is_current ? 'rgba(92,158,255,0.06)' : 'var(--surface)', border: `1px solid ${g.is_current ? 'rgba(92,158,255,0.4)' : 'var(--border)'}`, borderRadius: 8, marginBottom: 4 } },
          e('div', { style: { minWidth: 34, fontSize: 10, color: 'var(--text3)' } }, `Wk ${g.week}`),
          e('div', { style: { flex: 1, minWidth: 0 } },
            e('div', { style: { fontSize: 12, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, g.opp_name, e('span', { style: { fontSize: 10, color: 'var(--text3)', fontWeight: 400 } }, ` (${g.opp_record})`)),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${g.my_proj} vs ${g.opp_proj} proj`)
          ),
          e('div', { style: { width: 80 } }, e('div', { className: 'bar-track', style: { height: 6 } }, e('div', { className: 'bar-fill', style: { width: `${g.win_prob}%`, background: pc } }))),
          e('div', { style: { minWidth: 34, textAlign: 'right', fontSize: 12, fontWeight: 700, color: pc } }, `${g.win_prob}%`)
        );
      })
    ),

    // ── trade assets + draft ──
    e('div', { className: 'grid-2' },
      e(Card, null,
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent2)', marginBottom: 6 } }, '💰 Sell Candidates (vets with value)'),
        data.sell_candidates.length ? data.sell_candidates.map(p => e(PlayerLine, { key: p.id, p })) : e('div', { style: { fontSize: 12, color: 'var(--text3)' } }, 'No high-value veterans to move.'),
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', margin: '12px 0 6px' } }, '🌱 Young Core (≤25, starter quality)'),
        data.young_core.length ? data.young_core.map(p => e(PlayerLine, { key: p.id, p })) : e('div', { style: { fontSize: 12, color: 'var(--text3)' } }, 'No young starter-quality players.'),
        e('div', { style: { display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 10 } },
          data.needs.map(n => e(Tag, { key: 'n' + n, color: 'red' }, `NEED ${n}`)),
          data.surplus.map(n => e(Tag, { key: 's' + n, color: 'blue' }, `SURPLUS ${n}`))
        )
      ),
      e(Card, null,
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--purple)', marginBottom: 6 } }, `📋 ${data.draft.season} Draft Capital`),
        e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
          data.draft.picks.map((p, i) => e('div', { key: i, style: { padding: '6px 10px', background: 'var(--surface2)', border: `1px solid ${p.own ? 'var(--border)' : 'rgba(92,158,255,0.4)'}`, borderRadius: 8, fontSize: 11 } },
            e('div', { style: { fontWeight: 700, color: 'var(--purple)' } }, `Rd ${p.round}`),
            !p.own && e('div', { style: { fontSize: 9, color: 'var(--accent4)' } }, `via ${p.original_owner}`)
          )),
          data.draft.traded_away.map((t, i) => e('div', { key: 'ta' + i, style: { padding: '6px 10px', background: 'rgba(255,92,92,0.06)', border: '1px solid rgba(255,92,92,0.3)', borderRadius: 8, fontSize: 11 } },
            e('div', { style: { fontWeight: 700, color: 'var(--accent2)', textDecoration: 'line-through' } }, `Rd ${t.round}`),
            e('div', { style: { fontSize: 9, color: 'var(--accent2)' } }, `to ${t.to}`)
          ))
        ),
        e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, `${data.draft.picks.length} of ${data.draft.rounds} own-slot picks owned${data.draft.traded_away.length ? ` · ${data.draft.traded_away.length} traded away` : ''}`)
      )
    )
  );
}

// ── TRADE FINDER VIEW ─────────────────────────────────────────────────────────
function TradeFinderView({ data }) {
  if (!data) return null;
  if (data.ambiguous) return e(Card, { borderColor: 'var(--accent3)' },
    e('div', { style: { fontSize: 12, marginBottom: 8 } }, `Several players match "${data.query}" — enter the full name:`),
    data.matches.map(m => e('div', { key: m.id, className: 'player-row' }, e(PosBadge, { pos: m.position }), e('span', { className: 'player-name' }, m.name), e('span', { className: 'player-team' }, m.team))));
  const p = data.player, sm = data.summary || {};
  const GRADE = { A: 'var(--accent)', B: 'var(--accent4)', C: 'var(--accent3)', D: 'var(--accent2)' };
  const asset = a => e('div', { key: a.id, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border)' } },
    a.type === 'pick' ? e('span', { className: 'pos', style: { background: 'rgba(255,179,71,0.15)', color: 'var(--accent3)' } }, 'PICK') : e(PosBadge, { pos: a.position }),
    e('div', { style: { flex: 1, minWidth: 0 } },
      e('div', { style: { fontSize: 13, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, a.name),
      a.type === 'player' && e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${a.team}${a.age ? ` · age ${a.age}` : ''} · ${a.ppg} ppg`)),
    e('span', { style: { fontSize: 12, fontWeight: 700, color: 'var(--text2)' } }, a.value));
  const offer = (o, i) => e('div', { key: i, style: { padding: '10px 12px', background: 'var(--surface2, var(--surface))', border: `1px solid ${GRADE[o.grade]}`, borderRadius: 10, marginBottom: 8 } },
    e('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 } },
      e('span', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)' } }, `Offer ${i + 1} · ${o.has_pick ? 'with pick' : 'players'} · ${o.n}-for-1`),
      e('span', { style: { fontSize: 14, fontWeight: 800, color: GRADE[o.grade] } }, `Grade ${o.grade}`)),
    o.assets.map(asset),
    e('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 11, marginTop: 6, color: 'var(--text2)' } },
      e('span', null, o.why), e('span', { style: { fontWeight: 700 } }, `${o.send_value} (${o.ratio}×)`)));
  return e('div', null,
    e(Card, null,
      e('div', { style: { display: 'flex', alignItems: 'center', gap: 10 } },
        e(PosBadge, { pos: p.position }),
        e('div', { style: { flex: 1 } },
          e('div', { style: { fontSize: 18, fontWeight: 800 } }, `Acquire ${p.name}`),
          e('div', { style: { fontSize: 11, color: 'var(--text2)' } }, `${p.team}${p.age ? ` · age ${p.age}` : ''}`)),
        p.injury_status && e(Tag, { color: 'red' }, p.injury_status.toUpperCase()))),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.offers_built ?? 0, label: 'Leagues w/ Offers', color: 'var(--accent)' }),
      e(StatTile, { value: sm.a_grade ?? 0, label: 'A-Grade', color: 'var(--accent)' }),
      e(StatTile, { value: sm.no_offer ?? 0, label: 'No Realistic Offer', color: 'var(--accent2)' }),
      e(StatTile, { value: `${sm.free_agent ?? 0} / ${sm.already_mine ?? 0}`, label: 'FA / Already Yours', color: 'var(--text3)' })
    ),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 12 } }, 'Most feasible league first. Values are league-specific dynasty values (production × age curve); a pick’s value is set by that league’s player pool.'),
    data.results.map(r => e(Card, { key: r.league, borderColor: GRADE[r.offers[0].grade] },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), e('div', { className: 'card-subtitle' }, `${r.team} → ${r.owner}`)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontSize: 12, fontWeight: 700, color: r.owner_tier_color } }, `${r.owner_tier} · ${r.owner_record}`),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `his value ${r.target_value}${r.target_is_their_top3 ? ' · their top-3' : ''}`))),
      e('div', { style: { fontSize: 11, color: 'var(--text2)', marginBottom: 8 } },
        `They are ${r.their_need_at_pos > 0 ? `short ${r.their_need_at_pos} at` : r.their_need_at_pos < 0 ? `${-r.their_need_at_pos} deep at` : 'even at'} ${p.position}${r.superflex ? ' · superflex' : ''} · ask ${r.ask_range[0]}–${r.ask_range[1]} (${Math.round(r.premium * 100)}% premium)`),
      r.offers.map(offer),
      e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `Protected (never offered): ${r.protected.join(', ')}`)
    )),
    data.no_offer?.length > 0 && e(Card, { borderColor: 'var(--accent2)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent2)', marginBottom: 6 } }, `No realistic offer (${data.no_offer.length})`),
      data.no_offer.map(r => e('div', { key: r.league, style: { fontSize: 11, padding: '4px 0', borderBottom: '1px solid var(--border)' } }, e('b', null, r.league), e('span', { style: { color: 'var(--text3)' } }, ` · ${r.owner} · ${r.reason}`)))),
    (data.free_agent?.length > 0 || data.mine?.length > 0) && e('div', { style: { fontSize: 11, color: 'var(--text3)', marginTop: 8, lineHeight: 1.6 } },
      data.free_agent?.length > 0 && e('div', null, `🆓 Free agent — just add him: ${data.free_agent.map(r => r.league).join(' · ')}`),
      data.mine?.length > 0 && e('div', null, `✅ Already yours: ${data.mine.map(r => r.league).join(' · ')}`)),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── PLAYOFF PICTURE VIEW ──────────────────────────────────────────────────────
function PlayoffPictureView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  if (!sm.leagues) return e(Alert, { type: 'info' }, e('p', null, 'No leagues still in the regular season.'));
  const pctColor = p => p >= 85 ? 'var(--accent)' : p >= 60 ? 'var(--accent4)' : p >= 35 ? 'var(--accent3)' : p >= 10 ? '#ff8c42' : 'var(--accent2)';
  // clinch math for your team: ✅ clinched · ❌ eliminated · magic number (in a spot) · elimination number (out)
  const CL = { clinched: ['✅ CLINCHED', 'var(--accent)'], eliminated: ['❌ ELIMINATED', 'var(--accent2)'], magic: ['🔢 MAGIC', 'var(--accent4)'], elim: ['⏳ ELIM', 'var(--accent3)'] };
  const chip = c => { if (!c || !CL[c.code]) return null; const [t, col] = CL[c.code];
    return e('span', { style: { fontSize: 10, fontWeight: 800, color: col, border: `1px solid ${col}`, borderRadius: 6, padding: '1px 6px', whiteSpace: 'nowrap', flexShrink: 0 } }, c.number != null ? `${t} ${c.number}` : t); };
  const clLine = c => !c ? null : c.code === 'magic' ? `Clinches after any ${c.number}: your wins or ${c.vs} losses`
    : c.code === 'elim' ? `Out after any ${c.number}: your losses or ${c.vs} wins` : null;
  // this week's matchup on the latest projection, and the seed if every game this week ends that way
  const twLine = r => {
    const t = r.this_week; if (!t) return null;
    const res = t.result === 'W' ? 'var(--accent)' : t.result === 'L' ? 'var(--accent2)' : 'var(--text2)';
    const tag = t.status === 'final' ? 'FINAL' : t.status === 'live' ? 'LIVE' : 'PROJ';
    const ch = t.rank_change || 0;
    const seedCol = t.proj_in && !(r.rank <= r.playoff_spots) ? 'var(--accent)' : !t.proj_in && r.rank <= r.playoff_spots ? 'var(--accent2)' : ch > 0 ? 'var(--accent)' : ch < 0 ? 'var(--accent2)' : 'var(--text2)';
    const inOut = t.proj_in && !(r.rank <= r.playoff_spots) ? ' · moves IN' : !t.proj_in && r.rank <= r.playoff_spots ? ' · drops OUT' : '';
    return e('div', { style: { marginTop: 4, paddingTop: 4, borderTop: '1px dashed var(--border)', fontSize: 11, lineHeight: 1.4 } },
      e('div', { style: { display: 'flex', gap: 6, alignItems: 'baseline' } },
        e('span', { style: { fontSize: 9, fontWeight: 800, color: t.status === 'live' ? 'var(--accent4)' : 'var(--text3)' } }, `WK ${t.week} ${tag}`),
        e('span', { style: { fontWeight: 800, color: res, whiteSpace: 'nowrap' } }, `${t.result} ${t.my_exp.toFixed(1)}–${t.opp_exp.toFixed(1)}`)),
      e('div', { style: { color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, `vs ${t.opp}`),
      e('div', { style: { color: seedCol, fontWeight: 700 } },
        `${t.status === 'final' ? 'Seed' : 'If it holds'}: #${r.rank} → #${t.proj_rank}${ch ? ` (${ch > 0 ? '▲' : '▼'}${Math.abs(ch)})` : ''} · ${t.proj_record}${inOut}`));
  };
  const row = (r, left, right) => e('div', { key: r.league, style: { display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${pctColor(r.playoff_pct)}`, borderRadius: 10, marginBottom: 6 } },
    left,
    e('div', { style: { flex: 1, minWidth: 0 } },
      e('div', { style: { display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 } },
        e('div', { style: { fontSize: 14, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', minWidth: 0 } }, r.league),
        chip(r.clinch)),
      e('div', { style: { fontSize: 11, color: 'var(--text3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } },
        `${r.team} · ${r.record} · #${r.rank}/${r.total_teams}${!r.this_week && r.next && r.next.opp ? ` · next vs ${r.next.opp}` : ''}${r.next && r.next.swing >= 20 ? ' 🔥' : ''}`),
      clLine(r.clinch) && e('div', { style: { fontSize: 11, color: CL[r.clinch.code][1], lineHeight: 1.3, marginTop: 1 } }, clLine(r.clinch)),
      twLine(r)),
    right,
    e('div', { style: { textAlign: 'right', minWidth: 52 } },
      e('div', { style: { fontSize: 15, fontWeight: 800, color: pctColor(r.playoff_pct) } }, `${r.playoff_pct}%`),
      e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, 'odds')));
  const seedBadge = r => e('div', { style: { minWidth: 34, textAlign: 'center' } },
    e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.5rem', lineHeight: 1, color: r.has_bye ? 'var(--accent)' : 'var(--text)' } }, r.seed),
    e('div', { style: { fontSize: 9, color: r.has_bye ? 'var(--accent)' : 'var(--text3)', fontWeight: r.has_bye ? 700 : 400 } }, r.has_bye ? 'BYE' : 'seed'));
  const cushion = r => e('div', { style: { textAlign: 'center', minWidth: 46 } },
    e('div', { style: { fontSize: 13, fontWeight: 700, color: r.cushion == null ? 'var(--text3)' : r.cushion >= 2 ? 'var(--accent)' : r.cushion >= 1 ? 'var(--accent3)' : 'var(--accent2)' } },
      r.cushion == null ? '—' : `+${r.cushion}`),
    e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, 'cushion'));
  const gb = r => e('div', { style: { textAlign: 'center', minWidth: 46 } },
    e('div', { style: { fontSize: 13, fontWeight: 700, color: r.games_back <= 1 ? 'var(--accent3)' : 'var(--accent2)' } }, r.games_back <= 0 ? 'tied' : r.games_back),
    e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, r.games_back <= 0 ? 'on PF' : 'GB'));
  const live = data.outside.filter(r => r.playoff_pct >= 10), dead = data.outside.filter(r => r.playoff_pct < 10);
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: `${sm.in}/${sm.leagues}`, label: 'In A Spot', color: 'var(--accent)' }),
      e(StatTile, { value: sm.byes ?? 0, label: 'Holding A Bye', color: 'var(--accent)' }),
      e(StatTile, { value: sm.live_out ?? 0, label: 'Out, Still Alive', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.exp_playoff_teams ?? 0, label: 'Expected Playoff Teams', color: 'var(--accent4)' })),
    (sm.clinched > 0 || sm.eliminated > 0) && e('div', { style: { fontSize: 12, color: 'var(--text2)', marginBottom: 6 } },
      sm.clinched > 0 ? e('span', { style: { color: 'var(--accent)', fontWeight: 700, marginRight: 12 } }, `✅ ${sm.clinched} clinched`) : null,
      sm.eliminated > 0 ? e('span', { style: { color: 'var(--accent2)', fontWeight: 700 } }, `❌ ${sm.eliminated} eliminated`) : null),
    sm.shaky > 0 && e('div', { style: { fontSize: 12, color: 'var(--accent3)', marginBottom: 10 } }, `⚠️ ${sm.shaky} of your playoff spots are under 60% to hold.`),
    data.inside.length > 0 && e('div', null,
      secTitle(`✅ In a playoff spot (${data.inside.length}) — by seed`, 'var(--accent)'),
      data.inside.map(r => row(r, seedBadge(r), cushion(r)))),
    live.length > 0 && e('div', { style: { marginTop: 14 } },
      secTitle(`🎯 Out — still alive (${live.length}) — best odds first`, 'var(--accent3)'),
      live.map(r => row(r, null, gb(r)))),
    dead.length > 0 && e('details', { className: 'card', style: { marginTop: 14, borderLeft: '3px solid var(--accent2)' } },
      e('summary', { style: { cursor: 'pointer', fontSize: 13, fontWeight: 700, color: 'var(--accent2)' } }, `🔨 Under 10% (${dead.length}) — sell mode`),
      dead.map(r => lineRow(r.league, `${r.league} · ${r.record}`,
        `${r.clinch?.code === 'eliminated' ? '❌ · ' : r.clinch?.code === 'elim' ? `⏳ Elim ${r.clinch.number} · ` : ''}${r.games_back > 0 ? `${r.games_back} GB · ` : ''}${r.playoff_pct}%`, 'var(--accent2)'))),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 10 } }, data.note));
}

// ── REFRESH LEAGUES VIEW ──────────────────────────────────────────────────────
function RefreshLeaguesView({ data }) {
  const [diff, setDiff] = useState(null);
  useEffect(() => {
    if (!data || !data.leagues) return;
    const k = `leagues.${(store.get('username', '') || '').toLowerCase()}.${data.season}`;
    const prev = store.get(k, null);
    const now = data.leagues;
    if (prev) {
      const before = new Set(prev.map(l => l.league_id)), after = new Set(now.map(l => l.league_id));
      setDiff({ added: now.filter(l => !before.has(l.league_id)), removed: prev.filter(l => !after.has(l.league_id)), first: false });
    } else setDiff({ added: [], removed: [], first: true });
    store.set(k, now.map(l => ({ league_id: l.league_id, name: l.name })));
    window.dispatchEvent(new CustomEvent('ff:leagues-refreshed', { detail: { keepPrefix: 'refresh-leagues|' } }));
  }, [data]);
  if (!data) return null;
  const at = new Date((data.refreshed_at || Date.now() / 1000) * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
  return e('div', null,
    e(Alert, { type: 'success', title: `✅ ${data.count} leagues loaded` },
      e('p', null, `Fresh from Sleeper at ${at}. Every feature now uses this list — saved results were cleared so they re-run with it.`)),
    diff && !diff.first && (diff.added.length || diff.removed.length
      ? e(Card, null,
          diff.added.length > 0 && e('div', { style: { marginBottom: 8 } },
            secTitle(`➕ New since last refresh (${diff.added.length})`, 'var(--accent)'),
            diff.added.map(l => lineRow(l.league_id, l.name, l.teams ? `${l.teams} teams` : '', 'var(--accent)'))),
          diff.removed.length > 0 && e('div', null,
            secTitle(`➖ Gone since last refresh (${diff.removed.length})`, 'var(--accent2)'),
            diff.removed.map(l => lineRow(l.league_id, l.name, 'left', 'var(--accent2)'))))
      : e('div', { style: { fontSize: 13, color: 'var(--text2)', marginBottom: 12 } }, 'No leagues added or removed since your last refresh.')),
    diff && diff.first && e('div', { style: { fontSize: 13, color: 'var(--text2)', marginBottom: 12 } }, 'First refresh on this device — next time you’ll see which leagues were added or removed.'),
    e('details', { className: 'card' },
      e('summary', { style: { cursor: 'pointer', fontSize: 13, fontWeight: 700 } }, `All ${data.count} leagues`),
      data.leagues.map(l => lineRow(l.league_id, l.name, [l.teams ? `${l.teams} teams` : null, l.status === 'complete' ? 'complete' : null].filter(Boolean).join(' · ')))));
}

// ── LEAGUE EXPORT VIEW ────────────────────────────────────────────────────────
function LeagueExportView({ data }) {
  const [copied, setCopied] = useState(false);
  if (!data?.export) return null;
  const x = data.export;
  const prompt = `Below is my Sleeper fantasy football league "${data.league}" as JSON (NFL week ${data.week}). I'm "${data.team}" ("me": true in standings). ` +
    `Scoring and lineup rules are in league_setup; other teams' rosters are condensed (field_notes explains fields). ` +
    `Use it to answer my questions about lineups, trades, waivers and long-term strategy. My first question: `;
  const text = prompt + '\n\n```json\n' + JSON.stringify(x) + '\n```';
  const kb = Math.round(text.length / 1024);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); }
    catch (_) { const t = document.createElement('textarea'); t.value = text; document.body.appendChild(t); t.select(); try { document.execCommand('copy'); } catch (__) {} t.remove(); }
    setCopied(true); setTimeout(() => setCopied(false), 2500);
  };
  const share = async () => { try { await navigator.share({ title: `${data.league} — league export`, text }); } catch (_) {} };
  const me = x.my_team || {}, a = me.analysis || {};
  const counts = [
    ['Standings', `${(x.standings || []).length} teams`],
    ['Your roster', `${(me.roster || []).length} players`],
    ['Other rosters', `${(x.other_teams || []).length} teams, condensed`],
    ['Draft picks', `${Object.values(x.draft_picks_owned || {}).reduce((n, v) => n + v.length, 0)} picks`],
    ['Transactions', `${(x.recent_transactions || []).length} recent`],
    ['Your analysis', [a.roster_tier, a.core_age ? `age ${a.core_age}` : null, a.playoff_odds ? `${a.playoff_odds.playoff_pct}% playoffs` : null].filter(Boolean).join(' · ') || '—'],
  ];
  return e('div', null,
    e(Card, null,
      e('div', { className: 'card-title' }, data.league),
      e('div', { className: 'card-subtitle', style: { marginBottom: 12 } }, `${data.team} · week ${data.week} · about ${kb} KB`),
      e('div', { style: { display: 'flex', gap: 8 } },
        e('button', { className: 'primary', style: { flex: 1 }, onClick: copy }, copied ? '✓ Copied' : '📋 Copy for Claude'),
        typeof navigator !== 'undefined' && navigator.share && e('button', { className: 'secondary', onClick: share }, 'Share')),
      e('div', { style: { fontSize: 12, color: 'var(--text3)', marginTop: 10, lineHeight: 1.5 } },
        'Paste into a new Claude chat and finish the sentence at the top with your question. The JSON already includes a short intro so Claude knows what it is looking at.')),
    e(Card, null,
      secTitle('What’s included'),
      counts.map(([k, v]) => lineRow(k, k, v))),
    e('details', { className: 'card' },
      e('summary', { style: { cursor: 'pointer', fontSize: 13, fontWeight: 700 } }, 'Preview JSON'),
      e('pre', { style: { fontSize: 10.5, color: 'var(--text2)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 420, overflow: 'auto', marginTop: 8 } },
        JSON.stringify(x, null, 1).slice(0, 6000) + (JSON.stringify(x, null, 1).length > 6000 ? '\n… (full version is copied)' : ''))));
}

// ── DYNASTY TAB LIST ─────────────────────────────────────────────────────
FF.tab({ id: 'dynasty', label: 'Dynasty', icon: '🏆', groups: [
  { label: 'Team strength', features: [
    { id: 'playoff-picture', title: 'Playoff Picture', sub: 'In a spot by seed, the rest by odds', icon: '🎟️', tint: 'green',
      endpoint: '/analysis/playoff-picture', view: PlayoffPictureView, badge: d => d.summary && { n: `${d.summary.in}/${d.summary.leagues}`, color: 'green' } },
    { id: 'power-rankings', title: 'Power Rankings', sub: 'All your teams, best to worst', icon: '🏆', tint: 'orange',
      endpoint: '/analysis/power-rankings', view: PowerRankingsView },
    { id: 'tier-records', title: 'Tier Records', sub: 'Roster tier vs record, with verdicts', icon: '🏁', tint: 'red',
      endpoint: '/analysis/tier-records', view: TierRecordsView, badge: d => d.summary && cnt(d.summary.flagged, 'red') },
    { id: 'overview', title: 'Overview', sub: 'Contender status and strategy', icon: '📊', tint: 'blue',
      endpoint: '/analysis/overview', view: OverviewView },
    { id: 'deep-dive', title: 'Team Deep Dive', sub: 'Everything about one league', icon: '🔬', tint: 'purple',
      endpoint: '/analysis/team-deep-dive', view: DeepDiveView, needs: 'league' },
    { id: 'league-export', title: 'Export League for Claude', sub: 'Copy one league as JSON to ask Claude about', icon: '🤖', tint: 'purple',
      endpoint: '/analysis/league-export', view: LeagueExportView, needs: 'league' },
  ]},
  { label: 'Trades', features: [
    { id: 'trade-finder', title: 'Trade Finder', sub: 'Two offers for a player, every league', icon: '🤝', tint: 'blue',
      endpoint: '/analysis/trade-finder', view: TradeFinderView, needs: 'player' },
  ]},
  { label: 'Account', features: [
    { id: 'refresh-leagues', title: 'Refresh My Leagues', sub: 'Pick up leagues you just joined or left', icon: '🔄', tint: 'blue',
      endpoint: '/refresh-leagues', view: RefreshLeaguesView, alwaysRun: true, badge: d => ({ n: d.count, color: 'blue' }) },
  ]},
]});
