/* Fantasy Manager — tabs/today.js (v10.33)
   The Today tab: its result screens and the list that opens them. Needs core.js loaded first. */

// ── WEEKLY DIGEST VIEW ────────────────────────────────────────────────────────
function WeeklyDigestView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const LV = {
    CRITICAL: { color: 'var(--accent2)', icon: '🚨' }, HIGH: { color: 'var(--accent3)', icon: '🔶' },
    MEDIUM: { color: 'var(--accent4)', icon: '🔹' }, INFO: { color: 'var(--text3)', icon: 'ℹ️' }, CLEAN: { color: 'var(--accent)', icon: '✅' },
  };
  return e('div', null,
    e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: 'var(--text2)', marginBottom: 8 } }, `WEEK ${data.week} CHECKLIST`),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.critical ?? 0, label: 'Critical', color: 'var(--accent2)' }),
      e(StatTile, { value: sm.high ?? 0, label: 'High', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.medium ?? 0, label: 'Medium', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.clean ?? 0, label: 'Clean', color: 'var(--accent)' })
    ),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 12 } }, `${sm.total_actions ?? 0} action item${sm.total_actions === 1 ? '' : 's'} across ${sm.leagues ?? 0} leagues, in your Sleeper league order.`),
    data.errors?.length > 0 && e(Alert, { type: 'warning', title: 'Some checks failed' }, data.errors.map((x, i) => e('div', { key: i, style: { fontSize: 11 } }, x))),
    (() => { const act = (data.leagues || []).filter(lg => lg.action_count > 0); return act.length === 0 && e(Alert, { type: 'success', title: 'All clear' }, e('p', null, 'No league needs anything this week.')); })(),
    (data.leagues || []).filter(lg => lg.action_count > 0).map(lg => {
      const lv = LV[lg.urgency] || LV.INFO;
      return e(Card, { key: lg.league, borderColor: lv.color },
        e('div', { className: 'card-header' },
          e('div', null, e('div', { className: 'card-title' }, lg.league), e('div', { className: 'card-subtitle' }, [lg.team, lg.record, lg.playoff_pct != null ? `${lg.playoff_pct}% playoffs` : null].filter(Boolean).join(' · '))),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontSize: 12, fontWeight: 800, color: lv.color } }, `${lv.icon} ${lg.urgency}`),
            lg.action_count > 0 && e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${lg.action_count} to do`)
          )
        ),
        lg.items.length === 0
          ? e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, 'Nothing to do here this week.')
          : lg.items.map((it, i) => {
            const c = LV[it.level] || LV.INFO;
            return e('div', { key: i, style: { display: 'flex', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border)' } },
              e('span', { style: { fontSize: 12, minWidth: 18 } }, c.icon),
              e('div', { style: { flex: 1, minWidth: 0 } },
                e('div', { style: { fontSize: 12, fontWeight: it.level === 'INFO' ? 400 : 700, color: it.level === 'INFO' ? 'var(--text2)' : 'var(--text)' } }, it.text),
                it.detail && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 2 } }, it.detail)
              )
            );
          })
      );
    }),
    (() => {
      const ignore = (data.leagues || []).filter(lg => lg.action_count === 0);
      if (!ignore.length) return null;
      return e(Card, { borderColor: 'var(--accent)' },
        e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 8 } }, `✅ You can ignore (${ignore.length}) — nothing to do this week`),
        ignore.map(lg => {
          const odds = lg.items.find(i => i.type === 'odds');
          const live = lg.items.find(i => i.type === 'live');
          return e('div', { key: lg.league, style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11, padding: '4px 0', borderBottom: '1px solid var(--border)' } },
            e('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 } }, lg.league,
              lg.team ? e('span', { style: { color: 'var(--text3)', fontSize: 10 } }, ` · ${lg.team}`) : null),
            e('span', { style: { color: 'var(--text3)', whiteSpace: 'nowrap' } },
              [lg.record, lg.playoff_pct != null ? `${lg.playoff_pct}%` : null, live ? '🔴 live' : null].filter(Boolean).join(' · '))
          );
        })
      );
    })()
  );
}

function ThereIsAChanceView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const COLOR = { WON: 'var(--accent)', 'LOCKED IN': 'var(--accent)', WINNING: 'var(--accent)', 'COIN FLIP': 'var(--accent3)', "THERE'S A CHANCE": 'var(--accent3)', 'LONG SHOT': '#ff8c42', ELIMINATED: 'var(--accent2)', LOST: 'var(--accent2)', TIED: 'var(--text2)' };
  const chip = (p, color) => e('div', { key: p.id, style: { display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 8px', background: 'var(--bg)', border: `1px solid ${color}`, borderRadius: 6 } },
    e(PosBadge, { pos: p.position }), e('span', { style: { fontSize: 11 } }, p.name),
    p.state === 'live'
      ? e('span', { style: { fontSize: 10, color: 'var(--text3)' } }, `${p.actual} + ${p.remaining_proj} (${p.progress}% done)`)
      : e('span', { style: { fontSize: 11, fontWeight: 700, color } }, p.proj_pts));
  const group = (title, pre, live, color) => (pre.length + live.length > 0) && e('div', { style: { marginBottom: 8 } },
    e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color, marginBottom: 5 } }, `${title} · ${live.length ? `${live.length} in progress, ` : ''}${pre.length} to play`),
    e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 4 } }, live.map(p => chip(p, 'var(--accent4)')), pre.map(p => chip(p, color))));
  const oneLiner = (r) => e('div', { key: r.league, style: { display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: 11, padding: '4px 0', borderBottom: '1px solid var(--border)' } },
    e('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 } }, r.league, e('span', { style: { color: 'var(--text3)', fontSize: 10 } }, ` · vs ${r.opp_name}`)),
    e('span', { style: { whiteSpace: 'nowrap', color: 'var(--text3)' } }, `${r.my_live.toFixed(1)}–${r.opp_live.toFixed(1)} · `, e('span', { style: { color: COLOR[r.status] || 'var(--text2)', fontWeight: 700 } }, r.status === 'WON' || r.status === 'LOST' || r.status === 'TIED' ? r.status : `${r.win_prob}%`)));

  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.in_play ?? 0, label: 'In Play', color: 'var(--accent3)' }),
      e(StatTile, { value: `${sm.favored ?? 0}/${sm.underdog ?? 0}`, label: 'Favored / Dog', color: 'var(--text2)' }),
      e(StatTile, { value: `${sm.won ?? 0}-${sm.lost ?? 0}`, label: 'Final', color: 'var(--accent)' }),
      e(StatTile, { value: sm.expected_wins ?? 0, label: 'Exp. Wins', color: 'var(--accent4)' })
    ),
    data.have_schedule === false && e(Alert, { type: 'warning' }, e('p', null, 'Live game status unavailable — players whose team has kicked off are treated as in progress at 50%.')),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 12 } }, 'Closest games first. Leagues with under 3% to win and finished matchups are collapsed at the bottom.'),
    (data.results || []).map(r => {
      const sc = COLOR[r.status] || 'var(--text2)';
      const pct = Math.max(0, Math.min(100, r.win_prob));
      return e(Card, { key: r.league, borderColor: sc },
        e('div', { className: 'card-header' },
          e('div', null, e('div', { className: 'card-title' }, r.league), e('div', { className: 'card-subtitle' }, `${r.team ? r.team + ' · ' : ''}vs ${r.opp_name}`)),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', color: sc } }, `${r.win_prob}%`),
            e('div', { style: { fontSize: 10, color: sc, fontWeight: 700 } }, r.status))
        ),
        e('div', { className: 'bar-track', style: { marginBottom: 10, height: 6 } }, e('div', { className: 'bar-fill', style: { width: `${pct}%`, background: sc } })),
        e('div', { className: 'grid-2', style: { marginBottom: 10 } },
          e('div', { style: { padding: '8px 12px', background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' } },
            e('div', { style: { fontSize: 10, color: 'var(--text3)', marginBottom: 2 } }, `YOU · ${r.my_left} left`),
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.8rem', color: 'var(--accent)' } }, r.my_live?.toFixed(2)),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, r.my_left > 0 ? `+${r.my_remaining_proj} → ${r.my_exp} exp ±${r.my_sd}` : 'final')),
          e('div', { style: { padding: '8px 12px', background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' } },
            e('div', { style: { fontSize: 10, color: 'var(--text3)', marginBottom: 2 } }, `THEM · ${r.opp_left} left`),
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.8rem', color: 'var(--accent2)' } }, r.opp_live?.toFixed(2)),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, r.opp_left > 0 ? `+${r.opp_remaining_proj} → ${r.opp_exp} exp ±${r.opp_sd}` : 'final'))
        ),
        r.need_per_player != null && e('div', { style: { fontSize: 11, color: 'var(--text2)', marginBottom: 8 } },
          `Need ~${r.need_per_player} pts from each of your ${r.my_left} remaining to pull even with their expected ${r.opp_exp}.`),
        group('Your remaining', r.my_remaining || [], r.my_in_progress || [], 'rgba(0,229,160,0.5)'),
        group('Their remaining', r.opp_remaining || [], r.opp_in_progress || [], 'rgba(255,92,92,0.4)')
      );
    }),
    data.skipped?.length > 0 && e(Card, { borderColor: 'var(--accent2)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent2)', marginBottom: 6 } }, `🙈 You can ignore (${data.skipped.length}) — under 3% to win`),
      data.skipped.map(oneLiner)),
    data.finished?.length > 0 && e(Card, { borderColor: 'var(--text3)' },
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6 } }, `🏁 Final (${data.finished.length}) — ${sm.won ?? 0} won, ${sm.lost ?? 0} lost`),
      data.finished.map(oneLiner)),
    !data.results?.length && !data.skipped?.length && !data.finished?.length && e(Alert, { type: 'info' }, e('p', null, 'No live matchup data found.')),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── HAIL MARY VIEW ────────────────────────────────────────────────────────────
function HailMaryView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const SIT = { 'HAIL MARY': 'var(--accent2)', 'IN REACH': 'var(--accent3)', 'HOLD ON': 'var(--accent)', 'SWEAT IT OUT': 'var(--accent4)', 'YOUR MOVE': 'var(--accent3)' };
  const prow = (p, color, needLabel) => e('div', { key: p.id, style: { display: 'flex', alignItems: 'center', gap: 8, padding: '6px 0', borderBottom: '1px solid var(--border)' } },
    e(PosBadge, { pos: p.position }),
    e('div', { style: { flex: 1, minWidth: 0 } },
      e('div', { style: { fontSize: 14, fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, p.name),
      e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, p.state === 'live' ? `${p.team} · 🔴 ${p.actual} so far · ${p.progress}% done` : `${p.team} · yet to play`)),
    e('div', { style: { textAlign: 'right', minWidth: 64 } },
      e('div', { style: { fontSize: 15, fontWeight: 800, color } }, p.needs != null ? p.needs : '—'),
      e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${needLabel} · proj ${p.rem_proj}`)));
  return e('div', null,
    e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: 'var(--text2)', marginBottom: 8 } }, `WEEK ${data.week} · HAIL MARY`),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.in_doubt ?? 0, label: 'Still In Doubt', color: 'var(--accent3)' }),
      e(StatTile, { value: `${sm.favored ?? 0}/${sm.underdog ?? 0}`, label: 'Favored / Dog', color: 'var(--text2)' }),
      e(StatTile, { value: sm.swing_wins ?? 0, label: 'Exp. Wins Here', color: 'var(--accent4)' }),
      e(StatTile, { value: `${sm.ignored_locked ?? 0} / ${sm.ignored_lost ?? 0}`, label: 'Ignored: Safe / Gone', color: 'var(--text3)' })
    ),
    data.have_schedule === false && e(Alert, { type: 'warning' }, e('p', null, 'Live game status unavailable — in-progress players estimated at 50%.')),
    !data.results?.length && e(Alert, { type: 'success', title: 'Nothing in doubt' }, e('p', null, 'Every matchup is either safely won, out of reach, or finished.')),
    (data.results || []).map(r => {
      const c = SIT[r.situation] || 'var(--text2)';
      return e(Card, { key: r.league, borderColor: c },
        e('div', { className: 'card-header' },
          e('div', null, e('div', { className: 'card-title' }, r.league), e('div', { className: 'card-subtitle' }, `${r.team} vs ${r.opp_name}`)),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', color: c, lineHeight: 1 } }, `${r.win_prob}%`),
            e('div', { style: { fontSize: 11, fontWeight: 800, color: c } }, r.situation))),
        e('div', { style: { fontSize: 13, color: 'var(--text)', marginBottom: 10, lineHeight: 1.4 } }, r.headline),
        e('div', { className: 'grid-2', style: { marginBottom: 10 } },
          e('div', { style: { padding: '8px 10px', background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' } },
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `YOU · ${r.my_left} left`),
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', color: 'var(--accent)' } }, r.my_live.toFixed(1)),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `exp ${r.my_exp}`)),
          e('div', { style: { padding: '8px 10px', background: 'var(--surface2)', borderRadius: 8, textAlign: 'center' } },
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `THEM · ${r.opp_left} left`),
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', color: 'var(--accent2)' } }, r.opp_live.toFixed(1)),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `exp ${r.opp_exp}`))),
        r.my_players.length > 0 && e('div', { style: { marginBottom: 10 } },
          e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 4 } },
            `Your remaining · need ${r.my_need}${r.pace_pct != null ? ` (${r.pace_pct}% of proj)` : ''}`),
          r.my_players.map(p => prow(p, r.pace_pct > 115 ? 'var(--accent2)' : 'var(--accent)', 'needs'))),
        r.their_players.length > 0 && e('div', null,
          e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent2)', marginBottom: 4 } },
            r.hold_under != null ? `Their remaining · must stay under ${r.hold_under}` : `Their remaining · need ${r.their_need} to pass you`),
          r.their_players.map(p => prow(p, 'var(--accent2)', r.hold_under != null ? 'their share' : 'their need')))
      );
    }),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── ROOTING GUIDE VIEW ────────────────────────────────────────────────────────
function RootingGuideView({ data }) {
  if (!data) return null;
  const sm = data.summary || {};
  const netColor = n => n > 0 ? 'var(--accent)' : n < 0 ? 'var(--accent2)' : 'var(--text3)';
  const row = (r, i) => e('div', { key: r.id, className: 'player-row', style: { opacity: r.played ? 0.75 : 1 } },
    e('span', { style: { fontSize: 10, color: 'var(--text3)', minWidth: 20, textAlign: 'right' } }, i + 1),
    e(PosBadge, { pos: r.position }),
    e('span', { className: 'player-name' }, r.name),
    e('span', { className: 'player-team' }, r.team),
    r.injury_status && !r.played && e(Tag, { color: 'red' }, r.injury_status.toUpperCase()),
    e('span', { style: { fontSize: 11, color: 'var(--text2)', whiteSpace: 'nowrap' } },
      e('span', { style: { color: 'var(--accent)' } }, `${r.for} for`), ' · ', e('span', { style: { color: 'var(--accent2)' } }, `${r.against} vs`)),
    e('span', { className: 'player-pts', style: { color: netColor(r.net), minWidth: 36, textAlign: 'right' } }, (r.net > 0 ? '+' : '') + r.net)
  );
  const section = (title, rows, total, color, emptyMsg) => e(Card, { borderColor: color },
    e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color, marginBottom: 8 } },
      `${title} (${rows.length}${total > rows.length ? ` of ${total}` : ''})`),
    rows.length ? rows.map(row) : e('div', { style: { fontSize: 11, color: 'var(--text3)' } }, emptyMsg)
  );
  return e('div', null,
    e('div', { style: { fontFamily: 'Bebas Neue', letterSpacing: 2, color: 'var(--text2)', marginBottom: 8 } }, `WEEK ${data.week} ROOTING GUIDE`),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.leagues ?? 0, label: 'Matchups', color: 'var(--text2)' }),
      e(StatTile, { value: sm.players_remaining ?? 0, label: 'Still To Play', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.players_live ?? 0, label: 'In Progress', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.players_played ?? 0, label: 'Final', color: 'var(--text3)' })
    ),
    sm.have_schedule === false && e(Alert, { type: 'warning' }, e('p', null, 'Live game status unavailable — players whose team has played are shown as "played / in progress".')),
    (sm.biggest_for || sm.biggest_against) && e('div', { className: 'grid-2', style: { gap: 8, marginBottom: 12 } },
      sm.biggest_for && e('div', { style: { padding: '10px 12px', background: 'rgba(0,229,160,0.06)', border: '1px solid rgba(0,229,160,0.3)', borderRadius: 10 } },
        e('div', { style: { fontSize: 10, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: 1 } }, '🙏 Root hardest for'),
        e('div', { style: { fontSize: 13, fontWeight: 700 } }, `${sm.biggest_for.name} (${sm.biggest_for.position}, ${sm.biggest_for.team})`),
        e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${sm.biggest_for.for} for · ${sm.biggest_for.against} against · net +${sm.biggest_for.net}`)),
      sm.biggest_against && e('div', { style: { padding: '10px 12px', background: 'rgba(255,92,92,0.06)', border: '1px solid rgba(255,92,92,0.3)', borderRadius: 10 } },
        e('div', { style: { fontSize: 10, color: 'var(--accent2)', textTransform: 'uppercase', letterSpacing: 1 } }, '🙅 Root hardest against'),
        e('div', { style: { fontSize: 13, fontWeight: 700 } }, `${sm.biggest_against.name} (${sm.biggest_against.position}, ${sm.biggest_against.team})`),
        e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `${sm.biggest_against.for} for · ${sm.biggest_against.against} against · net ${sm.biggest_against.net}`))
    ),
    data.teams_remaining?.length > 0 && e(Card, null,
      e('div', { style: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 8 } }, 'Games still to come — where your interest is'),
      e('div', { style: { display: 'flex', flexWrap: 'wrap', gap: 6 } },
        data.teams_remaining.map(g => e('span', { key: g.team, style: { fontSize: 11, padding: '4px 8px', borderRadius: 6, border: `1px solid ${netColor(g.net)}`, background: g.state === 'live' ? 'rgba(92,158,255,0.10)' : 'transparent', color: 'var(--text2)' } },
          g.state === 'live' && '🔴 ', e('b', null, g.team), ` ${g.for}/${g.against} `, e('span', { style: { color: netColor(g.net), fontWeight: 700 } }, (g.net > 0 ? '+' : '') + g.net)))
      ),
      e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 6 } }, 'Team · starters for/against · net · 🔴 = in progress')
    ),
    section('⏳ Still to play', data.remaining || [], data.remaining_total || 0, 'var(--accent3)', 'Every starter has already kicked off this week.'),
    (data.live_total > 0 || sm.have_schedule === false) && section(sm.have_schedule === false ? '🔴 Played / in progress' : '🔴 In progress', data.live || [], data.live_total || 0, 'var(--accent4)', 'No games in progress right now.'),
    sm.have_schedule !== false && section('✅ Final', data.played || [], data.played_total || 0, 'var(--text3)', 'No games have finished yet.'),
    data.on_bye?.length > 0 && section('📅 On bye (started anyway)', data.on_bye, data.on_bye.length, 'var(--accent2)', ''),
    sm.no_matchup?.length > 0 && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, `No matchup this week in: ${sm.no_matchup.join(', ')}`),
    data.note && e('div', { style: { fontSize: 10, color: 'var(--text3)', marginTop: 8 } }, data.note)
  );
}

// ── WEEK ANALYSIS VIEW ────────────────────────────────────────────────────────
function WeekAnalysisView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No matchup data found.'));
  const wins = data.results.filter(r => r.won).length;
  const losses = data.results.filter(r => !r.won && !r.tied).length;
  const ties = data.results.filter(r => r.tied).length;

  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: `${wins}-${losses}${ties ? `-${ties}` : ''}`, label: 'Record', color: 'var(--accent)' }),
      e(StatTile, { value: data.results.reduce((s,r) => s + (r.my_pts||0), 0).toFixed(1), label: 'Total Pts', color: 'var(--accent4)' }),
      e(StatTile, { value: data.results.filter(r => (r.optimal_gain||0) > 2).length, label: 'Lineup Issues', color: 'var(--accent3)' })
    ),
    data.results.map(r => {
      const winColor = r.won ? 'var(--accent)' : r.tied ? 'var(--accent3)' : 'var(--accent2)';
      return e(Card, { key: r.league, borderColor: winColor },
        e('div', { className: 'card-header' },
          e('div', null,
            e('div', { className: 'card-title' }, r.league),
            e('div', { className: 'card-subtitle' }, `${r.team ? r.team + ' · ' : ''}vs ${r.opp_name}`)
          ),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.6rem', color: winColor } },
              `${r.my_pts?.toFixed(2)} – ${r.opp_pts?.toFixed(2)}`
            ),
            e('div', { style: { fontSize: 11, color: winColor, fontWeight: 700 } }, r.won ? '✅ WIN' : r.tied ? '🤝 TIE' : '❌ LOSS'),
            r.optimal_gain > 2 && e('div', { style: { fontSize: 10, color: 'var(--accent3)' } }, `+${r.optimal_gain?.toFixed(1)} left on bench`)
          )
        ),
        r.my_starters?.length > 0 && e('div', null,
          e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--text3)', marginBottom: 6 } }, 'Your Starters'),
          r.my_starters.map(p => {
            const ptColor = p.pts >= 20 ? 'var(--accent)' : p.pts >= 10 ? 'var(--text2)' : 'var(--accent2)';
            return e('div', { key: p.id, className: 'player-row' },
              e(PosBadge, { pos: p.position }),
              e('span', { className: 'player-name' }, p.name),
              e('span', { className: 'player-team' }, p.team),
              e('span', { className: 'player-pts', style: { color: ptColor } }, p.pts?.toFixed(2))
            );
          })
        )
      );
    })
  );
}

function WeekRecordView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No matchup data found.'));
  const sm = data.summary || {};
  const live = data.results.filter(r => r.status === 'LIVE');
  const finals = data.results.filter(r => r.status === 'FINAL');
  const pregame = data.results.filter(r => r.status === 'PREGAME');
  const flipped = data.results.filter(r => r.flipped);
  const col = w => w ? 'var(--accent)' : 'var(--accent2)';
  const row = r => e('div', { key: r.league, style: { display: 'flex', alignItems: 'center', gap: 10, padding: '8px 12px', background: 'var(--surface)', border: '1px solid var(--border)', borderLeft: `3px solid ${col(r.exp_win)}`, borderRadius: 8, marginBottom: 6 } },
    e('div', { style: { flex: 1, minWidth: 0 } },
      e('div', { style: { fontWeight: 700, fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, r.league),
      e('div', { style: { fontSize: 11, color: 'var(--text2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, `${r.team ? r.team + ' · ' : ''}vs ${r.opp_name}`)),
    e('div', { style: { textAlign: 'center', minWidth: 78 } },
      e('div', { style: { fontSize: 11, color: col(r.proj_win) } }, `${r.my_proj.toFixed(1)}–${r.opp_proj.toFixed(1)}`),
      e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, `proj ${r.win_prob}%`)),
    e('div', { style: { textAlign: 'center', minWidth: 78 } },
      e('div', { style: { fontSize: 12, fontWeight: 700, color: col(r.exp_win) } }, `${r.my_exp.toFixed(1)}–${r.opp_exp.toFixed(1)}`),
      e('div', { style: { fontSize: 9, color: 'var(--text3)' } }, r.status === 'FINAL' ? 'final' : r.status === 'LIVE' ? `exp ${r.exp_prob}% · ${r.my_left}/${r.opp_left} left` : `exp ${r.exp_prob}%`)),
    e('div', { style: { textAlign: 'right', minWidth: 44 } },
      e('div', { style: { fontWeight: 800, fontSize: 11, color: col(r.exp_win) } }, r.status === 'FINAL' ? (r.actual_tied ? 'TIE' : r.actual_won ? 'WIN' : 'LOSS') : (r.exp_win ? '▲ WIN' : '▼ LOSS')),
      r.flipped && e('div', { style: { fontSize: 9, color: r.exp_win ? 'var(--accent)' : 'var(--accent2)', fontWeight: 700 } }, r.exp_win ? 'flipped up' : 'flipped down'),
      r.surprise && e('div', { style: { fontSize: 9, color: 'var(--accent3)' } }, r.surprise === 'upset_win' ? '🎉 upset' : '😤 upset'))
  );
  const section = (title, rows, color) => rows.length > 0 && e('div', { style: { marginBottom: 12 } },
    e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color, marginBottom: 6 } }, `${title} (${rows.length})`), rows.map(row));
  return e('div', null,
    e('div', { className: 'stat-row' },
      e(StatTile, { value: sm.projected, label: 'Projected', color: 'var(--accent4)' }),
      e(StatTile, { value: sm.expected, label: 'Expected Now', color: 'var(--accent3)' }),
      e(StatTile, { value: sm.finals > 0 ? sm.final : '—', label: `Final (${sm.finals ?? 0})`, color: 'var(--accent)' }),
      e(StatTile, { value: `+${sm.flipped_up ?? 0} / −${sm.flipped_down ?? 0}`, label: 'Flipped vs Proj', color: 'var(--text2)' })
    ),
    data.have_schedule === false && e(Alert, { type: 'warning' }, e('p', null, 'Live game status unavailable — in-progress players are estimated at 50%.')),
    e('div', { style: { fontSize: 11, color: 'var(--text3)', marginBottom: 12 } },
      'Projected = pre-game projections (frozen). Expected = actual points for finished players, banked + remaining share for in-progress, projection for players yet to play.'),
    section('🔄 Flipped vs projection', flipped, 'var(--accent3)'),
    section('🔴 In progress', live.filter(r => !r.flipped), 'var(--accent4)'),
    section('⏳ Pregame', pregame.filter(r => !r.flipped), 'var(--text3)'),
    section('🏁 Final', finals.filter(r => !r.flipped), 'var(--accent)')
  );
}

// ── WEEK REVIEW VIEW ──────────────────────────────────────────────────────────
function WeekReviewView({ data }) {
  if (!data?.results?.length) return e(Alert, { type: 'info' }, e('p', null, 'No matchup data found for that week.'));
  const S = data.summary || {};
  const GRADE_COLOR = { A: 'var(--accent)', B: 'var(--accent4)', C: 'var(--accent3)', D: '#ff8c42', F: 'var(--accent2)' };
  const gradeChips = Object.entries(S.grades || {}).filter(([, n]) => n > 0);

  const DiffRow = ({ p }) => e('div', { className: 'player-row' },
    e(PosBadge, { pos: p.position }),
    e('span', { className: 'player-name' }, p.name),
    e('span', { className: 'player-team' }, p.team),
    e('span', { style: { fontSize: 10, color: 'var(--text3)' } }, `proj ${p.proj?.toFixed(1)}`),
    e('span', { className: 'player-pts', style: { color: p.diff < 0 ? 'var(--accent2)' : 'var(--accent)' } },
      `${p.pts?.toFixed(1)} (${p.diff > 0 ? '+' : ''}${p.diff})`)
  );

  return e('div', null,
    !data.week_done && e(Alert, { type: 'info' }, e('p', null, `Week ${data.week} isn't finished yet — this is a partial review.`)),
    e('div', { className: 'stat-row' },
      e(StatTile, { value: `${S.wins}-${S.losses}`, label: 'Week Record', color: 'var(--accent)' }),
      e(StatTile, { value: `${S.avg_efficiency}%`, label: 'Avg Efficiency', color: 'var(--accent4)' }),
      e(StatTile, { value: S.total_left_on_bench, label: 'Pts On Bench', color: 'var(--accent3)' }),
      e(StatTile, { value: S.cost_games, label: 'Lineup Cost A Win', color: S.cost_games ? 'var(--accent2)' : 'var(--text3)' })
    ),
    gradeChips.length > 0 && e('div', { style: { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 16 } },
      gradeChips.map(([g, n]) => e('div', { key: g, style: { padding: '5px 12px', borderRadius: 20, border: `1px solid ${GRADE_COLOR[g]}`, color: GRADE_COLOR[g], fontSize: 12, fontWeight: 700 } }, `${g}: ${n}`))
    ),
    data.results.map(r => {
      const gc = GRADE_COLOR[r.grade];
      const resColor = r.won ? 'var(--accent)' : r.won === false ? 'var(--accent2)' : 'var(--text3)';
      return e(Card, { key: r.league, borderColor: gc },
        e('div', { className: 'card-header' },
          e('div', null,
            e('div', { className: 'card-title' }, r.league),
            e('div', { className: 'card-subtitle' }, `${r.team ? r.team + ' · ' : ''}vs ${r.opp_name}`)
          ),
          e('div', { style: { textAlign: 'right' } },
            e('div', { style: { fontFamily: 'Bebas Neue', fontSize: '1.8rem', color: gc, lineHeight: 1 } }, r.grade),
            e('div', { style: { fontSize: 12, fontWeight: 700, color: resColor } },
              `${r.won ? 'W' : r.won === false ? 'L' : '—'} ${r.my_pts?.toFixed(1)}–${r.opp_pts?.toFixed(1) ?? '?'}`)
          )
        ),
        r.cost_the_game && e(Alert, { type: 'error' }, e('p', null,
          `Your optimal lineup (${r.optimal_pts.toFixed(1)}) would have beaten ${r.opp_name} (${r.opp_pts.toFixed(1)}). This one was left on the bench.`)),
        e('div', { style: { marginBottom: 12 } },
          e('div', { style: { display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 } },
            e('span', { style: { color: 'var(--text3)' } }, 'Lineup efficiency'),
            e('span', { style: { color: gc, fontWeight: 700 } }, `${r.efficiency}% · ${r.starter_pts.toFixed(1)} of ${r.optimal_pts.toFixed(1)} possible`)
          ),
          e('div', { className: 'bar-track', style: { height: 8 } }, e('div', { className: 'bar-fill', style: { width: `${r.efficiency}%`, background: gc } }))
        ),
        r.missed_moves?.length > 0
          ? e(MovesList, { moves: r.missed_moves, ptsKey: 'pts', title: `🪑 Left On Bench · ${r.left_on_bench.toFixed(1)} pts`,
                           verb: { start: 'SHOULD\'VE STARTED', move: 'SHOULD\'VE MOVED', bench: 'SHOULD\'VE SAT' } })
          : e('div', { style: { fontSize: 12, color: 'var(--accent)', marginBottom: 12 } }, '✅ You started your best possible lineup.'),
        r.underachievers?.length > 0 && e('div', { style: { marginBottom: 12 } },
          e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent2)', marginBottom: 6 } }, '📉 Underachievers'),
          r.underachievers.map(p => e(DiffRow, { key: p.id, p }))
        ),
        r.overachievers?.length > 0 && e('div', { style: { marginBottom: 12 } },
          e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent)', marginBottom: 6 } }, '📈 Overachievers'),
          r.overachievers.map(p => e(DiffRow, { key: p.id, p }))
        ),
        e('div', { style: { borderTop: '1px solid var(--border)', paddingTop: 12 } },
          e('div', { style: { display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 } },
            e('div', { style: { fontSize: 10, textTransform: 'uppercase', letterSpacing: 1, color: 'var(--accent4)' } }, `➡️ Week ${r.next_week} Recommendations`),
            e('div', { style: { fontSize: 10, color: 'var(--text3)' } }, `current ${r.next_current_pts} → optimal ${r.next_optimal_pts}`)
          ),
          r.next_flags?.map(p => e('div', { key: p.id, style: { display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: 'rgba(255,92,92,0.08)', border: '1px solid rgba(255,92,92,0.3)', borderRadius: 6, marginBottom: 4, fontSize: 12 } },
            e(PosBadge, { pos: p.position }), e('span', { style: { flex: 1 } }, p.name),
            e(Tag, { color: 'red' }, p.on_bye ? 'ON BYE' : (p.injury_status || '').toUpperCase())
          )),
          r.still_starting_under?.map(p => e('div', { key: 'u' + p.id, style: { display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', background: 'rgba(255,179,71,0.06)', border: '1px solid rgba(255,179,71,0.3)', borderRadius: 6, marginBottom: 4, fontSize: 12 } },
            e(PosBadge, { pos: p.position }), e('span', { style: { flex: 1 } }, p.name),
            e(Tag, { color: 'orange' }, 'UNDERPERFORMED · STILL STARTING')
          )),
          r.next_moves?.length > 0
            ? e(MovesList, { moves: r.next_moves, ptsKey: 'pts' })
            : e('div', { style: { fontSize: 12, color: 'var(--accent)' } }, '✅ Lineup already optimal for next week.')
        )
      );
    })
  );
}

// ── TODAY TAB LIST ───────────────────────────────────────────────────────
FF.tab({ id: 'today', label: 'Today', icon: '☀️', groups: [
  { label: 'Start here', features: [
    { id: 'weekly-digest', title: 'Weekly Digest', sub: 'Every league’s to-do list, most urgent first', icon: '☀️', tint: 'orange',
      endpoint: '/analysis/weekly-digest', view: WeeklyDigestView,
      badge: d => d.summary && (d.summary.critical ? cnt(d.summary.critical, 'red') : cnt(d.summary.total_actions, 'orange')) },
  ]},
  { label: 'Game day', features: [
    { id: 'theres-a-chance', title: 'There’s A Chance', sub: 'Live win % for every matchup', icon: '🎲', tint: 'blue',
      endpoint: '/analysis/theres-a-chance', view: ThereIsAChanceView, badge: d => d.summary && cnt(d.summary.in_play, 'blue') },
    { id: 'hail-mary', title: 'Hail Mary', sub: 'Games still in doubt and what it takes', icon: '🙏', tint: 'orange',
      endpoint: '/analysis/hail-mary', view: HailMaryView, badge: d => d.summary && cnt(d.summary.in_doubt, 'blue') },
    { id: 'rooting-guide', title: 'Rooting Guide', sub: 'Who to cheer for and against', icon: '📣', tint: 'purple',
      endpoint: '/analysis/rooting-guide', view: RootingGuideView },
  ]},
  { label: 'This week', features: [
    { id: 'week-record', title: 'Week Record', sub: 'Projected vs expected vs final record', icon: '🎯', tint: 'green',
      endpoint: '/analysis/week-record', view: WeekRecordView },
    { id: 'week-analysis', title: 'Week Analysis', sub: 'Matchup by matchup breakdown', icon: '📊', tint: 'blue',
      endpoint: '/analysis/week', view: WeekAnalysisView },
    { id: 'week-review', title: 'Week Review', sub: 'Hindsight lineup, under/over-achievers', icon: '📝', tint: 'purple',
      endpoint: '/analysis/week-review', view: WeekReviewView },
  ]},
]});
