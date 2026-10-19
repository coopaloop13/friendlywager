import json
from pathlib import Path

import pytest

from app.sync.espn import WeekKey, parse_scoreboard

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIX / name).read_text())


def event(state="pre", name="STATUS_SCHEDULED", home_rank=99, away_rank=99, odds=None):
    comp = {
        "competitors": [
            {"homeAway": "home", "score": "21", "team": {"displayName": "Home U", "abbreviation": "HOM"},
             "curatedRank": {"current": home_rank}},
            {"homeAway": "away", "score": "14", "team": {"displayName": "Away U", "abbreviation": "AWY"},
             "curatedRank": {"current": away_rank}},
        ]
    }
    if odds:
        comp["odds"] = [{"details": odds}]
    return {"id": "1", "date": "2026-10-20T00:15Z", "status": {"type": {"state": state, "name": name}},
            "competitions": [comp]}


def payload(*events):
    return {"season": {"year": 2026, "type": 2}, "week": {"number": 6}, "events": list(events)}


def test_parse_nfl_week_key():
    p = load("espn_nfl.json")
    key, _ = parse_scoreboard("nfl", p)
    assert key == WeekKey("nfl", p["season"]["year"], p["season"]["type"], p["week"]["number"])


def test_parse_nfl_all_games():
    p = load("espn_nfl.json")
    _, games = parse_scoreboard("nfl", p)
    assert len(games) == len(p["events"])
    assert games[0].home_abbr and games[0].kickoff_at.tzinfo


def test_parse_unranked_is_none():
    _, games = parse_scoreboard("cfb", load("espn_cfb.json"))
    assert any(g.home_rank is None and g.away_rank is None for g in games)
    assert any((g.home_rank or g.away_rank) for g in games)


def test_parse_spread_and_scores():
    _, [g] = parse_scoreboard("nfl", payload(event("pre", odds="SF -7.5")))
    assert g.spread_text == "SF -7.5" and g.home_score is None and g.away_score is None
    _, [g] = parse_scoreboard("nfl", payload(event("post", "STATUS_FINAL")))
    assert (g.home_score, g.away_score) == (21, 14)


@pytest.mark.parametrize(
    "state,name,expected",
    [
        ("pre", "STATUS_SCHEDULED", "scheduled"),
        ("in", "STATUS_IN_PROGRESS", "in_progress"),
        ("post", "STATUS_FINAL", "final"),
        ("pre", "STATUS_POSTPONED", "postponed"),
        ("post", "STATUS_CANCELED", "canceled"),
    ],
)
def test_parse_status_mapping(state, name, expected):
    _, [g] = parse_scoreboard("nfl", payload(event(state, name)))
    assert g.status == expected
