# Leaderboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the leaderboard from a static per-friend table into a page with a season summary, per-friend cards showing this week's live score, streak and week-by-week history, a sort toggle, and a personal season-stats card.

**Architecture:** The results service already groups head-to-head points by week and discards the detail; Task 1 keeps it and exposes it as `weeks` on `HeadToHead` (and therefore `LeaderboardRow`). Task 2 adds a small `season_stats` read over the user's own picks. Tasks 3 and 4 put every page calculation into a pure `standings.ts` module with Vitest tests and rewrite the Svelte page to render it. No migration: everything is computed on read like the rest of `results.py`.

**Tech Stack:** Python 3.12, strawberry-graphql, SQLAlchemy 2 async, pytest (API). SvelteKit 2 / Svelte 5, TypeScript, Vitest (web). Tests run via `docker compose run --rm api pytest` and `docker compose run --rm web npm test`.

**Spec:** `docs/superpowers/specs/2026-11-03-leaderboard-redesign-design.md`

## Global Constraints

- A friend's pick, or whether one exists, is never returned before that game's kickoff, and never to a non-friend. The new `weeks` list only contains weeks the existing head-to-head already counts.
- The spread never affects scoring.
- Scoring, week result and visibility rules are unchanged; nothing in `scoring.py` changes.
- Rows stay per opponent; no global ranking.
- TDD: every task starts with a failing test. SOLID: services take `AsyncSession` (and `Clock` where they use time); resolvers stay thin. No concurrent session work in resolvers.
- Each page's exact query string gets a test (API suite, Task 4).
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- A friend's early pick on a game that hasn't kicked off must not create a week entry. Pinned in Task 1 by asserting `weeks == []` in `test_head_to_head_ignores_picks_before_kickoff`.
- Current week with no kicked-off games: the card must say "not started", not show 0–0. Pinned in Task 3 by `thisWeek` returning `undefined` and Task 4 rendering the copy.
- A brand-new friend with no counted weeks: 0-0-0, blank streak, `even` lead, no crash on empty `weeks`. Pinned in Task 3 (`streak([])`, `lead` on zeros).
- Zero decided games in `seasonStats`: no `NaN%`. Pinned in Task 3 by `pct(0, 0) === ''`.
- Postseason weeks restart numbering at 1; chips must not read as two "week 1"s. Pinned in Task 3 by `weekLabel` tests for season types 1, 2, 3.

---

### Task 1: Per-week lines on head-to-head

**Files:**
- Modify: `api/app/results.py` (`HeadToHead` at line 33, `head_to_head` at line 100)
- Modify: `api/app/gql/schema.py` (`HeadToHead`/`LeaderboardRow` types at lines 171-183, resolvers at lines 275-286)
- Test: `api/tests/test_results.py`

**Interfaces:**
- Consumes: existing `results.head_to_head(session, clock, me, friend_id, league, season)` and `results.leaderboard(...)`.
- Produces: `results.WeekLine(season_type: int, week: int, points_for: int, points_against: int)` (frozen dataclass); `results.HeadToHead` gains a last field `weeks: list[WeekLine]` ordered by `(season_type, week)`. GraphQL `WeekLine { seasonType week pointsFor pointsAgainst }` and `weeks: [WeekLine!]!` on both `HeadToHead` and `LeaderboardRow`.

- [ ] **Step 1: Write the failing tests**

In `api/tests/test_results.py`, add after `test_head_to_head_skips_weeks_neither_picked`:

```python
async def test_head_to_head_lists_counted_weeks_in_order(session, clock, pair):
    me, them = pair
    g3 = await mkgame(session, score=(20, 10), season_type=3, week=1)
    await pick(session, me, g3, 21, 10)                           # postseason: me 1-0
    g2 = await mkgame(session, score=(20, 10), week=2)
    await pick(session, them, g2, 20, 10)                         # exact: them 0-2
    g1 = await mkgame(session, kickoff=NOW - timedelta(hours=1), status="in_progress", week=1)
    await pick(session, me, g1, 21, 10)                           # live, unscored: 0-0
    await mkgame(session, score=(20, 10), week=4)                 # nobody picked: absent
    h = await results.head_to_head(session, clock, me, them, "nfl", 2026)
    assert h.weeks == [
        results.WeekLine(2, 1, 0, 0), results.WeekLine(2, 2, 0, 2), results.WeekLine(3, 1, 1, 0)]
```

Update the three existing equality assertions so they include `weeks`:
- `test_head_to_head_includes_weeks_before_friendship`: expected gains `weeks=[results.WeekLine(2, 1, 1, 0)]`.
- `test_head_to_head_ignores_picks_before_kickoff`: `empty` gains `weeks=[]`; the post-kickoff expected gains `weeks=[results.WeekLine(2, 5, 0, 0)]`.
- `test_head_to_head_skips_weeks_neither_picked`: expected gains `weeks=[results.WeekLine(2, 2, 0, 1), results.WeekLine(2, 3, 0, 0), results.WeekLine(3, 1, 1, 0)]`.

Extend the GraphQL strings so the field is covered end to end: in `H2H` add `weeks { seasonType week pointsFor pointsAgainst }` after `weeksTied`, and in `test_head_to_head_tied_week` assert the returned dict also has `"weeks": [{"seasonType": 2, "week": 1, "pointsFor": 1, "pointsAgainst": 1}]`. In `BOARD` add the same selection and in `test_leaderboard_is_per_opponent` add `assert rows[0]["weeks"] == [{"seasonType": 2, "week": 1, "pointsFor": 1, "pointsAgainst": 0}]`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm api pytest tests/test_results.py -v`
Expected: FAIL with `AttributeError: module 'app.results' has no attribute 'WeekLine'` and the GraphQL tests failing on unknown field `weeks`.

- [ ] **Step 3: Implement in `api/app/results.py`**

Add `@dataclass(frozen=True) class WeekLine` with the four fields above, before `HeadToHead`. Add `weeks: list[WeekLine]` as the last field of `HeadToHead`. In `head_to_head`, build the list from the existing `weeks` dict: `[WeekLine(st, wk, a, b) for (st, wk), (a, b) in sorted(weeks.items())]`, and pass it as the sixth positional argument.

- [ ] **Step 4: Implement in `api/app/gql/schema.py`**

Add `@strawberry.type class WeekLine` (`season_type: int`, `week: int`, `points_for: int`, `points_against: int`) above `HeadToHead` and `weeks: list[WeekLine]` to `HeadToHead`. Add a helper `_h2h_fields(h: results.HeadToHead) -> dict` returning `{**vars(h), "weeks": [WeekLine(**vars(w)) for w in h.weeks]}`; use it in both the `head_to_head` and `leaderboard` resolvers in place of `vars(h)` / `vars(r)`.

- [ ] **Step 5: Run the API suite**

Run: `docker compose run --rm api pytest -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/results.py api/app/gql/schema.py api/tests/test_results.py
git commit -m "feat(api): expose per-week head-to-head lines

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Season stats query

**Files:**
- Modify: `api/app/results.py`
- Modify: `api/app/gql/schema.py` (`Query` class)
- Test: `api/tests/test_results.py`

**Interfaces:**
- Consumes: `scoring.picked_winner(pred, actual)` and `scoring.closeness(pred, actual)` from `app/scoring.py`; `_actual(g)` and `_score(p)` already in `results.py`.
- Produces: `results.SeasonStats(picked: int, winners: int, exact: int)` and `async def season_stats(session: AsyncSession, me: uuid.UUID, league: str, season: int) -> SeasonStats`. GraphQL `seasonStats(league: League!, season: Int!): SeasonStats! { picked winners exact }`.

- [ ] **Step 1: Write the failing tests**

```python
STATS = "{ seasonStats(league:NFL,season:2026){ picked winners exact } }"


async def test_season_stats_count_final_games_only(session, clock, pair):
    me, them = pair
    exact = await mkgame(session, score=(20, 10))
    await pick(session, me, exact, 20, 10)                        # winner + exact
    close = await mkgame(session, score=(20, 10))
    await pick(session, me, close, 21, 10)                        # winner
    wrong = await mkgame(session, score=(20, 10))
    await pick(session, me, wrong, 10, 20)                        # picked, wrong
    tied = await mkgame(session, score=(10, 10))
    await pick(session, me, tied, 10, 7)                          # picked, no winner to call
    live = await mkgame(session, kickoff=NOW - timedelta(hours=1), status="in_progress")
    await pick(session, me, live, 21, 10)                         # not final: ignored
    other = await mkgame(session, score=(20, 10), league="cfb")
    await pick(session, me, other, 20, 10)                        # other league: ignored
    theirs = await mkgame(session, score=(20, 10))
    await pick(session, them, theirs, 20, 10)                     # not my pick: ignored
    assert await results.season_stats(session, me, "nfl", 2026) == results.SeasonStats(picked=4, winners=2, exact=1)


async def test_season_stats_graphql_and_empty(client, now):
    a, _ = await make_user(client, "josh")
    _, r = await gql(client, STATS, headers=a)
    assert r["data"]["seasonStats"] == {"picked": 0, "winners": 0, "exact": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm api pytest tests/test_results.py -k season_stats -v`
Expected: FAIL with `AttributeError: ... has no attribute 'season_stats'` / unknown field `seasonStats`.

- [ ] **Step 3: Implement `season_stats` in `api/app/results.py`**

Add `@dataclass(frozen=True) class SeasonStats` and the function. One query: `select(Game, Pick).join(Pick, (Pick.game_id == Game.id) & (Pick.user_id == me)).where(Game.league == league, Game.season == season, Game.status == "final")`. Count rows where `_actual(g)` is not None as `picked`; `winners` where `picked_winner(score, actual)`; `exact` where `closeness(score, actual) == 0`. No `Clock` parameter: a final game has always kicked off.

- [ ] **Step 4: Implement the resolver in `api/app/gql/schema.py`**

Add `@strawberry.type class SeasonStats` (`picked`, `winners`, `exact`: `int`) and on `Query`:

```python
@strawberry.field
async def season_stats(self, info: Info[Context, None], league: League, season: int) -> SeasonStats:
    ctx = info.context
    return SeasonStats(**vars(await results.season_stats(ctx.session, require_user(ctx), league.value, season)))
```

- [ ] **Step 5: Run the API suite**

Run: `docker compose run --rm api pytest -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/results.py api/app/gql/schema.py api/tests/test_results.py
git commit -m "feat(api): seasonStats query for a user's own pick accuracy

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Standings helpers (web)

**Files:**
- Create: `web/src/lib/standings.ts`
- Test: `web/src/lib/standings.test.ts`

**Interfaces:**
- Produces (all exported from `#lib/standings.js`):

```ts
export type WeekLine = { seasonType: number; week: number; pointsFor: number; pointsAgainst: number };
export type Row = { userId: string; handle: string; pointsFor: number; pointsAgainst: number;
	weeksWon: number; weeksLost: number; weeksTied: number; weeks: WeekLine[] };
export type Stats = { picked: number; winners: number; exact: number };
export type Outcome = 'W' | 'L' | 'T';
export type SortBy = 'weeks' | 'points';

export const CURRENT_WEEK_QUERY: string;   // query($l: League!) { currentWeek(league: $l) { season seasonType week } }
export const BOARD_QUERY: string;          // query($l: League!, $s: Int!) { leaderboard(...) { userId handle pointsFor pointsAgainst weeksWon weeksLost weeksTied weeks { seasonType week pointsFor pointsAgainst } } seasonStats(league: $l, season: $s) { picked winners exact } }
export function outcome(w: WeekLine): Outcome;
export function streak(weeks: WeekLine[]): string;                 // '' | 'W3' | 'L2' | 'T1'
export function thisWeek(weeks: WeekLine[], cur: { seasonType: number; week: number }): WeekLine | undefined;
export function weekLabel(w: { seasonType: number; week: number }): string; // 'W5' | 'P1' | 'Pre1'
export function lead(r: Row): 'lead' | 'trail' | 'even';
export function diff(r: Row): number;                              // pointsFor - pointsAgainst
export function summary(rows: Row[]): { won: number; lost: number; tied: number; pointsFor: number; pointsAgainst: number };
export function sortRows(rows: Row[], by: SortBy): Row[];          // 'weeks' keeps server order; 'points' = diff desc, then handle
export function pct(part: number, whole: number): string;          // '' when whole is 0, else e.g. '67%'
```

- [ ] **Step 1: Write the failing tests** in `web/src/lib/standings.test.ts`

```ts
import { expect, it } from 'vitest';
import { diff, lead, outcome, pct, sortRows, streak, summary, thisWeek, weekLabel, type Row, type WeekLine } from './standings';

const w = (seasonType: number, week: number, pointsFor: number, pointsAgainst: number): WeekLine =>
	({ seasonType, week, pointsFor, pointsAgainst });
const row = (p: Partial<Row>): Row =>
	({ userId: 'u', handle: 'h', pointsFor: 0, pointsAgainst: 0, weeksWon: 0, weeksLost: 0, weeksTied: 0, weeks: [], ...p });

it('derives the week outcome from points', () => {
	expect([outcome(w(2, 1, 3, 1)), outcome(w(2, 1, 1, 3)), outcome(w(2, 1, 0, 0))]).toEqual(['W', 'L', 'T']);
});

it('streak is the trailing run of equal outcomes, blank when empty', () => {
	expect(streak([])).toBe('');
	expect(streak([w(2, 1, 0, 2), w(2, 2, 3, 1), w(2, 3, 2, 1), w(3, 1, 4, 0)])).toBe('W3');
	expect(streak([w(2, 1, 3, 1), w(2, 2, 1, 1)])).toBe('T1');
});

it('thisWeek finds the current week or nothing before kickoff', () => {
	const weeks = [w(2, 8, 5, 2), w(2, 9, 1, 0)];
	expect(thisWeek(weeks, { seasonType: 2, week: 9 })).toEqual(w(2, 9, 1, 0));
	expect(thisWeek(weeks, { seasonType: 2, week: 10 })).toBeUndefined();
	expect(thisWeek(weeks, { seasonType: 3, week: 9 })).toBeUndefined();
});

it('labels weeks by season type', () => {
	expect([weekLabel(w(2, 5, 0, 0)), weekLabel(w(3, 1, 0, 0)), weekLabel(w(1, 1, 0, 0))]).toEqual(['W5', 'P1', 'Pre1']);
});

it('lead compares weeks, then point differential', () => {
	expect(lead(row({ weeksWon: 2, weeksLost: 1 }))).toBe('lead');
	expect(lead(row({ weeksWon: 1, weeksLost: 2, pointsFor: 9 }))).toBe('trail');
	expect(lead(row({ weeksWon: 1, weeksLost: 1, pointsFor: 4, pointsAgainst: 2 }))).toBe('lead');
	expect(lead(row({ weeksWon: 1, weeksLost: 1, pointsFor: 2, pointsAgainst: 4 }))).toBe('trail');
	expect(lead(row({}))).toBe('even');
});

it('summary sums every friend', () => {
	const rows = [row({ weeksWon: 2, weeksTied: 1, pointsFor: 10, pointsAgainst: 4 }), row({ weeksLost: 1, pointsFor: 1, pointsAgainst: 3 })];
	expect(summary(rows)).toEqual({ won: 2, lost: 1, tied: 1, pointsFor: 11, pointsAgainst: 7 });
});

it('sortRows keeps server order for weeks and sorts by differential for points', () => {
	const a = row({ handle: 'a', weeksWon: 3, pointsFor: 5, pointsAgainst: 5 });
	const b = row({ handle: 'b', weeksWon: 1, pointsFor: 9, pointsAgainst: 2 });
	const c = row({ handle: 'c', weeksWon: 1, pointsFor: 9, pointsAgainst: 2 });
	expect(sortRows([a, b, c], 'weeks').map((r) => r.handle)).toEqual(['a', 'b', 'c']);
	expect(sortRows([c, a, b], 'points').map((r) => r.handle)).toEqual(['b', 'c', 'a']);
	expect(diff(b)).toBe(7);
});

it('pct rounds and is blank with nothing decided', () => {
	expect(pct(0, 0)).toBe('');
	expect(pct(2, 3)).toBe('67%');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose run --rm web npm test -- --run src/lib/standings.test.ts`
Expected: FAIL, module `./standings` not found.

- [ ] **Step 3: Implement `web/src/lib/standings.ts`** with the signatures in the Interfaces block. `sortRows` must not mutate its input (`[...rows].sort(...)`). `pct` uses `Math.round(100 * part / whole)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose run --rm web npm test -- --run src/lib/standings.test.ts`
Expected: PASS, 8 tests.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/standings.ts web/src/lib/standings.test.ts
git commit -m "feat(web): standings helpers for the leaderboard page

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Leaderboard page

**Files:**
- Modify: `web/src/routes/leaderboard/+page.svelte` (full rewrite of markup and styles; keep the stale-guard `$effect` shape)
- Test: `api/tests/test_results.py` (exact page query strings)

**Interfaces:**
- Consumes: everything exported from `#lib/standings.js` (Task 3); `gql` from `#lib/gql.js`; `leagueFrom` from `#lib/picks.js`; `LeagueToggle`.
- Produces: the page. No new exports.

- [ ] **Step 1: Write the failing API test for the page's exact queries**

In `api/tests/test_results.py` add the page's two query strings, character for character the same as `CURRENT_WEEK_QUERY` and `BOARD_QUERY` in `standings.ts` (Task 3):

```python
PAGE_CURRENT_WEEK = "query($l: League!) { currentWeek(league: $l) { season seasonType week } }"
PAGE_BOARD = ("query($l: League!, $s: Int!) { leaderboard(league: $l, season: $s) { userId handle pointsFor pointsAgainst "
              "weeksWon weeksLost weeksTied weeks { seasonType week pointsFor pointsAgainst } } "
              "seasonStats(league: $l, season: $s) { picked winners exact } }")


async def test_leaderboard_page_queries(client, session, now):
    a, aid = await make_user(client, "josh")
    session.add(LeagueState(league="nfl", season=2026, season_type=2, week=1))
    await session.commit()
    _, r = await gql(client, PAGE_CURRENT_WEEK, {"l": "NFL"}, a)
    assert r["data"]["currentWeek"] == {"season": 2026, "seasonType": 2, "week": 1}
    _, r = await gql(client, PAGE_BOARD, {"l": "NFL", "s": 2026}, a)
    assert r["data"] == {"leaderboard": [], "seasonStats": {"picked": 0, "winners": 0, "exact": 0}}
```

Import `LeagueState` from `app.models` at the top of the test file.

- [ ] **Step 2: Run it**

Run: `docker compose run --rm api pytest tests/test_results.py -k page_queries -v`
Expected: PASS already (Tasks 1 and 2 built the fields). This test exists to pin the page's strings; it fails later if either side drifts.

- [ ] **Step 3: Rewrite `web/src/routes/leaderboard/+page.svelte`**

Script: import from `#lib/standings.js`; state `rows: Row[] | null`, `stats: Stats | null`, `cur: { seasonType; week } | null`, `sortBy: SortBy = 'weeks'`, `loading`, `error`. The `$effect` runs `CURRENT_WEEK_QUERY`, then (when a week exists) `BOARD_QUERY` with `{ l, s: currentWeek.season }`, applying `rows`, `stats`, `cur` under the existing `stale` guard. `const shown = $derived(rows ? sortRows(rows, sortBy) : [])`.

Markup, top to bottom:
1. `<h1>Leaderboard</h1>`, `<LeagueToggle />`, error line (unchanged).
2. Loading: `<p>Loading…</p>`. No week: `<p>No games loaded yet.</p>`. No rows: `<p>Add friends to see your record against them. <a href="/friends">Find friends</a></p>`.
3. Summary strip (`.board`, black background, gold text, `--display` font, like `.totals` on the matchup page): `{s.won}-{s.lost}-{s.tied}` large, under it `Points {s.pointsFor}–{s.pointsAgainst}`.
4. Stats card (`.card`): "Your season" heading, then `{stats.picked} picked · {stats.winners} winners{pct ? ` (${pct})` : ''} · {stats.exact} exact`. Rendered whenever `stats` exists, even with no friends.
5. Sort toggle: two `<button aria-pressed={sortBy === 'weeks'}>Weeks won</button>` / `points` → "Point diff". Only rendered when there are rows.
6. One `<details class="card" data-lead={lead(r)}>` per row. `<summary>`: handle link `<a href="/matchup/{r.userId}?league={league}">@{r.handle}</a>`, `{r.weeksWon}-{r.weeksLost}-{r.weeksTied}` large, signed diff (`.pos` / `.neg` class; render `+3`, `0`, `-2`), streak chip when non-empty, and a `.this-week` line: with `thisWeek(...)` present → `{weekLabel(w)}: you {w.pointsFor} – {w.pointsAgainst} them`; absent → `{weekLabel(cur)}: not started`. Body: `<ol class="weeks">` of chips `<li class={outcome(w)}>{weekLabel(w)} {outcome(w)} {w.pointsFor}–{w.pointsAgainst}</li>`, or `<p class="meta">No weeks yet.</p>` when empty.

Styles: cards follow `.card` from the matchup page (`--chalk` background, 2px `--line` border, 14px radius). Left border 6px: `[data-lead=lead]` → `--turf`, `trail` → `--red`, `even` → `--line`. `.pos` color `--turf`, `.neg` color `--red`. Chips: `W` gold background, `L` `--red` text on chalk, `T` `--muted`. `summary` has `list-style: none` and `cursor: pointer`, min-height 44px for tap targets. Buttons with `aria-pressed="true"` use the gold fill from `LeagueToggle`.

- [ ] **Step 4: Type-check and run the web suite**

Run: `docker compose run --rm web sh -c "npm run check && npm test -- --run"`
Expected: svelte-check 0 errors; all tests PASS.

- [ ] **Step 5: Look at it**

Run: `docker compose up --build` and open `/leaderboard` for both leagues with a user who has friends and one with none. Confirm: summary strip numbers equal the sum of the cards; a friend's card expands; sort toggle reorders; a week with no kicked-off games shows "not started".

- [ ] **Step 6: Commit**

```bash
git add web/src/routes/leaderboard/+page.svelte api/tests/test_results.py
git commit -m "feat(web): leaderboard summary, stats, live week, history and sort

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
