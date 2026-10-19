# Friendly Wager — Design

## Intent

A small social app for friendly, no-money pick'em between friends on NFL and college football. Each week a user predicts final scores for the week's games. Friends compete 1-on-1 for bragging rights, and the app keeps every week's picks and results for history and a season leaderboard.

The first release is a mobile-first web app (SvelteKit, installable as a PWA) used for testing with friends. The backend is a GraphQL API that native iOS/Android apps can use later without changes.

## Goals

- Load each week's games automatically: **every NFL game** and **every FBS game involving a Top 25 team**.
- Users predict the **final score** of any game they choose. The predicted winner is implied by the score.
- Users add friends by **handle**, and the friend has to **accept the request**.
- Users compare picks against each friend 1-on-1, with a per-week result and a season leaderboard.
- Keep all picks, games and results permanently for historical reporting.

## Non-goals (for now)

- Real money, payments, or any wager amounts.
- Group or league competitions (1-on-1 only).
- Native mobile apps (the API must be ready for them; building them is later work).
- Social login (Google/Apple), email verification, password reset by email. *(My call: password reset needs email sending, so it is deferred. A friend group in testing can live without it.)*
- Push notifications, chat, comments.

## Anti-goals (would make it a failure even if it "works")

- The spread affecting scoring in any way. The spread is shown for information only.
- A user seeing a friend's pick for a game before that game kicks off.
- A pick being created or changed after kickoff.
- Losing historical picks or results.

## Rules (decided by the user)

### Games and weeks
- NFL and college are **separate leagues with their own weeks**. Each league's week follows that league's own schedule (NFL weeks 1–18 plus playoffs; the college weeks the data source uses, plus bowls and playoff).
- Slate per week: all NFL games; all FBS games where at least one team is in the Top 25. *(My call: the **AP Top 25** current when that week's games are loaded. Postseason uses the same rule, so it includes NFL playoffs and bowls/CFP games with a ranked team.)*
- The spread is shown next to each game and may update as it changes. It has **no effect** on picks or scoring.

### Picks
- A pick is a predicted final score for both teams (non-negative integers). The predicted winner is the team with the higher predicted score. *(My call: tied predicted scores are rejected for both leagues, because a pick has to name a winner.)*
- Picks can be created or edited until **that game's kickoff**, then they lock. The lock is enforced by the server using the game's current stored kickoff time.
- Picking is optional per game.
- A user has **one set of picks per week**, and it's used against **all** of their friends.

### Visibility
- At a game's kickoff, each friend's pick for that game becomes visible (only to accepted friends). Before kickoff, a friend's pick is hidden, including whether they have picked at all. *(My call: hiding even the existence of a pick.)*

### Scoring (per game, per friend pair)
Once a game is final:
1. Neither player picked the actual winner (including not picking): **no point**.
2. Exactly one player picked the actual winner: **that player gets 1 point**. This applies even if the other player made no pick.
3. Both picked the actual winner: the player whose prediction is **closer** gets 1 point. Closeness = `|pred_home − actual_home| + |pred_away − actual_away|` *(my call: total error across both scores)*. Equal closeness = **push, no point**.

Games that are cancelled or postponed out of the week score nothing. *(My call.)*

A pair's **week result** per league: whoever has more points that week wins the week; equal points is a tied week. *(My call: a week where neither player made any pick in that league is not counted at all.)*

Head-to-head covers the **whole season**, including weeks before the two users became friends, because those picks were made before kickoff. *(Decided by the user.)*

### Leaderboard *(my call — not specified by the user)*
- **Head-to-head, per friend:** season totals per league. These are points for vs. against, and weeks won/lost/tied.
- **Season leaderboard:** you and all of your friends ranked by **correct-winner picks** for the season, with **average closeness on those picks** as the tiebreaker, per league. This ranks everyone on the same scale no matter how many friends each person has. Head-to-head points can't be compared across people with different friend lists, so they aren't used here.

### Friends and accounts
- Sign up with email, password and a unique handle. *(My call: handles are 3–20 characters from `a-z 0-9 _`, unique ignoring case.)*
- Sign-up requires a single shared **invite code** (server env var), so strangers who find the URL can't create accounts. *(My call.)*
- Friend requests are sent by handle and have to be accepted. Either side can remove the friendship. *(My call: once removed, the other person drops off your friends list and their matchup and head-to-head views are no longer accessible. Picks are never deleted, so if you re-friend, the full record comes back.)*

## Architecture

### Stack (decided by the user)
- **Backend:** Python, GraphQL, PostgreSQL.
- **Frontend:** SvelteKit, mobile-first.
- **Local orchestration:** Docker containers with docker compose (`docker compose up --build` to build/run, `docker compose down -v` to destroy).
- **Hosting:** Cloudflare.

### My calls on the stack
- **API:** FastAPI + Strawberry GraphQL, SQLAlchemy 2 + Alembic migrations, `asyncpg`, argon2 password hashing.
- **Auth:** the API issues a signed session token. Browsers get it as an `HttpOnly`, `Secure`, `SameSite` cookie. Native clients later send the same token as `Authorization: Bearer`. The API accepts both.
- **Same-site routing:** the browser calls the SvelteKit server only, which forwards `/graphql` to the API. This keeps the cookie first-party with or without a custom domain (no cross-site cookie or CORS issues on `*.pages.dev` / `*.workers.dev`). Native clients call the API directly.
- **Data source:** ESPN's public scoreboard JSON (schedules, kickoff times, AP rankings, spreads, live/final scores) for both leagues. It's free and has no key, but it's **unofficial**, so all access goes through one small adapter module that can be swapped for a paid feed (e.g. SportsDataIO) later.
- **Data sync:** an internal `POST /internal/sync` endpoint, protected by a shared secret, pulls current weeks for both leagues and upserts games, kickoff times, spreads, status and final scores. Locally, a tiny compose service calls it on an interval. In production, a Cloudflare Cron Trigger calls it. Cadence is left to the builder (roughly every 10–15 min during game windows).
- **Results:** derived from stored games and picks. The scoring logic is a pure function so it can be tested in isolation. Whether week results are cached or computed on read is left to the builder.
- **Cloudflare hosting:**
  - Frontend: SvelteKit with `@sveltejs/adapter-cloudflare` on Cloudflare Pages.
  - API: the same Docker image used locally, deployed on **Cloudflare Containers** (fronted by a minimal Worker, as Containers require).
  - Database: Cloudflare has no managed Postgres (D1 is SQLite, which would drop the requirement). Production Postgres is **Neon**, a serverless Postgres the API connects to directly. Local dev uses the `postgres` image in compose.
  - The repo includes the deploy config (wrangler files, env templates). The actual deploy happens only when the user asks.

### Data model (outline)
- `users` (id, email unique, handle unique ci, password_hash, created_at)
- `friendships` (requester_id, addressee_id, status: pending/accepted, timestamps; one row per pair)
- `games` (id, league: nfl/cfb, season, season_type, week, external_id unique, home/away team names + abbreviations, home/away AP rank at load, kickoff_at, status, home_score, away_score, spread_text, updated_at)
- `picks` (user_id, game_id, pred_home, pred_away, updated_at; unique per user+game)

### GraphQL surface (outline)
- Auth: `signUp`, `logIn`, `logOut`, `me`.
- Friends: `sendFriendRequest(handle)`, `respondToFriendRequest(id, accept)`, `removeFriend(userId)`, `friends`, `pendingRequests`.
- Games/picks: `currentWeek(league)`, `week(league, season, week)` returning games with my pick; `savePick(gameId, home, away)`, `deletePick(gameId)`. Both are rejected after kickoff.
- Compare: `matchup(friendId, league, season, week)` returns each game with both picks (friend's pick only after kickoff), per-game point, and week totals.
- History: `headToHead(friendId, league, season)`, `leaderboard(league, season)`.

### Frontend screens
Log in / sign up · This week (league toggle, game cards with score inputs, lock indicator, spread) · Friends (search by handle, requests, list) · Matchup vs. a friend (per-game side-by-side, points) · Leaderboard & history (past weeks, head-to-head).

## Development principles (decided by the user)
- A root `CLAUDE.md` records the app's core values and rules (the anti-goals, scoring, lock and visibility rules above) and these principles, so every future session follows them.
- **SOLID** in all application code.
- **TDD**: write a failing test first, then the code that makes it pass.
- **ACID** database design: constraints in Postgres (unique, foreign keys, checks), and multi-step writes in one transaction.

## Testing
- Unit tests for the scoring function (each rule above, including push and no-pick cases), kickoff lock, and pick visibility.
- An API test for the friend request flow and the matchup query.
- Docker compose brings up the full stack locally with one command.

## Left to the builder
Exact sync cadence, caching of results, UI styling, GraphQL naming details, project layout, how the ESPN adapter maps fields.
