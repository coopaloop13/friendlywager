# Friendly Wager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first pick'em app where friends predict NFL and Top 25 college football final scores each week and compete 1-on-1 with history and a season leaderboard.

**Architecture:** A Python GraphQL API (FastAPI + Strawberry) on Postgres holds users, friendships, games and picks. Results are computed on read by a pure scoring module. A sync endpoint pulls games from ESPN's public scoreboard. A SvelteKit frontend talks only to its own `/graphql` route, which forwards requests to the API so the session cookie stays first-party. Docker compose runs everything locally. Production is Cloudflare Pages (web), Cloudflare Containers (API), and Neon (Postgres).

**Tech Stack:** Python 3.12, FastAPI, strawberry-graphql, SQLAlchemy 2 (async) + asyncpg, Alembic, argon2-cffi, PyJWT, httpx, pytest + pytest-asyncio. Postgres 16. Node 22, SvelteKit 2 / Svelte 5 / TypeScript, Vitest. Docker compose. Wrangler + `@cloudflare/containers`.

**Spec:** `docs/superpowers/specs/2026-10-19-friendly-wager-design.md`

## Global Constraints

- The spread **never** affects scoring. It is display-only text.
- A pick can't be created, edited or deleted when `now >= game.kickoff_at` (server-enforced, UTC, timezone-aware).
- A friend's pick, or whether one exists, is never returned before that game's kickoff, and never to a non-friend.
- Scoring per game per pair: neither picked the actual winner → no point; only one did → 1 point to them (even if the other didn't pick); both did → lower closeness wins 1 point; equal closeness → push (no point). Closeness = `|pred_home − home| + |pred_away − away|`. Only `final` games score.
- Week result per pair per league: more points wins; equal is a tie; a week where neither player picked any game in that league is not counted.
- Head-to-head covers the whole season, including weeks before the friendship.
- Leagues are `nfl` and `cfb`, with separate weeks keyed by `(league, season, season_type, week)`.
- Slate: all NFL games; CFB games where either team's AP rank is ≤ 25 at load time. Once loaded, a game is never removed.
- Handles: stored lowercase, `^[a-z0-9_]{3,20}$`, unique. Emails stored lowercase, unique.
- Sign-up requires `INVITE_CODE` (env).
- Auth cookie `fw_session`: HttpOnly, SameSite=Lax, Secure when `COOKIE_SECURE=true`. The same JWT is accepted as `Authorization: Bearer <token>`.
- Development principles: **TDD** (a failing test first in every task), **SOLID** (services depend on injected `Clock`, `ScoreboardClient`, and `AsyncSession`, never on concrete globals), **ACID** (integrity in Postgres constraints; every multi-step write in one transaction).
- Local lifecycle: `docker compose up --build` and `docker compose down -v`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **An NFL game ends in a tie.** Nobody picked the winner, so no one gets a point. → test `test_actual_tie_scores_nothing` in Task 3.
2. **A ranked CFB team drops out of the poll mid-week and sync runs again.** The game must stay on the slate and keep updating. → test `test_existing_cfb_game_kept_when_unranked` in Task 6.
3. **The final score is corrected after the game ended.** Results must reflect the correction (they're computed on read). → test `test_sync_updates_final_score` in Task 6 and `test_matchup_reflects_score_correction` in Task 8.
4. **Handles typed with different capitals** ("Josh" vs "josh") in sign-up and friend requests. Lookup must ignore case. → test `test_request_by_handle_is_case_insensitive` in Task 5.
5. **A removed friend's matchup is opened by URL.** It must be rejected. → test `test_matchup_forbidden_after_unfriend` in Task 8.

---

## File Structure

```
CLAUDE.md                       core values, rules, principles
docker-compose.yml              db, api, web, sync
.env.example
db/init.sql                     creates friendly_wager_test
api/
  Dockerfile  pyproject.toml  alembic.ini
  alembic/env.py  alembic/versions/0001_initial.py
  app/
    main.py        create_app(): FastAPI + /health + /graphql + /internal/sync
    config.py      Settings from env
    db.py          engine, sessionmaker, session dependency
    models.py      SQLAlchemy models
    clock.py       Clock protocol, SystemClock
    errors.py      DomainError + subclasses
    scoring.py     pure scoring functions
    auth.py        passwords, tokens, sign_up, log_in
    friends.py     friend request service
    picks.py       pick service + week view
    results.py     matchup, head_to_head, leaderboard
    sync/espn.py   ESPN client + parse_scoreboard
    sync/service.py sync_league
    gql/schema.py  Strawberry types, queries, mutations, context
  tests/
    conftest.py  fixtures/espn_nfl.json  fixtures/espn_cfb.json
    test_health.py test_models.py test_scoring.py test_auth.py test_friends.py
    test_espn.py test_sync.py test_picks.py test_results.py
web/
  Dockerfile  package.json  svelte.config.js  vite.config.ts  wrangler.jsonc
  src/lib/gql.ts  src/lib/picks.ts  src/lib/picks.test.ts
  src/routes/graphql/+server.ts  src/routes/graphql/server.test.ts
  src/routes/+layout.ts  +layout.svelte  +page.svelte (this week)
  src/routes/login/+page.svelte  signup/+page.svelte  friends/+page.svelte
  src/routes/matchup/[friendId]/+page.svelte  leaderboard/+page.svelte
  static/manifest.webmanifest
deploy/api-worker/
  wrangler.jsonc  package.json  src/index.ts
```

---

### Task 1: Repo bootstrap, CLAUDE.md, compose, API health

**Files:**
- Create: `CLAUDE.md`, `.gitignore`, `.env.example`, `docker-compose.yml`, `db/init.sql`
- Create: `api/Dockerfile`, `api/pyproject.toml`, `api/app/__init__.py`, `api/app/main.py`, `api/app/config.py`, `api/app/db.py`, `api/app/clock.py`, `api/app/errors.py`
- Test: `api/tests/conftest.py`, `api/tests/test_health.py`

**Interfaces:**
- Produces:
  - `create_app(settings: Settings | None = None) -> FastAPI`
  - `Settings` (pydantic-settings): `database_url: str`, `session_secret: str`, `invite_code: str`, `sync_secret: str`, `cookie_secure: bool = False`
  - `get_session() -> AsyncIterator[AsyncSession]` (FastAPI dependency) and `sessionmaker` in `app/db.py`
  - `class Clock(Protocol): def now(self) -> datetime` and `SystemClock` (returns `datetime.now(UTC)`)
  - `class DomainError(Exception)` with `code: str`, plus `NotFound`, `Forbidden`, `Conflict`, `Invalid`, `Locked`, `Unauthenticated` (codes `NOT_FOUND`, `FORBIDDEN`, `CONFLICT`, `INVALID`, `LOCKED`, `UNAUTHENTICATED`)
  - Test fixtures in `conftest.py`: `session` (AsyncSession on `TEST_DATABASE_URL`, migrated once with `alembic upgrade head`, all tables truncated after each test), `client` (`httpx.AsyncClient` over `create_app()` with ASGITransport and the test session), and `FixedClock(dt)` for tests

- [ ] **Step 1:** `git init`. Write `CLAUDE.md` with these sections: *What this is* (one paragraph from the spec's Intent). *Core rules* (copy every Global Constraints bullet above verbatim). *Anti-goals* (the spec's four). *Principles*: TDD first, SOLID, ACID. *Commands*: `docker compose up --build`, `docker compose down -v`, `docker compose run --rm api pytest`, `docker compose run --rm web npm test`. *Pointers* to the spec and this plan.
- [ ] **Step 2:** Write `docker-compose.yml`. Services:
  - `db`: `postgres:16`, mounting `db/init.sql` into `/docker-entrypoint-initdb.d/`, with a named volume and a healthcheck.
  - `api`: build `./api` with build arg `INSTALL_DEV=1`, env from `.env`, port 8000, `depends_on` db healthy.
  - `web` and `sync`: added in later tasks.

  Write `.env.example` with `DATABASE_URL=postgresql+asyncpg://fw:fw@db:5432/friendly_wager`, `TEST_DATABASE_URL=…/friendly_wager_test`, `SESSION_SECRET`, `INVITE_CODE`, `SYNC_SECRET`, `COOKIE_SECURE=false`, `API_URL=http://api:8000`. `.gitignore` covers `.env`, `node_modules`, `__pycache__`, `.svelte-kit`, `.wrangler`.
- [ ] **Step 3:** Write the failing test `test_health_ok`: `GET /health` → 200 and `{"ok": True}`.
- [ ] **Step 4:** Run `cp .env.example .env && docker compose run --rm api pytest tests/test_health.py -v`. Expected: FAIL (app missing).
- [ ] **Step 5:** Implement `create_app`, `Settings`, `db.py`, `clock.py`, `errors.py`. The Dockerfile is `python:3.12-slim`, installs `.[dev]` when `INSTALL_DEV=1`, and runs `uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000` after `alembic upgrade head`.
- [ ] **Step 6:** Run the same command again. Expected: PASS.
- [ ] **Step 7:** Commit `chore: bootstrap repo, compose, CLAUDE.md, api health`.

### Task 2: Schema and migration with integrity constraints

**Files:**
- Create: `api/app/models.py`, `api/alembic.ini`, `api/alembic/env.py`, `api/alembic/versions/0001_initial.py`
- Test: `api/tests/test_models.py`

**Interfaces:**
- Produces SQLAlchemy models (UUID primary keys default `gen_random_uuid()`, all timestamps `timestamptz`):
  - `User(id, email, handle, password_hash, created_at)`. Checks: `email = lower(email)`, `handle ~ '^[a-z0-9_]{3,20}$'`. Unique on `email` and on `handle`.
  - `Friendship(id, requester_id, addressee_id, status, created_at, accepted_at)`. `status IN ('pending','accepted')`, `requester_id <> addressee_id`, unique index on `(LEAST(requester_id,addressee_id), GREATEST(...))`.
  - `Game(id, league, season, season_type, week, external_id, home_name, home_abbr, away_name, away_abbr, home_rank, away_rank, kickoff_at, status, home_score, away_score, spread_text, updated_at)`. `league IN ('nfl','cfb')`, `status IN ('scheduled','in_progress','final','postponed','canceled')`, unique `(league, external_id)`, index `(league, season, season_type, week)`.
  - `Pick(user_id, game_id, pred_home, pred_away, updated_at)`. PK `(user_id, game_id)`, checks `pred_home BETWEEN 0 AND 200`, `pred_away BETWEEN 0 AND 200`, `pred_home <> pred_away`.
  - `LeagueState(league PK, season, season_type, week)`: the current week per league, set by sync.

- [ ] **Step 1:** Write failing tests. Each inserts a valid row, then attempts the violating insert and asserts `IntegrityError`:
  - `test_handle_must_be_lowercase_pattern` (`"Josh"` rejected)
  - `test_handle_unique`
  - `test_friendship_pair_unique_either_direction` (A→B then B→A rejected)
  - `test_friendship_not_self`
  - `test_pick_unique_per_user_game`
  - `test_pick_cannot_be_tie` (3–3 rejected)
  - `test_pick_score_range` (−1 and 201 rejected)
- [ ] **Step 2:** Run `docker compose run --rm api pytest tests/test_models.py -v`. Expected: FAIL.
- [ ] **Step 3:** Write the models and a hand-written `0001_initial` migration matching them exactly. `env.py` reads `DATABASE_URL`, and tests override it with `TEST_DATABASE_URL`.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(api): schema with integrity constraints`.

### Task 3: Pure scoring

**Files:**
- Create: `api/app/scoring.py`
- Test: `api/tests/test_scoring.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Score: home: int; away: int`
  - `closeness(pred: Score, actual: Score) -> int`
  - `picked_winner(pred: Score, actual: Score) -> bool` (False when `actual.home == actual.away`)
  - `game_point(actual: Score, a: Score | None, b: Score | None) -> Literal["a", "b"] | None`
  - `week_result(a_points: int, b_points: int) -> Literal["a", "b", "tie"]`

- [ ] **Step 1:** Write failing tests with `actual = Score(24, 17)`:
  - `test_neither_correct`: `game_point(actual, Score(10,20), Score(3,14)) is None`
  - `test_only_a_correct`: `game_point(actual, Score(21,20), Score(10,20)) == "a"`
  - `test_only_b_correct_a_no_pick`: `game_point(actual, None, Score(30,3)) == "b"`
  - `test_both_correct_closer_wins`: `game_point(actual, Score(27,17), Score(35,10)) == "a"` (3 vs 18)
  - `test_both_correct_equal_is_push`: `game_point(actual, Score(27,17), Score(21,17)) is None`
  - `test_neither_picked`: `game_point(actual, None, None) is None`
  - `test_actual_tie_scores_nothing`: `game_point(Score(20,20), Score(21,20), Score(20,21)) is None`
  - `test_closeness`: `closeness(Score(27,17), actual) == 3`
  - `test_week_result`: `(3,2)→"a"`, `(1,4)→"b"`, `(2,2)→"tie"`
- [ ] **Step 2:** Run `docker compose run --rm api pytest tests/test_scoring.py -v`. Expected: FAIL (ImportError).
- [ ] **Step 3:** Implement the functions in `scoring.py`. There's no I/O and no imports beyond the stdlib.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(api): pure scoring rules`.

### Task 4: Auth (sign up, log in, session) + GraphQL skeleton

**Files:**
- Create: `api/app/auth.py`, `api/app/gql/__init__.py`, `api/app/gql/schema.py`
- Modify: `api/app/main.py` (mount `/graphql`)
- Test: `api/tests/test_auth.py`

**Interfaces:**
- Consumes: `User`, `Settings`, `DomainError` subclasses.
- Produces:
  - `hash_password(pw: str) -> str` and `verify_password(hash: str, pw: str) -> bool` (argon2-cffi)
  - `issue_token(user_id: UUID, secret: str) -> str` (HS256, `sub`, `exp` = 30 days) and `read_token(token: str, secret: str) -> UUID | None`
  - `async sign_up(session, *, email, password, handle, invite_code, expected_invite) -> User`. Raises `Forbidden` on a bad invite. Raises `Invalid` when the password is under 8 characters or the handle/email format is bad. Raises `Conflict` when the email or handle is taken. Lowercases email and handle before insert.
  - `async log_in(session, *, email, password) -> User`. Raises `Unauthenticated` on any mismatch, with the same message for an unknown email and a wrong password.
  - GraphQL context `Context(session, clock, settings, user_id: UUID | None, response)`. `user_id` comes from the `fw_session` cookie or the `Authorization: Bearer` header. `require_user(ctx) -> UUID` raises `Unauthenticated`.
  - GraphQL: `type User { id: ID!, handle: String! }`, `type AuthPayload { user: User!, token: String! }`. Mutations `signUp(email, password, handle, inviteCode): AuthPayload!`, `logIn(email, password): AuthPayload!`, `logOut: Boolean!`. Query `me: User`. `DomainError` is mapped to a GraphQL error with `extensions.code`.

- [ ] **Step 1:** Write failing tests (through `client` posting to `/graphql`):
  - `test_sign_up_sets_cookie_and_me_works`
  - `test_sign_up_bad_invite_forbidden` (code `FORBIDDEN`)
  - `test_sign_up_duplicate_handle_any_case_conflict` (`"Josh"` after `"josh"` → `CONFLICT`)
  - `test_log_in_wrong_password_unauthenticated`
  - `test_bearer_token_auth_works`: `me` with `Authorization: Bearer <token>` and no cookie
  - `test_log_out_clears_cookie`
- [ ] **Step 2:** Run `docker compose run --rm api pytest tests/test_auth.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `auth.py` and `gql/schema.py`. Mount it with `strawberry.fastapi.GraphQLRouter(schema, context_getter=...)`. Add a `# ponytail: stateless JWT, no server-side revocation; add a sessions table if logout-everywhere is needed` comment.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(api): email/password auth with cookie + bearer`.

### Task 5: Friends

**Files:**
- Create: `api/app/friends.py`
- Modify: `api/app/gql/schema.py`
- Test: `api/tests/test_friends.py`

**Interfaces:**
- Consumes: `Friendship`, `User`, `require_user`.
- Produces:
  - `async send_request(session, me: UUID, handle: str) -> Friendship`. Lowercases the handle. Raises `NotFound` for an unknown handle, `Invalid` for yourself, `Conflict` if already friends or already requested by me. If the other user already requested me, accepts that request instead (sets status `accepted` and `accepted_at`).
  - `async respond(session, me: UUID, friendship_id: UUID, accept: bool) -> None`. Only the addressee may call it. Accepting sets status/`accepted_at`, and declining deletes the row.
  - `async remove(session, me: UUID, friend_id: UUID) -> None`. Deletes the accepted row.
  - `async are_friends(session, a: UUID, b: UUID) -> bool`
  - `async list_friends(session, me) -> list[User]` and `async pending_incoming(session, me) -> list[tuple[Friendship, User]]`
  - GraphQL: mutations `sendFriendRequest(handle)`, `respondToFriendRequest(id, accept)`, `removeFriend(userId)`. Queries `friends: [User!]!`, `pendingRequests: [FriendRequest!]!` with `FriendRequest { id, from: User! }`.

- [ ] **Step 1:** Write failing tests:
  - `test_request_and_accept_makes_friends`
  - `test_request_by_handle_is_case_insensitive` (`"JOSH"` finds `josh`)
  - `test_cannot_request_self`
  - `test_duplicate_request_conflict`
  - `test_reverse_request_auto_accepts`
  - `test_only_addressee_can_respond` (`FORBIDDEN`)
  - `test_decline_deletes_request`
  - `test_remove_friend`
- [ ] **Step 2:** Run `docker compose run --rm api pytest tests/test_friends.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `friends.py` and the resolvers.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(api): friend requests by handle`.

### Task 6: ESPN adapter and sync

**Files:**
- Create: `api/app/sync/__init__.py`, `api/app/sync/espn.py`, `api/app/sync/service.py`, `api/tests/fixtures/espn_nfl.json`, `api/tests/fixtures/espn_cfb.json`
- Modify: `api/app/main.py` (add `POST /internal/sync`), `docker-compose.yml` (add `sync` service)
- Test: `api/tests/test_espn.py`, `api/tests/test_sync.py`

**Interfaces:**
- Consumes: `Game`, `LeagueState`, `Settings.sync_secret`.
- Produces:
  - `@dataclass(frozen=True) class WeekKey: league: str; season: int; season_type: int; week: int`
  - `@dataclass(frozen=True) class GameData`: every `Game` column except `id`/`updated_at`. `home_score`/`away_score` are `int | None`, and ranks are `int | None` (ESPN's 99 means `None`).
  - `parse_scoreboard(league: str, payload: dict) -> tuple[WeekKey, list[GameData]]`
  - `class ScoreboardClient(Protocol): async def fetch(self, league: str, key: WeekKey | None = None) -> dict` and `EspnClient(httpx.AsyncClient)`
  - `async sync_league(session, client: ScoreboardClient, league: str) -> int` (number of games upserted)
  - `POST /internal/sync` with header `X-Sync-Secret` (checked with `hmac.compare_digest`; 401 otherwise). It syncs `nfl` then `cfb` and returns `{"nfl": n, "cfb": m}`.

ESPN details:
- URLs:
  - `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
  - `https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?groups=80&limit=400`
  - When `key` is given, add `seasontype`, `week` and `dates=<season>`.
- Week key: `payload.season.year`, `payload.season.type`, `payload.week.number`.
- Per event:
  - `id` → `external_id`; `date` → `kickoff_at`.
  - Teams: from `competitions[0].competitors[]` by `homeAway`, using `team.displayName`, `team.abbreviation`, `score` (as int, only when the status is in-progress or final) and `curatedRank.current`.
  - Spread: `competitions[0].odds[0].details` if present.
  - Status: `status.type.state` `pre`→`scheduled`, `in`→`in_progress`, `post`→`final`. Then `status.type.name` `STATUS_POSTPONED`→`postponed` and `STATUS_CANCELED`→`canceled` override.

Sync rule:
- Fetch the current week and upsert by `(league, external_id)`.
- For `cfb`, insert a new game only if either rank ≤ 25, but always update existing games.
- If the previously stored `LeagueState` week differs from the current one, also fetch and update that previous week (this catches late finals at the week rollover).
- Save `LeagueState` in the same transaction.
- Add a `# ponytail: unofficial ESPN feed behind ScoreboardClient; swap EspnClient for a paid feed if it breaks` comment.

- [ ] **Step 1:** Capture the fixtures: `curl -s '<nfl url>' > api/tests/fixtures/espn_nfl.json` and the same for cfb. Check the field paths above against them. If a path differs, use the real path and note it in `espn.py`.
- [ ] **Step 2:** Write failing tests in `test_espn.py`:
  - `test_parse_nfl_week_key` (matches the values in the fixture)
  - `test_parse_nfl_all_games` (count = `len(payload["events"])`)
  - `test_parse_unranked_is_none`
  - `test_parse_status_mapping` (a hand-built minimal event per status)
- [ ] **Step 3:** Write failing tests in `test_sync.py`, using a `FakeClient` that returns hand-built payloads:
  - `test_cfb_unranked_new_game_skipped`
  - `test_existing_cfb_game_kept_when_unranked`
  - `test_sync_updates_final_score` (second payload changes the score → row updated)
  - `test_sync_sets_league_state`
  - `test_rollover_also_updates_previous_week`
  - `test_internal_sync_requires_secret` (401 without header)
- [ ] **Step 4:** Run `docker compose run --rm api pytest tests/test_espn.py tests/test_sync.py -v`. Expected: FAIL.
- [ ] **Step 5:** Implement `espn.py`, `service.py` and the endpoint. Upsert uses `insert(...).on_conflict_do_update`. Add a compose `sync` service: `curlimages/curl`, running `sh -c 'while true; do curl -fsS -X POST -H "X-Sync-Secret: $$SYNC_SECRET" http://api:8000/internal/sync; sleep 900; done'`.
- [ ] **Step 6:** Run the same command. Expected: PASS. Then run `docker compose up -d --build` and `docker compose logs sync`. Expected: a JSON line with non-zero `nfl` during the season.
- [ ] **Step 7:** Commit `feat(api): ESPN sync for NFL and Top 25 CFB`.

### Task 7: Picks and the week view

**Files:**
- Create: `api/app/picks.py`
- Modify: `api/app/gql/schema.py`
- Test: `api/tests/test_picks.py`

**Interfaces:**
- Consumes: `Game`, `Pick`, `LeagueState`, `WeekKey`, `Clock`.
- Produces:
  - `async save_pick(session, clock: Clock, user_id, game_id, home: int, away: int) -> Pick`. Raises `NotFound` for an unknown game, `Locked` when `clock.now() >= game.kickoff_at` or the status isn't `scheduled`, and `Invalid` for a tie or a value outside 0–200 (checked before the DB, so the client gets a clear error). Upserts.
  - `async delete_pick(session, clock, user_id, game_id) -> None`. Same lock rule.
  - `async current_week(session, league) -> WeekKey | None` (from `LeagueState`)
  - `async week_games(session, user_id, key: WeekKey) -> list[tuple[Game, Pick | None]]`, ordered by `kickoff_at`
  - GraphQL:
    - `enum League { NFL, CFB }`
    - `type Week { league, season, seasonType, week, games: [GameView!]! }`
    - `type GameView { id, homeName, homeAbbr, awayName, awayAbbr, homeRank, awayRank, kickoffAt, status, homeScore, awayScore, spread, locked: Boolean!, myPick: PickView }`
    - `type PickView { home: Int!, away: Int! }`
    - Queries `currentWeek(league): Week` and `week(league, season, seasonType, week): Week`
    - Mutations `savePick(gameId, home, away): PickView!` and `deletePick(gameId): Boolean!`
    - `locked` = `clock.now() >= kickoff_at`

- [ ] **Step 1:** Write failing tests (with `FixedClock`):
  - `test_save_pick_before_kickoff`
  - `test_edit_pick_before_kickoff_overwrites`
  - `test_save_pick_at_kickoff_locked` (now == kickoff → `LOCKED`)
  - `test_delete_pick_after_kickoff_locked`
  - `test_tie_pick_invalid`
  - `test_kickoff_moved_later_reopens` (update `kickoff_at` → save succeeds)
  - `test_week_view_shows_my_pick_and_spread`
- [ ] **Step 2:** Run `docker compose run --rm api pytest tests/test_picks.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `picks.py` and the resolvers.
- [ ] **Step 4:** Run the same command. Expected: PASS.
- [ ] **Step 5:** Commit `feat(api): picks with kickoff lock`.

### Task 8: Matchup, head-to-head, leaderboard

**Files:**
- Create: `api/app/results.py`
- Modify: `api/app/gql/schema.py`
- Test: `api/tests/test_results.py`

**Interfaces:**
- Consumes: `scoring.*`, `friends.are_friends`, `WeekKey`, `Clock`.
- Produces:
  - `@dataclass class MatchupGame: game: Game; mine: Score | None; theirs: Score | None; point: Literal["me","them"] | None`. `theirs` is always `None` before kickoff. `point` is set only for `final` games.
  - `@dataclass class Matchup: games: list[MatchupGame]; my_points: int; their_points: int`
  - `async matchup(session, clock, me, friend_id, key: WeekKey) -> Matchup`. Raises `Forbidden` unless `are_friends`.
  - `@dataclass class HeadToHead: points_for: int; points_against: int; weeks_won: int; weeks_lost: int; weeks_tied: int`
  - `async head_to_head(session, me, friend_id, league, season) -> HeadToHead`. Raises `Forbidden` unless friends. Counts all season types for `season`. Only `final` games score. A week is skipped when neither player picked any game in it.
  - `@dataclass class LeaderboardRow: user_id: UUID; handle: str; correct_winners: int; avg_closeness: float | None`
  - `async leaderboard(session, me, league, season) -> list[LeaderboardRow]`. Covers me plus accepted friends, final games only. `avg_closeness` is the mean over correct-winner picks. Sorted by `correct_winners` desc, then `avg_closeness` asc (None last), then `handle`.
  - GraphQL:
    - `matchup(friendId, league, season, seasonType, week): Matchup!`, where `Matchup { games: [MatchupGame!]!, myPoints, theirPoints }` and `MatchupGame { game: GameView!, mine: PickView, theirs: PickView, point: String }`
    - `headToHead(friendId, league, season): HeadToHead!`
    - `leaderboard(league, season): [LeaderboardRow!]!`
  - `# ponytail: computed on read; cache per-week results if leaderboard queries get slow`

- [ ] **Step 1:** Write failing tests:
  - `test_friend_pick_hidden_before_kickoff` (`theirs is None` even though a pick exists)
  - `test_friend_pick_visible_at_kickoff`
  - `test_matchup_points_follow_scoring` (one final game per rule branch, including "they didn't pick, I'm right")
  - `test_matchup_forbidden_for_non_friend`
  - `test_matchup_forbidden_after_unfriend`
  - `test_matchup_reflects_score_correction`
  - `test_head_to_head_includes_weeks_before_friendship` (picks in week 1, friendship accepted "after" → still counted)
  - `test_head_to_head_skips_weeks_neither_picked`
  - `test_head_to_head_tied_week`
  - `test_leaderboard_ranks_by_correct_then_closeness`
  - `test_leaderboard_excludes_non_friends`
- [ ] **Step 2:** Run `docker compose run --rm api pytest tests/test_results.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `results.py`. Load the games and both users' picks with one query per call, then fold them through `scoring.game_point` and `scoring.week_result`.
- [ ] **Step 4:** Run `docker compose run --rm api pytest -v` (full suite). Expected: all PASS.
- [ ] **Step 5:** Commit `feat(api): matchups, head-to-head, leaderboard`.

### Task 9: SvelteKit app shell, proxy, auth screens

**Files:**
- Create: `web/` via `npx sv create web --template minimal --types ts` (add vitest), then `web/Dockerfile`, `web/svelte.config.js` (`@sveltejs/adapter-cloudflare`), `web/src/routes/graphql/+server.ts`, `web/src/lib/gql.ts`, `web/src/routes/+layout.ts`, `web/src/routes/+layout.svelte`, `web/src/routes/login/+page.svelte`, `web/src/routes/signup/+page.svelte`, `web/static/manifest.webmanifest`
- Modify: `docker-compose.yml` (add `web`: build `./web`, `npm run dev -- --host 0.0.0.0`, port 5173, env `API_URL`)
- Test: `web/src/routes/graphql/server.test.ts`

**Interfaces:**
- Consumes: the GraphQL API from Tasks 4–8.
- Produces:
  - `POST /graphql` (SvelteKit endpoint). Forwards the body and the incoming `cookie` header to `${env.API_URL}/graphql`, and returns the API's status, body and every `set-cookie` header unchanged.
  - `gql<T>(query: string, variables?: Record<string, unknown>, f = fetch): Promise<T>`. Posts to `/graphql`. Throws `GqlError` (with `code`) on `errors[0]`.
  - The `+layout.ts` load calls `me`. On no user and a route other than `/login`/`/signup`, it redirects to `/login`.

- [ ] **Step 1:** Write failing tests in `server.test.ts` (mock `fetch`):
  - `forwards cookie to API`
  - `passes set-cookie back`
  - `passes status through`
- [ ] **Step 2:** Run `docker compose run --rm web npm test -- --run`. Expected: FAIL.
- [ ] **Step 3:** Implement the proxy, `gql.ts`, the layout guard, and the login/signup forms. Signup fields are email, password, handle and invite code, and the form shows the `extensions.code` message on error. Add a mobile viewport meta and the manifest link in `app.html`.
- [ ] **Step 4:** Run the same command. Expected: PASS. Then run `docker compose up --build`, open http://localhost:5173, sign up, and confirm you land on `/`.
- [ ] **Step 5:** Commit `feat(web): sveltekit shell, graphql proxy, auth`.

### Task 10: Web screens — week picks, friends, matchup, leaderboard

**Files:**
- Create: `web/src/lib/picks.ts`, `web/src/routes/+page.svelte`, `web/src/routes/friends/+page.svelte`, `web/src/routes/matchup/[friendId]/+page.svelte`, `web/src/routes/leaderboard/+page.svelte`
- Test: `web/src/lib/picks.test.ts`

**Interfaces:**
- Consumes: `gql`. Queries/mutations `currentWeek`, `week`, `savePick`, `deletePick`, `friends`, `pendingRequests`, `sendFriendRequest`, `respondToFriendRequest`, `removeFriend`, `matchup`, `headToHead`, `leaderboard`.
- Produces:
  - `isLocked(kickoffAt: string, now: Date): boolean`
  - `validatePick(home: string, away: string): string | null`. Returns `"Enter both scores"`, `"Scores must be 0–200"` or `"A pick can't be a tie"`, or null.

- [ ] **Step 1:** Write failing tests:
  - `isLocked` at kickoff → true, and one second before → false
  - `validatePick("21","21")` → `"A pick can't be a tie"`
  - `validatePick("","3")` → `"Enter both scores"`
  - `validatePick("201","3")` → `"Scores must be 0–200"`
  - `validatePick("24","17")` → null
- [ ] **Step 2:** Run `docker compose run --rm web npm test -- --run`. Expected: FAIL.
- [ ] **Step 3:** Implement `picks.ts` and the screens:
  - **This week (`/`):** NFL/CFB toggle, and one card per game showing teams, ranks, kickoff in local time, spread, two numeric inputs and a lock badge. Save on blur when valid. Locked games are read-only and show the final score.
  - **Friends:** an add-by-handle form, incoming requests with accept/decline, and the friend list with a remove button and a link to the matchup.
  - **Matchup:** week selector, each game with my pick / their pick ("hidden until kickoff" before lock) / point, week totals, and the head-to-head summary.
  - **Leaderboard:** league toggle, rows showing handle, correct winners and avg closeness.
  - Bottom tab nav for mobile.
- [ ] **Step 4:** Run the same command. Expected: PASS. Then, with `docker compose up --build`, use two browsers: user A requests user B, B accepts, both pick a game, and after kickoff each sees the other's pick on the matchup screen.
- [ ] **Step 5:** Commit `feat(web): picks, friends, matchup, leaderboard screens`.

### Task 11: Cloudflare deploy config

**Files:**
- Create: `deploy/api-worker/wrangler.jsonc`, `deploy/api-worker/package.json`, `deploy/api-worker/src/index.ts`, `web/wrangler.jsonc`
- Modify: `CLAUDE.md` (add a Deploy section), `.env.example` (add the Neon `DATABASE_URL` comment)

**Interfaces:**
- Consumes: `api/Dockerfile` (built with `INSTALL_DEV=0`), `POST /internal/sync`.
- Produces:
  - Worker `fw-api`: `class Api extends Container` (`defaultPort = 8000`, `sleepAfter = "10m"`, `envVars` from Worker secrets `DATABASE_URL`, `SESSION_SECRET`, `INVITE_CODE`, `SYNC_SECRET`, `COOKIE_SECURE=true`). `fetch` forwards every request to one named instance. `scheduled` (cron `*/15 * * * *`) POSTs `/internal/sync` with the secret.
  - Pages project `fw-web` with `API_URL` set to the `fw-api` Worker URL.

- [ ] **Step 1:** Load the `cloudflare` and `wrangler` skills and check the current Containers config shape (`containers`, `durable_objects` binding, `migrations.new_sqlite_classes`) against the docs before writing it.
- [ ] **Step 2:** Write the configs and `src/index.ts`. The Deploy section in `CLAUDE.md`:
  - Create a Neon database.
  - Run `alembic upgrade head` against it.
  - `wrangler secret put` each secret.
  - `wrangler deploy` in `deploy/api-worker`.
  - Deploy `web` to Pages.
- [ ] **Step 3:** Run `cd deploy/api-worker && npm i && npx wrangler deploy --dry-run` and `cd web && npm run build`. Expected: both succeed with no errors. Do **not** run a real deploy unless the user asks.
- [ ] **Step 4:** Commit `chore: cloudflare containers + pages deploy config`.
