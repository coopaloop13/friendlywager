# Pick'ems: Box Score Picks

Public name: **Pick'ems: Box Score Picks** (short: Pick'ems). The repo, Workers (`fw-*`), cookie and storage keys keep the old working name, Friendly Wager.

## What this is

A small social app for friendly, no-money pick'em between friends on NFL and college football. Each week a user predicts final scores for the week's games. Friends compete 1-on-1 for bragging rights, and the app keeps every week's picks and results for history and a season leaderboard. The first release is a mobile-first web app (SvelteKit, installable as a PWA) used for testing with friends. The backend is a GraphQL API that native iOS/Android apps can use later without changes.

## Core rules

- The spread **never** affects scoring. It is display-only text.
- A pick can't be created, edited or deleted when `now >= game.kickoff_at` (server-enforced, UTC, timezone-aware).
- A friend's pick, or whether one exists, is never returned before that game's kickoff, and never to a non-friend.
- Scoring per game per pair, each player independently: 1 point for picking the actual winner; +1 for an exact score; +1 for lower closeness when both picked the winner (equal closeness → no bonus). Max 3. Closeness = `|pred_home − home| + |pred_away − away|`. Only `final` games score; a tied final scores nothing.
- Week result per pair per league: more points wins; equal is a tie; a week where neither player picked any game in that league is not counted.
- Head-to-head covers the whole season, including weeks before the friendship. The leaderboard is per opponent (your head-to-head record against each friend), never a global ranking.
- Leagues are `nfl` and `cfb`, with separate weeks keyed by `(league, season, season_type, week)`.
- Slate: all NFL games; CFB games where either team's AP rank is ≤ 25 at load time. Once loaded, a game is never removed.
- Handles: stored lowercase, `^[a-z0-9_]{3,20}$`, unique. Emails stored lowercase, unique.
- Sign-in is by a 6-digit code emailed to the address (10 minutes, 5 attempts, one live code per email, stored hashed). A new email picks a handle with the same code. No passwords, no invite code.
- Blocking a user removes any friendship or request between the two and silently drops that user's later requests; they are never told. Sending a request to someone you blocked unblocks them.
- At most 20 unanswered sent friend requests per user; the sender can cancel one. Handles on a short reserved/offensive list are refused at sign-up and rename.
- Abuse limits: the `fw-api` Worker allows 120 `/graphql` requests and 5 sign-in code requests per client IP per minute (429, code `RATE_LIMITED`); the web proxy passes the visitor's IP as `x-real-ip`. The API refuses bodies over 16 KB and more than 10 aliases, and has no introspection in production.
- Invite links: `/add/<handle>`. Logged out, the handle is kept in `sessionStorage` through sign-in; the request is only ever sent by a tap on that page, never by opening the link.
- Public pages (no login): `/`, `/login`, `/terms`, `/privacy`. No money, no prizes; minimum age 13. The contact and report address is `SUPPORT` in `web/src/lib/site.ts`.
- Store apps: the same web app in a Capacitor shell (`web/ios`, `web/android`, app id `cc.sportspicks.app`). Build with `npm run build:app` in `web/` (static build + `cap sync`). In the shell, `web/src/lib/native.ts` sends requests straight to `api.sportspicks.cc` with the session token (kept in device preferences) as a bearer token; the API allows only the shell origins by CORS. The shell shows team abbreviations, never ESPN logos.
- Reminders: the sync cron pushes "picks lock soon" to users with a registered device and an unpicked game kicking off within the hour, at most once per 12 hours per user. `Notifier` is injected like `EmailSender`; until a Firebase project exists it only logs.
- Deleting an account removes the user, their picks and their friendships for good; their friends lose that history too.
- Auth cookie `fw_session`: HttpOnly, SameSite=Lax, Secure when `COOKIE_SECURE=true`. The same JWT is accepted as `Authorization: Bearer <token>`.
- Development principles: **TDD** (a failing test first in every task), **SOLID** (services depend on injected `Clock`, `ScoreboardClient`, `EmailSender`, and `AsyncSession`, never on concrete globals), **ACID** (integrity in Postgres constraints; every multi-step write in one transaction).
- Local lifecycle: `docker compose up --build` and `docker compose down -v`.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Anti-goals

- The spread affecting scoring in any way. The spread is shown for information only.
- A user seeing a friend's pick for a game before that game kicks off.
- A pick being created or changed after kickoff.
- Losing historical picks or results (the one exception: a user deleting their own account).

## Principles

- TDD first: a failing test before any implementation.
- SOLID: inject `Clock`, `ScoreboardClient`, `EmailSender`, `Notifier`, `AsyncSession`; no concrete globals.
- GraphQL: resolvers stay thin (args → one service call → GraphQL type). Each field returns only what its screen needs. Pages query only the fields they render, so responses stay small. Sibling fields share one `AsyncSession` and are serialized by `Context.db_lock` in `DomainErrors.resolve`; never run concurrent session work (e.g. `asyncio.gather`). Each page's exact query string gets a test.
- ACID: integrity lives in Postgres constraints; multi-step writes use one transaction.

## Commands

- `docker compose up --build`
- `docker compose down -v`
- `docker compose run --rm api pytest`
- `docker compose run --rm web npm test`

## Deploy

API: Cloudflare Worker `fw-api` (`deploy/api-worker`, serves `api.sportspicks.cc`) fronting a container built from `api/Dockerfile`; a 5-minute cron calls `/internal/sync` (also keeps the container and the Neon compute from sleeping; a container cold start is ~2 minutes of 500s). Web: Cloudflare Worker `fw-web` with static assets (`web/`, serves `sportspicks.cc`, `API_URL=https://api.sportspicks.cc`). Domain `sportspicks.cc` lives on the user's Cloudflare account.

1. Confirm `npx wrangler whoami` shows the intended Cloudflare account (see your notes; never commit emails or account_id).
2. Create a Neon database. `DATABASE_URL` must be `postgresql+asyncpg://USER:PASS@HOST/DB?ssl=require` (asyncpg scheme, TLS required).
3. Migrations: none to run by hand. The container runs `alembic upgrade head` on every start (optional manual run: `DATABASE_URL=... alembic upgrade head` from `api/`).
4. In `deploy/api-worker`, `npm i`, then `npx wrangler secret put` for each of `DATABASE_URL`, `SESSION_SECRET` (>=32 chars), `SYNC_SECRET` (>=16 chars), `EMAIL_API_TOKEN` (Cloudflare API token with Email Sending permission) and `CLOUDFLARE_ACCOUNT_ID`. Sign-in codes are sent from `signin@sportspicks.cc` through Cloudflare Email Service (`npx wrangler email sending enable sportspicks.cc`); without the two email secrets the code is only written to the container log and nobody can sign in. Generate SESSION_SECRET and SYNC_SECRET with `openssl rand -base64 48`. The first `secret put` before the first deploy will offer to create the Worker; accept.
5. `npx wrangler deploy` in `deploy/api-worker` (needs Docker running; builds the image with the Dockerfile default `INSTALL_DEV=0`). Allow a few minutes for container provisioning.
6. Web: `cd web && npm run build && npx wrangler deploy`. If host Node fails the engine check, build in Docker (`docker compose run --rm --no-deps web npm run build`) and run `npx wrangler deploy` from `web/` on the host; the container has no Cloudflare login.
7. Dry runs: `npx wrangler deploy --dry-run` in either directory.
8. Rotating a secret (`wrangler secret put`): the running container keeps its old env until the image changes; it only picks up the new value on a new image rollout or after it idles out (10m with no requests, but the 5-minute cron usually keeps it awake).

## Pointers

- Runbook (health check, fixing a score): `docs/runbook.md`
- Spec: `docs/superpowers/specs/2026-10-19-friendly-wager-design.md`
- Plan: `docs/superpowers/plans/2026-10-19-friendly-wager.md`
