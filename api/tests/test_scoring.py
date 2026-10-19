from app.scoring import Score, closeness, game_point, picked_winner, week_result

actual = Score(24, 17)


def test_neither_correct():
    assert game_point(actual, Score(10, 20), Score(3, 14)) is None


def test_only_a_correct():
    assert game_point(actual, Score(21, 20), Score(10, 20)) == "a"


def test_only_b_correct_a_no_pick():
    assert game_point(actual, None, Score(30, 3)) == "b"


def test_both_correct_closer_wins():
    # a: |27-24| + |17-17| = 3; b: |35-24| + |10-17| = 18
    assert game_point(actual, Score(27, 17), Score(35, 10)) == "a"


def test_both_correct_equal_is_push():
    # a: 3; b: |21-24| + |17-17| = 3
    assert game_point(actual, Score(27, 17), Score(21, 17)) is None


def test_neither_picked():
    assert game_point(actual, None, None) is None


def test_actual_tie_scores_nothing():
    assert game_point(Score(20, 20), Score(21, 20), Score(20, 21)) is None


def test_closeness():
    assert closeness(Score(27, 17), actual) == 3


def test_picked_winner_false_when_actual_tie():
    assert picked_winner(Score(21, 20), Score(20, 20)) is False
    assert picked_winner(Score(20, 20), Score(20, 20)) is False


def test_week_result():
    assert week_result(3, 2) == "a"
    assert week_result(1, 4) == "b"
    assert week_result(2, 2) == "tie"
