/* Fantasy Manager — tabs/lineups.js
   The Lineups tab: its result screens and the list that opens them. Needs core.js loaded first. */

function OptimalLineupView({ data }) {
  if (!data) return null;
  const total = (data.results?.length || 0) + (data.optimal_leagues?.length || 0);
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: total, label: 'Leagues', color: 'var(--text2)' }),
      e(StatTile, { value: data.optimal_leagues?.length || 0, label: 'Already Optimal', color: 'var(--accent)' }),
      e(StatTile, { value: data.summary?.need_lineup_changes ?? (data.results?.length || 0), label: 'Lineup Changes', color: 'var(--accent3)' }),
      e(StatTile, { value: data.summary?.have_fa_upgrades ?? 0, label: 'FA Upgrades', color: 'var(--accent4)' })
    ),
    data.results?.map(r => e(Card, { key: r.league, borderColor: r.lineup_only ? 'var(--accent4)' : undefined },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', color: 'var(--accent)' } }, r.optimal_pts?.toFixed(1)),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, 'optimal pts'),
          !r.lineup_only && e('div', { style: { fontSize: 11, color: 'var(--accent3)' } }, `+${r.gain?.toFixed(1)} vs current`),
          r.fa_gain > 0 && e('div', { style: { fontSize: 11, color: 'var(--accent4)' } }, `+${r.fa_gain} more via FAs`),
          r.locked_count > 0 && e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `🔒 ${r.locked_count} locked (played)`)
        )
      ),
      r.lineup_only && e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 8 } }, 'Roster lineup is already optimal — free agents below would improve it.'),
      e(MovesList, { moves: r.moves, ptsKey: 'pts' }),
      r.fa_upgrades?.length > 0 && e('div', { style: { marginBottom: 12 } },
        e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent4)', marginBottom: 6 } }, r.taxi_upgrades > 0 ? '🚕 Taxi / 🆓 Free Agent Upgrades' : '🆓 Free Agent Upgrades'),
        r.fa_upgrades.map((u, i) => e('div', { key: i, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: 'rgba(92,158,255,0.06)', border: '1px solid rgba(92,158,255,0.3)', borderRadius: 8, marginBottom: 4 } },
          e('span', { style: { fontSize: 10, fontWeight: 800, color: u.fa.source === 'taxi' ? 'var(--accent3)' : 'var(--accent4)', minWidth: 54 } }, `${u.fa.source === 'taxi' ? '🚕' : '+'} ${u.slot}`),
          e(PosBadge, { pos: u.fa.position }),
          e('div', { style: { flex: 1, minWidth: 0 } },
            e('div', { style: { fontSize: 12, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, `${u.fa.name} (${u.fa.team})`, u.fa.injury_status ? e('span', { style: { fontSize: 9, color: 'var(--accent3)' } }, ` ${u.fa.injury_status}`) : null),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${u.fa.source === 'taxi' ? 'promote from taxi · ' : 'free agent · '}${u.current ? `over ${u.current.name} (${u.current.pts})` : 'fills empty slot'}`)),
          e('span', { style: { fontSize: 12, fontWeight: 700, color: 'var(--accent4)' } }, `${u.fa.pts} (+${u.gain})`)
        ))
      ),
      e('details', null,
      e('summary', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6, cursor: 'pointer' } }, 'Full optimal lineup'),
      r.lineup?.map((os, i) => {
        const p = os.player;
        if (!p) return e('div', { key: i, className: 'player-row', style: { opacity: 0.5 } }, e('span', { style: { fontSize: 10, color: 'var(--text3)', minWidth: 52 } }, os.slot), e('span', { style: { fontSize: 11, color: 'var(--accent2)' } }, 'Empty'));
        const ptColor = p.pts >= 20 ? 'var(--accent)' : p.pts >= 10 ? 'var(--text2)' : 'var(--accent2)';
        return e('div', { key: i, className: 'player-row', style: { opacity: os.locked ? 0.6 : 1, border: `1px solid ${!p.is_starter ? 'rgba(255,179,71,0.4)' : 'var(--border)'}` } },
          e('span', { style: { fontSize: 9, color: 'var(--text3)', minWidth: 52, textAlign: 'center' } }, os.locked ? `🔒 ${os.slot}` : os.slot),
          e(PosBadge, { pos: p.position }),
          e('span', { className: 'player-name' }, p.name),
          e('span', { className: 'player-team' }, p.team),
          !p.is_starter && e('span', { style: { fontSize: 9, color: 'var(--accent3)', fontWeight: 700 } }, '▲'),
          e('span', { style: { fontSize: 9, color: 'var(--text3)', textAlign: 'right', lineHeight: 1.3, whiteSpace: 'nowrap' } },
            e('div', null, os.locked ? 'actual' : `proj ${p.proj ?? p.pts}`),
            e('div', null, p.gp > 0 ? `avg ${p.avg}${p.std != null ? ` ±${p.std}` : ''} · ${p.gp} GP` : '0 GP')
          ),
          e('span', { className: 'player-pts', style: { color: ptColor } }, p.pts)
        );
      }))
    )),
    data.results?.length > 0 && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginBottom: 10 } },
      data.weeks_completed > 0
        ? `Lineup ranked on week projections (actual points once a player has played). Season average ± std dev per game played (${data.weeks_completed} week${data.weeks_completed === 1 ? '' : 's'} of stats) shown for reference.`
        : 'Lineup ranked on week projections. No completed weeks yet, so no season averages.'),
    data.optimal_leagues?.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 8 } }, `✅ Already Optimal (${data.optimal_leagues.length})`),
      data.optimal_leagues.map(l => e('div', { key: l.league, style: { display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 12 } },
        e('span', null, l.league, l.team ? e('span', { style: { color: 'var(--text3)', fontSize: 10 } }, ` · ${l.team}`) : null),
        e('span', { style: { fontWeight: 700, color: 'var(--accent)' } }, `${l.pts} pts`)
      ))
    )
  );
}

// ── UPGRADE RECS VIEW ─────────────────────────────────────────────────────────
function UpgradeRecsView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No data found.'));
  const hasUpgrades = data.results.filter(r => r.moves?.length > 0);
  const optimal = data.results.filter(r => !r.moves?.length);

  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: hasUpgrades.length, label: 'Need Changes', color: 'var(--accent3)' }),
      e(StatTile, { value: optimal.length, label: 'Optimal', color: 'var(--accent)' })
    ),
    hasUpgrades.map(r => e(Card, { key: r.league, borderColor: 'var(--accent3)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.8rem', color: 'var(--accent3)', lineHeight: 1 } }, `+${r.gain?.toFixed(1)}`),
          e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, 'floor pts gained')
        )
      ),
      e(MovesList, { moves: r.moves, ptsKey: 'week_pts', subKey: 'ytd_avg', title: `🔄 ${r.moves.length} move${r.moves.length === 1 ? '' : 's'}` }),
    )),
    hasUpgrades.length > 0 && e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 10, lineHeight: 1.4 } },
      data.weeks_completed > 0
        ? 'Adj = floor × matchup. Floor is the lower of this week\'s projection and season average per game (projection only with 0 games). Matchup = points this week\'s opponent allows to that position vs the average defense: 🟢 8 easiest, 🔴 8 hardest.'
        : 'No completed weeks yet — recommendations use week projections only.'),
    optimal.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, color: 'var(--accent)', marginBottom: 8, fontWeight: 700 } }, `✅ Already Optimal (${optimal.length})`),
      optimal.map(l => e('div', { key: l.league, style: { display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 12 } },
        e('span', null, l.league),
        e('span', { style: { color: 'var(--accent)', fontWeight: 700 } }, `${l.optimal_pts?.toFixed(1)} pts`)
      ))
    )
  );
}

// ── STARTER UPGRADES VIEW ─────────────────────────────────────────────────────
function StarterUpgradesView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No data found.'));
  const needsWork = data.results.filter(r => r.upgrades?.length > 0);
  const optimal = data.results.filter(r => r.optimal);

  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: needsWork.length, label: 'Need Changes', color: 'var(--accent3)' }),
      e(StatTile, { value: optimal.length, label: 'Optimal', color: 'var(--accent)' })
    ),
    needsWork.map(r => e(Card, { key: r.league, borderColor: 'var(--accent3)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' } },
          e(Tag, { color: 'orange' }, `${r.upgrades.length} slot${r.upgrades.length > 1 ? 's' : ''} to upgrade`),
          r.upgrades.some(u => u.zero_projection) && e(Tag, { color: 'red' }, `0️⃣ ${r.upgrades.filter(u => u.zero_projection).length} zero-pt`),
          r.locked_count > 0 && e(Tag, { color: 'gray' }, `🔒 ${r.locked_count} played`)
        )
      ),
      e(MovesList, { moves: r.moves, ptsKey: 'pts', title: '🔄 Roster Moves (no pickups needed)' }),
      r.upgrades.some(u => u.fa_upgrades?.length || u.zero_projection) && e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent4)', marginBottom: 6 } }, '🏷 Slot-By-Slot · Free Agent Options'),
      r.upgrades.map((u, i) => e('div', { key: i, style: { marginBottom: 14 } },
        e('div', { style: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6, flexWrap: 'wrap' } },
          e('span', null, `${u.slot} · Currently: ${u.current_starter ? `${u.current_starter.name} (${u.current_starter.pts} pts)` : 'EMPTY'}`),
          u.zero_projection && e(Tag, { color: 'red' }, '0 PTS PROJECTED')
        ),
        u.bench_upgrades.map(p => e('div', { key: p.id, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: 'rgba(0,229,160,0.06)', border: '1px solid rgba(0,229,160,0.3)', borderRadius: 8, marginBottom: 4 } },
          e(PosBadge, { pos: p.position }),
          e('div', { style: { flex: 1 } },
            e('div', { style: { fontSize: 12, fontWeight: 700 } }, p.name),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${p.team} · Already on your roster`)
          ),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontSize: 13, fontWeight: 700, color: 'var(--accent)' } }, p.pts),
            e('div', { style: { fontSize: 10, color: 'var(--accent)' } }, `+${(p.pts - (u.current_starter?.pts || 0)).toFixed(1)}`)
          )
        )),
        u.fa_upgrades.map(p => e('div', { key: p.id, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '8px 10px', background: 'rgba(92,158,255,0.06)', border: '1px solid rgba(92,158,255,0.3)', borderRadius: 8, marginBottom: 4 } },
          e(PosBadge, { pos: p.position }),
          e('div', { style: { flex: 1 } },
            e('div', { style: { fontSize: 12, fontWeight: 700 } }, p.name),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${p.team} · Free Agent`)
          ),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontSize: 13, fontWeight: 700, color: 'var(--accent4)' } }, p.pts),
            e('div', { style: { fontSize: 10, color: 'var(--accent4)' } }, `+${(p.pts - (u.current_starter?.pts || 0)).toFixed(1)}`)
          )
        ))
      ))
    )),
    optimal.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, color: 'var(--accent)', marginBottom: 8, fontWeight: 700 } }, `✅ Optimal Lineups (${optimal.length})`),
      optimal.map(l => e('div', { key: l.league, style: { fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' } }, l.league))
    )
  );
}

// ── BENCH VS FA VIEW ──────────────────────────────────────────────────────────
function BenchVsFaView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No data found.'));
  const hasWork = data.results.filter(r => r.drops?.length || r.ir_moves?.length);
  const fine = data.results.filter(r => r.optimal);
  const sm = data.summary || {};
  const STATUS = { bye: ['BYE', 'orange'], injured: ['OUT', 'red'] };
  const side = (label, color, p, line) => e('div', null,
    e('div', { style: { fontSize: 10, color, fontWeight: 800, marginBottom: 4 } }, label),
    e('div', { style: { display: 'flex', alignItems: 'center', gap: 6 } },
      e(PosBadge, { pos: p.position }),
      e('div', { style: { minWidth: 0 } },
        e('div', { style: { fontSize: 14, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name),
        e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, line))));
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.with_drops ?? hasWork.length, label: 'Leagues w/ Drops', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.drops ?? 0, label: 'Drops', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.ir_moves ?? 0, label: 'Move To IR', color: 'var(--accent4)' }),
      e(StatTile, { value: fine.length, label: 'Roster Fine', color: 'var(--accent)' })),
    hasWork.map(r => e(Card, { key: r.league, borderColor: r.drops.length ? 'var(--accent2)' : 'var(--accent4)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { display: 'flex', gap: 4, flexWrap: 'wrap', justifyContent: 'flex-end' } },
          r.drops.length > 0 && e(Tag, { color: 'red' }, `${r.drops.length} drop${r.drops.length > 1 ? 's' : ''}`),
          r.ir_moves.length > 0 && e(Tag, { color: 'blue' }, `${r.ir_moves.length} to IR`))),
      r.drops.map((d, i) => e('div', { key: i, className: 'swap-card', style: { marginBottom: 6 } },
        side('✂ DROP', 'var(--accent2)', d.drop,
          d.drop.status === 'active' ? `${d.drop.team} · ${d.drop.pts} pts` : `${d.drop.team} · ${STATUS[d.drop.status][0]} · avg ${d.drop.avg}`),
        e('div', { style: { textAlign: 'center' } },
          e('div', { style: { fontSize: 13, fontWeight: 800, color: 'var(--accent)' } }, `+${d.gain}`),
          e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, d.drop.basis === 'season avg' ? 'vs avg' : 'gain')),
        side('➕ ADD', 'var(--accent)', d.add, `${d.add.team} · ${d.add.pts} pts`))),
      r.ir_moves.length > 0 && e('div', { style: { marginTop: 6 } },
        e('div', { style: { fontSize: 11, fontWeight: 800, color: 'var(--accent4)', marginBottom: 4 } },
          `🏥 Move to IR instead of dropping${r.ir_open ? ` · ${r.ir_open} IR slot${r.ir_open > 1 ? 's' : ''} open` : ' · IR is full'}`),
        r.ir_moves.map(p => e('div', { key: p.id, className: 'player-row' },
          e(PosBadge, { pos: p.position }),
          e('span', { className: 'player-name' }, p.name),
          e('span', { className: 'player-team' }, p.team),
          e(Tag, { color: 'red' }, (p.injury_status || '').toUpperCase()),
          e('span', { className: 'player-pts' }, `avg ${p.avg}`))))
    )),
    fine.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, color: 'var(--accent)', marginBottom: 8, fontWeight: 700 } }, `✅ Roster Fine (${fine.length})`),
      fine.map(l => e('div', { key: l.league, style: { fontSize: 13, padding: '5px 0', borderBottom: '1px solid var(--border)' } }, l.league))),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── WAIVER WATCH VIEW ─────────────────────────────────────────────────────────
function WaiverWatchView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const TREND = { rising: ['📈 Rising', 'var(--accent)'], fading: ['📉 Fading', 'var(--accent2)'], steady: ['➡ Steady', 'var(--text3)'] };
  const candRow = (c, i, showLeague) => e('div', { key: c.id + i, style: { padding: '8px 10px', background: 'var(--surface2, var(--surface))', border: '1px solid var(--border)', borderRadius: 8, marginBottom: 6 } },
    e('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
      e(PosBadge, { pos: c.position }),
      e('div', { style: { flex: 1, minWidth: 0 } },
        e('div', { style: { fontSize: 12, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, c.name,
          c.under_radar && e('span', { style: { marginLeft: 6, fontSize: 9, color: 'var(--accent4)', fontWeight: 700 } }, 'UNDER RADAR')),
        e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${c.team}${showLeague ? ` · ${c.league}` : ''} · proj ${c.proj} · avg ${c.avg}${c.std != null ? ` ±${c.std}` : ''} · last 2: ${c.recent} · ${c.gp} GP`)
      ),
      e('div', { style: { textAlign: 'right' } },
        e('div', { style: { fontSize: 14, fontWeight: 800, color: 'var(--accent)' } }, `+${c.gain}`),
        e('div', { style: { fontSize: 9, color: TREND[c.trend]?.[1] || 'var(--text3)' } }, TREND[c.trend]?.[0] || c.trend)
      )
    ),
    e('div', { style: { fontSize: 10, color: 'var(--text2)', marginTop: 4 } },
      `Replaces ${c.replaces?.name || 'empty slot'} at ${c.replaces?.slot} (floor ${c.replaces?.floor})`,
      c.drop_candidate ? ` · Drop ${c.drop_candidate.name} (${c.drop_candidate.position}, avg ${c.drop_candidate.avg}, ${c.drop_candidate.gp} GP)` : '',
      c.trending_adds > 0 ? ` · 🔥 ${c.trending_adds} adds/24h` : ''
    )
  );
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.leagues ?? 0, label: 'Leagues', color: 'var(--text2)' }),
      e(StatTile, { value: sm.leagues_with_pickups ?? 0, label: 'With Pickups', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.total_candidates ?? 0, label: 'Candidates', color: 'var(--accent)' }),
      e(StatTile, { value: sm.under_radar ?? 0, label: 'Under Radar', color: 'var(--accent4)' })
    ),
    sm.top?.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 8 } }, '🏆 Best Pickups Across All Leagues'),
      sm.top.map((c, i) => candRow(c, i, true))
    ),
    data.results?.filter(r => r.candidates?.length).map(r => e(Card, { key: r.league, borderColor: 'var(--accent3)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e('div', { style: { textAlign: 'right' } },
          e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.4rem', color: 'var(--accent)' } }, `+${r.best_gain}`),
          e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${r.total_candidates} candidate${r.total_candidates === 1 ? '' : 's'}`)
        )
      ),
      r.candidates.map((c, i) => candRow(c, i, false))
    )),
    (() => { const none = data.results?.filter(r => !r.candidates?.length) || []; return none.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, color: 'var(--accent)', fontWeight: 700, marginBottom: 6 } }, `✅ Nothing worth grabbing (${none.length})`),
      none.map(r => e('div', { key: r.league, style: { fontSize: 12, padding: '4px 0', borderBottom: '1px solid var(--border)' } }, r.league, r.team ? e('span', { style: { color: 'var(--text3)', fontSize: 10 } }, ` · ${r.team}`) : null))
    ); })(),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── RESULTS VIEWS ─────────────────────────────────────────────────────────────

function AlertsView({ data, type }) {
  if (!data || !data.results?.length) return e(Alert, { type: 'success', title: '✅ All Clear' }, e('p', null, 'No issues found across your leagues.'));
  return e('div', null,
    data.results.map(r => e(Card, { key: r.league, borderColor: 'var(--accent2)' },
      e('div', { className: 'card-header' },
        e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
        e(Tag, { color: 'red' }, `${(r.injured || r.questionable || r.on_bye || r.zero_starters || []).length} flagged`)
      ),
      (r.injured || r.questionable || r.on_bye || r.zero_starters || []).map(p =>
        e('div', { key: p.id, className: 'player-row' },
          p.slot && e('span', { style: { fontSize: 9, color: 'var(--text3)', minWidth: 52, textAlign: 'center' } }, p.slot),
          e(PosBadge, { pos: p.position }),
          e('span', { className: 'player-name' }, p.name),
          e('span', { className: 'player-team' }, p.team),
          e(Tag, { color: 'red' }, (p.status || '').toUpperCase())
        )
      )
    ))
  );
}

// ── K / DEF LEAGUES VIEW ──────────────────────────────────────────────────────
function KDefLeaguesView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const [filter, setFilter] = useState('all');
  const rows = (data.results || []).filter(r => filter === 'all' || (filter === 'K' ? r.k_slots : filter === 'DEF' ? r.def_slots : r.issues));
  const flagged = rows.filter(r => r.issues > 0), clean = rows.filter(r => !r.issues);
  const btn = (id, label) => e('button', { key: id, onClick: () => setFilter(id), style: { flex: 1, padding: '8px 4px', fontSize: 12, fontWeight: 700, borderRadius: 8, border: `1px solid ${filter === id ? 'var(--accent)' : 'var(--border)'}`, background: filter === id ? 'var(--surface2)' : 'transparent', color: filter === id ? 'var(--text)' : 'var(--text3)' } }, label);
  const slotRow = (x, i) => e('div', { key: i, style: { padding: '8px 0', borderBottom: '1px solid var(--border)' } },
    e('div', { style: { display: 'flex', alignItems: 'center', gap: 8 } },
      e(PosBadge, { pos: x.slot }),
      e('span', { style: { fontSize: 14, fontWeight: 700, flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, x.name || 'Empty slot'),
      x.issue && e(Tag, { color: 'red' }, x.issue),
      x.name && e('span', { style: { fontSize: 14, fontWeight: 700, color: x.proj > 0 ? 'var(--text)' : 'var(--accent2)' } }, x.proj)),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginTop: 2 } },
      `${x.team || ''}${x.team ? ' · ' : ''}${x.rostered_at_pos} ${x.slot} rostered`,
      x.backup ? ` · backup ${x.backup.name} (${x.backup.proj})` : x.issue ? ' · no backup — check waivers' : ''));
  const card = r => e(Card, { key: r.league, borderColor: r.issues ? 'var(--accent2)' : 'var(--accent)' },
    e('div', { className: 'card-header' },
      e('div', null, e('div', { className: 'card-title' }, r.league), r.team && e('div', { className: 'card-subtitle' }, r.team)),
      e('div', { style: { fontSize: 11, color: 'var(--text3)', textAlign: 'right' } }, [r.k_slots ? `${r.k_slots} K` : null, r.def_slots ? `${r.def_slots} DEF` : null].filter(Boolean).join(' · '))),
    r.slots.map(slotRow));
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.with_k_or_def ?? 0, label: `K/DEF Leagues (of ${sm.leagues})`, color: 'var(--text)' }),
      e(StatTile, { value: sm.with_k ?? 0, label: 'Start a K', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.with_def ?? 0, label: 'Start a DEF', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.issues ?? 0, label: 'Slots Flagged', color: 'var(--accent2)' })),
    e('div', { style: { display: 'flex', gap: 6, marginBottom: 12 } }, btn('all', 'All'), btn('K', 'K'), btn('DEF', 'DEF'), btn('issues', '⚠️ Flagged')),
    flagged.map(card),
    clean.length > 0 && e(Card, { borderColor: 'var(--accent)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 6 } }, `✅ Set (${clean.length})`),
      clean.map(r => e('div', { key: r.league, style: { padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 12 } },
        e('div', { style: { fontWeight: 700 } }, r.league, e('span', { style: { color: 'var(--text3)', fontWeight: 400, fontSize: 10 } }, r.team ? ` · ${r.team}` : '')),
        e('div', { style: { color: 'var(--text2)', fontSize: 11 } }, r.slots.map(x => `${x.slot}: ${x.name} (${x.proj})`).join(' · '))))),
    !rows.length && e(Alert, { type: 'info' }, e('p', null, 'No leagues match this filter.')),
    data.neither?.length > 0 && e('details', { style: { marginTop: 8 } },
      e('summary', { style: { fontSize: 11, color: 'var(--text3)', cursor: 'pointer' } }, `${data.neither.length} league${data.neither.length === 1 ? '' : 's'} with no K or DEF slot`),
      e('div', { style: { fontSize: 11, color: 'var(--text2)', lineHeight: 1.6, marginTop: 4 } }, data.neither.join(' · '))));
}

// ── LINEUPS TAB LIST ─────────────────────────────────────────────────────
FF.tab({ id: 'lineups', label: 'Lineups', icon: '⚡', groups: [
  { label: 'Set your lineups', features: [
    { id: 'optimal', title: 'Optimal Lineup', sub: 'Bench, free agent and taxi upgrades', icon: '⚡', tint: 'green',
      endpoint: '/analysis/optimal-lineup', view: OptimalLineupView, badge: d => cnt((d.results || []).length, 'orange') },
    { id: 'upgrade', title: 'Upgrade Recs', sub: 'Ranked on floor (projection vs average)', icon: '🔼', tint: 'blue',
      endpoint: '/analysis/upgrade-recommendations', view: UpgradeRecsView,
      badge: d => cnt((d.results || []).filter(r => r.moves && r.moves.length).length, 'orange') },
    { id: 'starter-upgrades', title: 'Starter Upgrades', sub: 'Slot by slot: bench and free agents', icon: '⬆️', tint: 'blue',
      endpoint: '/analysis/starter-upgrades', view: StarterUpgradesView },
    { id: 'bench-vs-fa', title: 'Bench vs FA', sub: 'Free agents better than your bench', icon: '🔄', tint: 'purple',
      endpoint: '/analysis/bench-vs-fa', view: BenchVsFaView },
    { id: 'waiver-watch', title: 'Waiver Watch', sub: 'Free agents beating your starters', icon: '👀', tint: 'purple',
      endpoint: '/analysis/waiver-watch', view: WaiverWatchView, badge: d => d.summary && cnt(d.summary.leagues_with_pickups, 'green') },
  ]},
  { label: 'Problems to fix', features: [
    { id: 'injured', title: 'OUT / IR Starters', sub: 'Starters who won’t play', icon: '🚨', tint: 'red',
      endpoint: '/alerts/injured-starters', view: AlertsView, viewProps: { type: 'injured' }, badge: d => cnt((d.results || []).length, 'red') },
    { id: 'questionable', title: 'Questionable', sub: 'Game-time decisions in your lineups', icon: '⚠️', tint: 'orange',
      endpoint: '/alerts/questionable-starters', view: AlertsView, viewProps: { type: 'questionable' }, badge: d => cnt((d.results || []).length, 'orange') },
    { id: 'bye', title: 'Starters on Bye', sub: 'Byes still in a lineup', icon: '📅', tint: 'red',
      endpoint: '/alerts/starters-on-bye', view: AlertsView, viewProps: { type: 'bye' }, badge: d => cnt((d.results || []).length, 'red') },
    { id: 'open', title: 'Open Spots', sub: 'Empty starting slots', icon: '⭕', tint: 'red',
      endpoint: '/alerts/open-starter-spots', view: AlertsView, viewProps: { type: 'open' }, badge: d => cnt((d.results || []).length, 'red') },
    { id: 'zero-proj', title: 'Zero-Point Starters', sub: 'Starters projected for nothing', icon: '0️⃣', tint: 'orange',
      endpoint: '/alerts/zero-projection-starters', view: AlertsView, viewProps: { type: 'zero-proj' }, badge: d => cnt((d.results || []).length, 'orange') },
    { id: 'k-def', title: 'K / DEF Leagues', sub: 'Kicker and defense slots, flagged', icon: '🦵', tint: 'blue',
      endpoint: '/analysis/k-def-leagues', view: KDefLeaguesView, badge: d => d.summary && cnt(d.summary.issues, 'red') },
  ]},
]});
