# Leaderboard Redesign

## Intent

The leaderboard is a three-column table (handle, week record, points for/against) with a league toggle. It answers "what is my season record against each friend" and nothing else. The original spec calls this screen "Leaderboard & history (past weeks, head-to-head)"; the history half was never built. This redesign makes the page worth opening mid-week: it shows where you stand right now against each friend, how you got there week by week, and how well you pick overall.

Scope decided by the user on 2026-11-03: all eight items below.

## Goals

1. **Season summary strip** at the top: combined weeks W/L/T across all friends and total points for and against, scoreboard style (black and gold like the matchup totals).
2. **Card rows instead of a table.** One card per friend: large W-L-T, signed point differential (green positive, red negative), a left border color that says lead / trail / even at a glance. The handle links to the matchup page as today.
3. **Sort toggle**: by weeks won (server order, the default) or by point differential.
4. **Empty state** links to the Friends page.
5. **This week, live**: each card shows the current week's running score against that friend, or "not started" when no game in the week has kicked off.
6. **Week-by-week history**: a card expands to show every counted week as a chip (W/L/T with points for–against), in season order.
7. **Streak**: the trailing run of identical week outcomes, shown as `W3`, `L2`, `T1`, or nothing when there are no weeks.
8. **Your season stats card**: games picked (final games only), winners called with percentage, exact scores hit. Per user, not per pair.

## Non-goals

- A global ranking. Rows stay per opponent (CLAUDE.md rule).
- Past-season picker. The page keeps using the current season from `currentWeek`.
- Changing any scoring or visibility rule.

## Anti-goals

- Leaking a friend's picks, or whether one exists, for a game that hasn't kicked off. The per-week list must only contain weeks the existing head-to-head already counts (someone picked a game that has kicked off).
- Letting the spread affect anything.

## Decisions

### API (my calls)

- `HeadToHead` (service and GraphQL) gains `weeks: [WeekLine]`, ordered by `(seasonType, week)`. `WeekLine = { seasonType, week, pointsFor, pointsAgainst }`. The week's outcome is not sent: the client derives it as more points wins, equal ties, which is the whole rule.
- `LeaderboardRow` inherits `weeks`, so the leaderboard page gets everything in one query.
- New query `seasonStats(league, season): SeasonStats { picked, winners, exact }`. `picked` counts my picks on `final` games in that league and season. `winners` counts those where I picked the actual winner. `exact` counts closeness 0. Non-final games are ignored, so the percentage is over decided games only.
- No schema migration. Everything is computed on read, like the rest of results.

### Web (my calls)

- All page arithmetic lives in `web/src/lib/standings.ts` as pure functions with Vitest tests. The page component only renders.
- Expand/collapse uses the native `<details>` element. Sort toggle is two buttons with `aria-pressed`.
- Lead / trail / even per friend: compare weeks won to weeks lost; if equal, the sign of the point differential; zero differential is even.
- Week chip labels: regular season `W5`, postseason `P1`, preseason `Pre1` (ESPN season types 2, 3, 1).
- Percentage is omitted (not `NaN%`) when no games are decided.
- The page's exact query strings get a test in the API suite, matching the project convention.

## Left to the builder

Card spacing, chip styling and exact copy within the look already established by the matchup page (`--chalk` cards, `--turf` border, `--gold` highlights, `--display` font).
