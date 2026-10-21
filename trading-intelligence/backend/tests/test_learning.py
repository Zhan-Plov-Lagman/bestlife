import pytest

from app.learning import assert_no_leakage, evaluate_probabilities, temporal_split, walk_forward


def test_temporal_embargo_and_walkforward():
    times = list(range(100))
    split = temporal_split(times, 5, 3)
    assert max(split["train"]) + 5 < min(split["validation"]) - 3
    assert max(split["validation"]) + 5 < min(split["test"]) - 3
    assert len(walk_forward(times, 2, 1)) == 3


def test_leakage_and_probability_metrics():
    with pytest.raises(ValueError):
        assert_no_leakage([2], [1])
    metrics = evaluate_probabilities([0, 1], [0.1, 0.9])
    assert metrics["brier"] == pytest.approx(0.01)
    assert metrics["precision"] == 1
    assert metrics["calibration_error_10_bins"] == pytest.approx(0.1)
    with pytest.raises(ValueError):
        evaluate_probabilities([1], [float("nan")])
