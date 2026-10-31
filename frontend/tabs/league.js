/* Fantasy Manager — tabs/leagues.js
   The Leagues tab: its result screens and the list that opens them. Needs core.js loaded first. */

// ── LEAGUE SHEET VIEW ─────────────────────────────────────────────────────────
function LeagueSheetView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No leagues found.'));
  const sm = data.summary || {};
  const [sort, setSort] = useState('league');
  const [needsOnly, setNeedsOnly] = useState(false);
  let rows = data.results.filter(r => !needsOnly || r.needs.length);
  const cmp = {
    league: (a, b) => a.order - b.order,
    record: (a, b) => b.win_pct - a.win_pct || a.order - b.order,
    proj: (a, b) => b.proj - a.proj,
    needs: (a, b) => (b.needs.filter(n => n.critical).length - a.needs.filter(n => n.critical).length) || (b.needs.length - a.needs.length) || a.order - b.order,
  };
  rows = [...rows].sort(cmp[sort]);
  const btn = (id, label) => e('button', { key: id, onClick: () => setSort(id), style: { flex: 1, padding: '8px 4px', fontSize: 12, fontWeight: 700, borderRadius: 8, border: `1px solid ${sort === id ? 'var(--accent)' : 'var(--border)'}`, background: sort === id ? 'var(--surface2)' : 'transparent', color: sort === id ? 'var(--text)' : 'var(--text3)' } }, label);
  const recColor = p => p > 0.5 ? 'var(--accent)' : p < 0.5 ? 'var(--accent2)' : 'var(--text2)';
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.leagues ?? 0, label: 'Leagues', color: 'var(--text2)' }),
      e(StatTile, { value: `${sm.proj_wins ?? 0}-${sm.proj_losses ?? 0}`, label: `Wk ${data.week} Projected`, color: 'var(--accent4)' }),
      e(StatTile, { value: sm.with_needs ?? 0, label: 'With Needs', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.critical ?? 0, label: "Can't Fill", color: 'var(--accent2)' })),
    e('div', { style: { display: 'flex', gap: 6, marginBottom: 8 } }, btn('league', 'League'), btn('record', 'Record'), btn('proj', 'Proj'), btn('needs', 'Needs')),
    e('label', { style: { display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text2)', marginBottom: 12 } },
      e('input', { type: 'checkbox', checked: needsOnly, onChange: ev => setNeedsOnly(ev.target.checked) }), 'Only leagues with needs'),
    rows.map(r => e('div', { key: r.league, style: { padding: '10px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${r.needs.some(n => n.critical) ? 'var(--accent2)' : r.needs.length ? 'var(--accent3)' : 'var(--accent)'}`, borderRadius: 8, marginBottom: 6 } },
      e('div', { style: { display: 'flex', alignItems: 'baseline', gap: 10 } },
        e('div', { style: { flex: 1, minWidth: 0 } },
          e('div', { style: { fontSize: 14, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.league),
          e('div', { style: { fontSize: 11, color: 'var(--text3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.team)),
        e('div', { style: { textAlign: 'right', minWidth: 46 } },
          e('div', { style: { fontSize: 14, fontWeight: 800, color: recColor(r.win_pct) } }, r.record),
          e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, 'record')),
        e('div', { style: { textAlign: 'right', minWidth: 62 } },
          e('div', { style: { fontSize: 14, fontWeight: 800, color: r.proj_win == null ? 'var(--text)' : r.proj_win ? 'var(--accent)' : 'var(--accent2)' } }, r.proj.toFixed(1)),
          e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, r.opp_proj != null ? `vs ${r.opp_proj.toFixed(1)}` : 'proj'))),
      e('div', { style: { fontSize: 12, color: 'var(--text2)', margin: '6px 0 4px', fontFamily: 'ui-monospace, Menlo, monospace', wordBreak: 'break-word' } }, r.lineup),
      r.needs.length
        ? e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 5 } }, r.needs.map(n => e('span', { key: n.position, style: { fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 5, border: `1px solid ${n.critical ? 'var(--accent2)' : 'var(--accent3)'}`, color: n.critical ? 'var(--accent2)' : 'var(--accent3)' } }, `${n.position} ${n.have}/${n.need}`)))
        : e('div', { style: { fontSize: 11, color: 'var(--accent)' } }, '✓ No needs')
    )),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

// ── SEASON RECORDS VIEW ───────────────────────────────────────────────────────
function SeasonRecordsView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No leagues found.'));
  const sm = data.summary || {};
  const [sortKey, setSortKey] = useState('league');
  const [desc, setDesc] = useState(false);
  const cols = [
    ['league', 'League', 'left'], ['record', 'Rec', 'right'], ['pf', 'PF', 'right'], ['pa', 'PA', 'right'], ['max_pf', 'Max PF', 'right'], ['efficiency', 'Eff%', 'right'],
  ];
  const rows = [...data.results];
  if (sortKey !== 'league') {
    const k = sortKey === 'record' ? 'win_pct' : sortKey;
    rows.sort((a, b) => ((b[k] ?? -1) - (a[k] ?? -1)) * (desc ? -1 : 1) || a.league.localeCompare(b.league));
  } else if (desc) rows.reverse();
  const click = k => { if (sortKey === k) setDesc(!desc); else { setSortKey(k); setDesc(false); } };
  const effColor = v => v == null ? 'var(--text3)' : v >= 90 ? 'var(--accent)' : v >= 80 ? 'var(--accent3)' : 'var(--accent2)';
  const recColor = p => p > 0.5 ? 'var(--accent)' : p < 0.5 ? 'var(--accent2)' : 'var(--text2)';
  const th = ([k, label, align]) => e('th', { key: k, onClick: () => click(k), style: { textAlign: align, fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: sortKey === k ? 'var(--accent)' : 'var(--text3)', padding: '6px 4px', cursor: 'pointer', whiteSpace: 'nowrap', borderBottom: '1px solid var(--border)' } }, label, sortKey === k ? (desc ? ' ▼' : ' ▲') : '');
  const td = (c, align, extra) => e('td', { style: { textAlign: align, padding: '6px 4px', fontSize: 11, borderBottom: '1px solid var(--border)', whiteSpace: 'nowrap', ...extra } }, c);
  return e('div', null,
    e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: 'var(--text2)', marginBottom: 8 } }, `${data.season} SEASON RECORDS · THROUGH WEEK ${Math.max((data.week || 1) - 1, 0)}`),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.record, label: `Overall (${sm.leagues})`, color: recColor(sm.win_pct) }),
      e(StatTile, { value: sm.pf?.toLocaleString(), label: 'Points For', color: 'var(--accent)' }),
      e(StatTile, { value: sm.pa?.toLocaleString(), label: 'Points Against', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.avg_efficiency != null ? `${sm.avg_efficiency}%` : '—', label: 'Avg Efficiency', color: effColor(sm.avg_efficiency) })
    ),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 10 } }, 'Tap a column header to sort. Eff% = PF ÷ Max PF (points a perfect lineup would have scored).',
      sm.worst_eff ? e('span', null, ` Lowest efficiency: `, e('b', null, sm.worst_eff), '.') : null),
    e('div', { style: { overflowX: 'auto', WebkitOverflowScrolling: 'touch' } },
      e('table', { style: { width: '100%', borderCollapse: 'collapse' } },
        e('thead', null, e('tr', null, cols.map(th))),
        e('tbody', null, rows.map(r => e('tr', { key: r.league },
          td(e('div', null, e('div', { style: { fontWeight: 700, maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' } }, r.league), e('div', { style: { fontSize: 10, color: 'var(--text3)', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis' } }, `${r.team}${r.rank ? ` · #${r.rank}/${r.total_teams}` : ''}`)), 'left', { whiteSpace: 'normal' }),
          td(r.record, 'right', { fontWeight: 700, color: recColor(r.win_pct) }),
          td(r.pf.toFixed(1), 'right'),
          td(r.pa.toFixed(1), 'right'),
          td(r.max_pf.toFixed(1), 'right', { color: 'var(--text2)' }),
          td(r.efficiency != null ? `${r.efficiency}%` : '—', 'right', { fontWeight: 700, color: effColor(r.efficiency) })
        )))
      )
    ),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── PLAYOFF ODDS VIEW ─────────────────────────────────────────────────────────
function PlayoffOddsView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No leagues still in the regular season.'));
  const sm = data.summary || {};
  const needsCard = r => (r.playoff_pct >= 10 && r.playoff_pct < 85) || (r.next_game && r.next_game.swing >= 20);
  const focus = data.results.filter(needsCard);
  const safe = data.results.filter(r => !needsCard(r) && r.playoff_pct >= 85);
  const out = data.results.filter(r => !needsCard(r) && r.playoff_pct < 85);
  const oneLiner = (r, extra) => e('div', { key: r.league, style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11, padding: '4px 0', borderBottom: '1px solid var(--border)' } },
    e('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 } }, r.league, r.team ? e('span', { style: { color: 'var(--text3)', fontSize: 10 } }, ` · ${r.team}`) : null),
    e('span', { style: { whiteSpace: 'nowrap', color: 'var(--text3)' } }, `${r.record} · #${r.rank} · `, e('span', { style: { color: r.color, fontWeight: 700 } }, `${r.playoff_pct}%`), extra ? ` · ${extra}` : '')
  );
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.leagues ?? 0, label: 'Leagues', color: 'var(--text2)' }),
      e(StatTile, { value: sm.clinched_or_safe ?? 0, label: 'Safe (≥85%)', color: 'var(--accent)' }),
      e(StatTile, { value: sm.bubble ?? 0, label: 'Bubble', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.out ?? 0, label: 'Out (<10%)', color: 'var(--accent2)' })
    ),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 12 } },
      `${focus.length} league${focus.length === 1 ? '' : 's'} where this week's decisions move the needle (bubble or must-win). Safe and eliminated leagues are listed at the bottom.`),
    focus.map(r => {
      const hist = Object.entries(r.wins_hist || {});
      const maxH = Math.max(...hist.map(([, v]) => v), 1);
      return e(Card, { key: r.league, borderColor: r.color },
        e('div', { className: 'card-header' },
          e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', color: r.color } }, `${r.playoff_pct}%`),
            e('div', { style: { fontSize: 10, color: r.color, fontWeight: 700 } }, r.status)
          )
        ),
        e('div', { style: { fontSize: 11, color: 'var(--text2)', marginBottom: 8 } },
          `${r.record} · #${r.rank}/${r.total_teams} · ${r.playoff_spots} spots · ${r.games_left} left · exp. ${r.exp_wins} W · scoring ${r.my_mu} ± ${r.my_sd} (lg ${r.league_mu})${r.bye_pct > 0 ? ` · bye ${r.bye_pct}%` : ''}`),
        r.next_game && e('div', { style: { padding: '8px 10px', background: r.next_game.swing >= 20 ? 'rgba(255,179,71,0.08)' : 'var(--surface2, var(--surface))', border: `1px solid ${r.next_game.swing >= 20 ? 'rgba(255,179,71,0.4)' : 'var(--border)'}`, borderRadius: 8, marginBottom: 8, fontSize: 11 } },
          e('div', { style: { fontWeight: 700 } }, `${r.next_game.swing >= 20 ? '🔥 Must-win: ' : 'Next: '}Wk ${r.next_game.week} vs ${r.next_game.opp_name} (${r.next_game.win_prob}% to win)`),
          e('div', { style: { color: 'var(--text2)', marginTop: 2 } }, `Playoffs ${r.next_game.playoff_if_win}% with a win · ${r.next_game.playoff_if_loss}% with a loss`)
        ),
        e('div', { style: { fontSize: 11, color: 'var(--text2)', padding: '6px 10px', borderLeft: `2px solid ${r.color}`, marginBottom: 8 } }, r.advice),
        e('details', null,
          e('summary', { style: { fontSize: 10, color: 'var(--text3)', cursor: 'pointer' } }, 'Wins distribution & league table'),
          e('div', { style: { display: 'flex', alignItems: 'flex-end', gap: 3, height: 44, margin: '8px 0' } },
            hist.map(([w, pct]) => e('div', { key: w, style: { flex: 1, textAlign: 'center' } },
              e('div', { style: { height: `${Math.max(2, (pct / maxH) * 32)}px`, background: r.color, opacity: 0.8, borderRadius: 2 } }),
              e('div', { style: { fontSize: 9, color: 'var(--text3)', marginTop: 2 } }, w)
            ))
          ),
          r.league_table?.map((t, i) => e('div', { key: i, style: { display: 'flex', justifyContent: 'space-between', fontSize: 11, padding: '3px 0', borderBottom: '1px solid var(--border)', color: t.team === r.team ? 'var(--accent)' : 'var(--text2)' } },
            e('span', null, `${i + 1}. ${t.team}`), e('span', null, `${t.wins} W · ${t.playoff_pct}%`)
          ))
        )
      );
    }),
    safe.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 6 } }, `✅ Safe / clinched (${safe.length}) — bank FAAB`),
      safe.map(r => oneLiner(r, r.bye_pct > 0 ? `bye ${r.bye_pct}%` : null))
    ),
    out.length > 0 && e(Card, { borderColor: 'var(--accent2)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent2)', marginBottom: 6 } }, `🔨 Out of it (${out.length}) — sell mode`),
      out.map(r => oneLiner(r, r.status))
    ),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── SEASON FORECAST VIEW ──────────────────────────────────────────────────────
function SeasonForecastView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No data found.'));
  return e('div', null,
    e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: 'var(--text2)', marginBottom: 12 } }, 'PROJECTED FINAL RECORDS'),
    data.results.map(r => {
      const projWinPct = r.proj_wins / Math.max(r.proj_wins + r.proj_losses, 1);
      const barColor = projWinPct >= 0.6 ? 'var(--accent)' : projWinPct >= 0.45 ? 'var(--accent3)' : 'var(--accent2)';
      return e('div', { key: r.league, style: { marginBottom: 12, padding: '12px 14px', background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${barColor}`, borderRadius: 10 } },
        e('div', { style: { display: 'flex', justifyContent: 'space-between', marginBottom: 6 } },
          e('div', null,
            e('div', { style: { fontWeight: 700, fontSize: 14 } }, r.league),
            e('div', { style: { fontSize: 11, color: 'var(--text2)', marginTop: 2 } }, `${r.team ? r.team + ' · ' : ''}Current: ${r.current_record}`)
          ),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.4rem', color: barColor } }, r.projected_record),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, 'projected final')
          )
        ),
        e('div', { className: 'bar-track', style: { height: 8 } },
          e('div', { className: 'bar-fill', style: { width: `${projWinPct * 100}%`, background: barColor } })
        ),
        e('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--text3)', marginTop: 4 } },
          e('span', null, `${r.weeks_remaining} weeks remaining`),
          e('span', null, `${r.my_proj_score} proj pts/wk`)
        )
      );
    })
  );
}

// ── TRADE DEADLINES VIEW ──────────────────────────────────────────────────────
function TradeDeadlinesView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const fmtDate = d => { if (!d) return null; const x = new Date(d + 'T12:00:00'); return x.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' }); };
  const daysTo = d => { if (!d) return null; const t = new Date(d + 'T23:59:00'), n = new Date(); return Math.ceil((t - n) / 86400000); };
  const recColor = p => p == null ? 'var(--text2)' : p > 0.5 ? 'var(--accent)' : p < 0.5 ? 'var(--accent2)' : 'var(--text2)';
  const urgency = g => g.weeks_left === 0 ? 'var(--accent2)' : g.weeks_left === 1 ? 'var(--accent3)' : 'var(--accent4)';
  const WIN = { Closing: 'var(--accent2)', 'Win now': 'var(--accent3)', Open: 'var(--accent4)', Rising: 'var(--accent)' };
  const leagueRow = r => e('div', { key: r.league_id, style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0', borderBottom: '1px solid var(--border)' } },
    e('div', { style: { flex: 1, minWidth: 0 } },
      e('div', { style: { fontSize: 14, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.league),
      e('div', { style: { fontSize: 11, color: 'var(--text3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } },
        `${r.team} · #${r.rank}/${r.teams}${r.in_playoff_spot ? ' · playoff spot' : ''}`)),
    e('div', { style: { textAlign: 'center', minWidth: 44 } },
      e('div', { style: { fontSize: 14, fontWeight: 800, color: recColor(r.win_pct) } }, r.record),
      e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, 'record')),
    e('div', { style: { textAlign: 'right', minWidth: 52 } },
      e('div', { style: { fontSize: 14, fontWeight: 800 } }, r.core_age != null ? r.core_age : '—'),
      e('div', { style: { fontSize: 9, fontWeight: 700, color: WIN[r.window] || 'var(--text3)' } }, r.window ? `age · ${r.window}` : 'age')));
  const nxt = sm.next;
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.this_week ?? 0, label: 'Close This Week', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.open ?? 0, label: 'Still Open', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.no_deadline ?? 0, label: 'No Deadline', color: 'var(--accent)' }),
      e(StatTile, { value: sm.passed ?? 0, label: 'Passed', color: 'var(--text3)' })),
    nxt && e('div', { style: { fontSize: 13, color: 'var(--text2)', marginBottom: 12 } },
      'Next: ', e('b', null, `${nxt.leagues.length} league${nxt.leagues.length === 1 ? '' : 's'} at week ${nxt.deadline_week}`),
      nxt.closes_after ? ` — closes after ${fmtDate(nxt.closes_after)}${daysTo(nxt.closes_after) != null && daysTo(nxt.closes_after) >= 0 ? ` (${daysTo(nxt.closes_after) === 0 ? 'today' : `in ${daysTo(nxt.closes_after)} day${daysTo(nxt.closes_after) === 1 ? '' : 's'}`})` : ''}` : ''),
    (data.groups || []).map(g => e(Card, { key: g.deadline_week, borderColor: urgency(g) },
      e('div', { className: 'card-header', style: { marginBottom: 4 } },
        e('div', null,
          e('div', { className: 'card-title' }, `Week ${g.deadline_week} deadline`),
          e('div', { className: 'card-subtitle' }, g.closes_after ? `Closes after the last week-${g.deadline_week} game · ${fmtDate(g.closes_after)}` : `Closes after the last week-${g.deadline_week} game`)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontSize: 13, fontWeight: 800, color: urgency(g), whiteSpace: 'nowrap' } },
            g.weeks_left === 0 ? 'THIS WEEK' : `${g.weeks_left} wk${g.weeks_left === 1 ? '' : 's'}`),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${g.leagues.length} league${g.leagues.length === 1 ? '' : 's'}`))),
      g.leagues.map(leagueRow))),
    !(data.groups || []).length && e(Alert, { type: 'info' }, e('p', null, 'No upcoming trade deadlines.')),
    data.no_deadline?.length > 0 && e('details', { className: 'card', style: { borderLeft: '3px solid var(--accent)' } },
      e('summary', { style: { cursor: 'pointer', fontSize: 13, fontWeight: 700, color: 'var(--accent)' } }, `♾️ No trade deadline (${data.no_deadline.length})`),
      data.no_deadline.map(leagueRow)),
    data.passed?.length > 0 && e('details', { className: 'card', style: { borderLeft: '3px solid var(--text3)' } },
      e('summary', { style: { cursor: 'pointer', fontSize: 13, fontWeight: 700, color: 'var(--text3)' } }, `🔒 Deadline passed (${data.passed.length})`),
      data.passed.map(r => e('div', { key: r.league_id, style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 12, padding: '6px 0', borderBottom: '1px solid var(--border)', color: 'var(--text2)' } },
        e('span', { style: { flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.league),
        e('span', { style: { whiteSpace: 'nowrap' } }, `week ${r.deadline_week} · ${r.record}${r.core_age != null ? ` · age ${r.core_age}` : ''}`)))),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note));
}

// ── LEAGUES TAB LIST ─────────────────────────────────────────────────────
FF.tab({ id: 'leagues', label: 'Leagues', icon: '📋', groups: [
  { label: 'Your leagues', features: [
    { id: 'league-sheet', title: 'League Sheet', sub: 'Lineup format, record, projection, needs', icon: '📋', tint: 'blue',
      endpoint: '/analysis/league-sheet', view: LeagueSheetView, badge: d => d.summary && cnt(d.summary.critical, 'red') },
    { id: 'trade-deadlines', title: 'Trade Deadlines', sub: 'Every league’s deadline, soonest first', icon: '⏰', tint: 'red',
      endpoint: '/analysis/trade-deadlines', view: TradeDeadlinesView, badge: d => d.summary && cnt(d.summary.this_week, 'red') },
    { id: 'season-records', title: 'Season Records', sub: 'Record, PF, PA and max PF', icon: '📒', tint: 'green',
      endpoint: '/analysis/season-records', view: SeasonRecordsView },
  ]},
  { label: 'Predictions', features: [
    { id: 'playoff-odds', title: 'Playoff Odds', sub: 'Simulated odds and must-win games', icon: '🎰', tint: 'orange',
      endpoint: '/analysis/playoff-odds', view: PlayoffOddsView, badge: d => d.summary && cnt(d.summary.bubble, 'orange') },
    { id: 'season-forecast', title: 'Season Forecast', sub: 'Projected final records', icon: '📈', tint: 'purple',
      endpoint: '/analysis/season-forecast', view: SeasonForecastView },
  ]},
]});
