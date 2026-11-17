# Runbook

## Is it healthy?

`GET https://api.pickem.cc/health` answers 200 `{"ok": true}` only when Postgres answers and every league's
feed was fetched in the last 30 minutes. Otherwise it answers 503 with `{"ok": false, "stale": ["cfb"]}`.
Point an uptime monitor at it.

The 5-minute cron fails loudly (Worker logs, `sync failed: 502 {"nfl": 12, "cfb": null}`) when a league's fetch or
parse breaks. The other league is still saved. `null` marks the league that failed; the traceback is in the
container log.

## Fix a wrong final score

Results are computed on read from `games`, so correcting the row corrects every matchup, head-to-head and
leaderboard at once. Nothing else needs re-running.

```sql
-- find it
SELECT id, external_id, away_abbr, away_score, home_abbr, home_score, status
FROM games WHERE league = 'nfl' AND season = 2026 AND season_type = 2 AND week = 11;

-- fix it
UPDATE games SET home_score = 27, away_score = 24, status = 'final', updated_at = now()
WHERE id = '<game id>';
```

The next sync overwrites the row with whatever the feed says, so this only sticks once the feed is right or has
stopped returning that week (it returns the current week, plus the previous week once at rollover).
