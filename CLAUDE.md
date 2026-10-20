# Friendly Wager

## What this is

A small social app for friendly, no-money pick'em between friends on NFL and college football. Each week a user predicts final scores for the week's games. Friends compete 1-on-1 for bragging rights, and the app keeps every week's picks and results for history and a season leaderboard. The first release is a mobile-first web app (SvelteKit, installable as a PWA) used for testing with friends. The backend is a GraphQL API that native iOS/Android apps can use later without changes.

## Core rules

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

## Anti-goals

- The spread affecting scoring in any way. The spread is shown for information only.
- A user seeing a friend's pick for a game before that game kicks off.
- A pick being created or changed after kickoff.
- Losing historical picks or results.

## Principles

- TDD first: a failing test before any implementation.
- SOLID: inject `Clock`, `ScoreboardClient`, `AsyncSession`; no concrete globals.
- ACID: integrity lives in Postgres constraints; multi-step writes use one transaction.

## Commands

- `docker compose up --build`
- `docker compose down -v`
- `docker compose run --rm api pytest`
- `docker compose run --rm web npm test`

## Deploy

API: Cloudflare Worker `fw-api` (`deploy/api-worker`, serves `api.sportspicks.cc`) fronting a container built from `api/Dockerfile`; a 15-minute cron calls `/internal/sync`. Web: Cloudflare Worker `fw-web` with static assets (`web/`, serves `sportspicks.cc`, `API_URL=https://api.sportspicks.cc`). Domain `sportspicks.cc` lives on the user's Cloudflare account.

1. Confirm `npx wrangler whoami` shows the intended Cloudflare account (see your notes; never commit emails or account_id).
2. Create a Neon database. `DATABASE_URL` must be `postgresql+asyncpg://USER:PASS@HOST/DB?ssl=require` (asyncpg scheme, TLS required).
3. Migrations: none to run by hand. The container runs `alembic upgrade head` on every start (optional manual run: `DATABASE_URL=... alembic upgrade head` from `api/`).
4. In `deploy/api-worker`, `npm i`, then `npx wrangler secret put` for each of `DATABASE_URL`, `SESSION_SECRET` (>=32 chars), `INVITE_CODE` (any shared code, 6+ chars), `SYNC_SECRET` (>=16 chars). Generate SESSION_SECRET and SYNC_SECRET with `openssl rand -base64 48`. The first `secret put` before the first deploy will offer to create the Worker; accept.
5. `npx wrangler deploy` in `deploy/api-worker` (needs Docker running; builds the image with the Dockerfile default `INSTALL_DEV=0`). Allow a few minutes for container provisioning.
6. Web: `cd web && npm run build && npx wrangler deploy` (use `docker compose run --rm --no-deps web sh -c "npm run build && npx wrangler deploy"` if host Node fails the engine check).
7. Dry runs: `npx wrangler deploy --dry-run` in either directory.
8. Rotating a secret (`wrangler secret put`): the running container keeps its old env until the image changes; it only picks up the new value on a new image rollout or after it idles out (10m with no requests, but the 15-min cron usually keeps it awake).

## Pointers

- Spec: `docs/superpowers/specs/2026-10-19-friendly-wager-design.md`
- Plan: `docs/superpowers/plans/2026-10-19-friendly-wager.md`
