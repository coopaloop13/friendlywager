from app.scoring import Score, closeness, game_points, picked_winner, week_result

actual = Score(24, 17)


def test_neither_correct():
    assert game_points(actual, Score(10, 20), Score(3, 14)) == (0, 0)


def test_only_a_correct():
    assert game_points(actual, Score(21, 20), Score(10, 20)) == (1, 0)


def test_only_b_correct_a_no_pick():
    assert game_points(actual, None, Score(30, 3)) == (0, 1)


def test_both_correct_closer_gets_bonus():
    # a: |27-24| + |17-17| = 3; b: |35-24| + |10-17| = 18
    assert game_points(actual, Score(27, 17), Score(35, 10)) == (2, 1)
    assert game_points(actual, Score(35, 10), Score(27, 17)) == (1, 2)


def test_both_correct_equal_closeness_no_bonus():
    # a: 3; b: |21-24| + |17-17| = 3
    assert game_points(actual, Score(27, 17), Score(21, 17)) == (1, 1)


def test_exact_score_bonus_without_opponent_winner():
    assert game_points(actual, Score(24, 17), Score(10, 20)) == (2, 0)
    assert game_points(actual, Score(24, 17), None) == (2, 0)


def test_exact_score_with_both_correct_is_three():
    assert game_points(actual, Score(24, 17), Score(27, 17)) == (3, 1)


def test_both_exact():
    assert game_points(actual, Score(24, 17), Score(24, 17)) == (2, 2)


def test_neither_picked():
    assert game_points(actual, None, None) == (0, 0)


def test_actual_tie_scores_nothing():
    assert game_points(Score(20, 20), Score(21, 20), Score(20, 20)) == (0, 0)


def test_closeness():
    assert closeness(Score(27, 17), actual) == 3


def test_picked_winner_false_when_actual_tie():
    assert picked_winner(Score(21, 20), Score(20, 20)) is False
    assert picked_winner(Score(20, 20), Score(20, 20)) is False


def test_week_result():
    assert week_result(3, 2) == "a"
    assert week_result(1, 4) == "b"
    assert week_result(2, 2) == "tie"
