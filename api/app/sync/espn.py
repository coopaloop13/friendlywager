"""ESPN scoreboard adapter.

Real field paths (verified against live payloads captured 2026-10-19), same as the brief:
  season: payload.season.year / payload.season.type (1 pre, 2 reg, 3 post, 4 off); week: payload.week.number
  event: id, date ("2026-10-20T00:15Z"), status.type.state/name,
         competitions[0].competitors[].{homeAway, score, team.displayName, team.abbreviation, curatedRank.current}
         competitions[0].odds[0].details (optional)
  curatedRank.current is 99 for unranked teams. Offseason payloads may lack `week`.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import httpx


BASE = "https://site.api.espn.com/apis/site/v2/sports/football"
URLS = {
    "nfl": (f"{BASE}/nfl/scoreboard", {}),
    "cfb": (f"{BASE}/college-football/scoreboard", {"groups": 80, "limit": 400}),
}
STATE = {"pre": "scheduled", "in": "in_progress", "post": "final"}
NAME_OVERRIDE = {"STATUS_POSTPONED": "postponed", "STATUS_CANCELED": "canceled"}


@dataclass(frozen=True)
class WeekKey:
    league: str
    season: int
    season_type: int
    week: int


@dataclass(frozen=True)
class GameData:
    league: str
    season: int
    season_type: int
    week: int
    external_id: str
    home_name: str
    home_abbr: str
    away_name: str
    away_abbr: str
    home_rank: int | None
    away_rank: int | None
    kickoff_at: datetime
    status: str
    home_score: int | None
    away_score: int | None
    spread_text: str | None


def _rank(c: dict) -> int | None:
    r = c.get("curatedRank", {}).get("current")
    return r if r is not None and r != 99 else None


def parse_scoreboard(league: str, payload: dict) -> tuple[WeekKey, list[GameData]]:
    key = WeekKey(
        league, payload["season"]["year"], payload["season"]["type"], payload["week"]["number"]
    )
    games = []
    for e in payload["events"]:
        comp = e["competitions"][0]
        side = {c["homeAway"]: c for c in comp["competitors"]}
        t = e["status"]["type"]
        status = NAME_OVERRIDE.get(t["name"]) or STATE[t["state"]]
        scored = status in ("in_progress", "final")
        odds = comp.get("odds") or []
        games.append(
            GameData(
                league=league,
                season=key.season,
                season_type=key.season_type,
                week=key.week,
                external_id=str(e["id"]),
                home_name=side["home"]["team"]["displayName"],
                home_abbr=side["home"]["team"]["abbreviation"],
                away_name=side["away"]["team"]["displayName"],
                away_abbr=side["away"]["team"]["abbreviation"],
                home_rank=_rank(side["home"]),
                away_rank=_rank(side["away"]),
                kickoff_at=datetime.fromisoformat(e["date"]),
                status=status,
                home_score=int(side["home"]["score"]) if scored else None,
                away_score=int(side["away"]["score"]) if scored else None,
                spread_text=odds[0].get("details") if odds else None,
            )
        )
    return key, games


class ScoreboardClient(Protocol):
    async def fetch(self, league: str, key: WeekKey | None = None) -> dict: ...


# ponytail: unofficial ESPN feed behind ScoreboardClient; swap EspnClient for a paid feed if it breaks
class EspnClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def fetch(self, league: str, key: WeekKey | None = None) -> dict:
        url, params = URLS[league]
        if key:
            params = {**params, "seasontype": key.season_type, "week": key.week, "dates": key.season}
        r = await self.http.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def get_scoreboard_client():
    async with httpx.AsyncClient(timeout=15) as http:
        yield EspnClient(http)
