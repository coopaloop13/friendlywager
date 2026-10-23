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


def game_points(actual: Score, a: Score | None, b: Score | None) -> tuple[int, int]:
    """Points (a, b) for one final game: 1 for the winner, +1 for an exact score,
    +1 for being closer when both picked the winner."""
    if actual.home == actual.away:
        return 0, 0
    ca = closeness(a, actual) if a is not None and picked_winner(a, actual) else None
    cb = closeness(b, actual) if b is not None and picked_winner(b, actual) else None
    pa = 0 if ca is None else 1 + (ca == 0)
    pb = 0 if cb is None else 1 + (cb == 0)
    if ca is not None and cb is not None and ca != cb:
        if ca < cb:
            pa += 1
        else:
            pb += 1
    return pa, pb


def week_result(a_points: int, b_points: int) -> Literal["a", "b", "tie"]:
    if a_points == b_points:
        return "tie"
    return "a" if a_points > b_points else "b"
