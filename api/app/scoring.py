from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Score:
    home: int
    away: int


def closeness(pred: Score, actual: Score) -> int:
    return abs(pred.home - actual.home) + abs(pred.away - actual.away)


def picked_winner(pred: Score, actual: Score) -> bool:
    if actual.home == actual.away:
        return False
    return (pred.home - pred.away) * (actual.home - actual.away) > 0


def game_point(
    actual: Score, a: Score | None, b: Score | None
) -> Literal["a", "b"] | None:
    if actual.home == actual.away:
        return None
    a_ok = a is not None and picked_winner(a, actual)
    b_ok = b is not None and picked_winner(b, actual)
    if a_ok and b_ok:
        ca, cb = closeness(a, actual), closeness(b, actual)
        if ca == cb:
            return None
        return "a" if ca < cb else "b"
    if a_ok:
        return "a"
    if b_ok:
        return "b"
    return None


def week_result(a_points: int, b_points: int) -> Literal["a", "b", "tie"]:
    if a_points == b_points:
        return "tie"
    return "a" if a_points > b_points else "b"
