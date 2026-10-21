"""Offline evaluation helpers. No deserialization, training or auto-promotion."""

import math
from statistics import mean

from pydantic import Field

from .domain import StrictModel


class ModelVersion(StrictModel):
    version: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,80}$")
    status: str = "CANDIDATE"
    dataset_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_version: str = "features-v1"
    metrics: dict[str, float]
    trained: bool = False
    approved: bool = False


def temporal_split(
    timestamps: list[float], horizon: float, embargo: float = 0
) -> dict[str, list[int]]:
    if len(timestamps) < 20 or timestamps != sorted(set(timestamps)):
        raise ValueError("At least 20 strictly increasing timestamps required")
    if horizon < 0 or embargo < 0:
        raise ValueError("Nonnegative horizon and embargo required")
    n = len(timestamps)
    validation_start, test_start = timestamps[int(n * 0.6)], timestamps[int(n * 0.8)]
    train = [i for i, t in enumerate(timestamps) if t + horizon < validation_start - embargo]
    validation = [
        i
        for i, t in enumerate(timestamps)
        if validation_start <= t and t + horizon < test_start - embargo
    ]
    test = [i for i, t in enumerate(timestamps) if t >= test_start]
    if not all([train, validation, test]):
        raise ValueError("Not enough samples after purge/embargo")
    return {"train": train, "validation": validation, "test": test}


def walk_forward(timestamps: list[float], horizon: float, embargo: float, folds: int = 3):
    if folds < 1:
        raise ValueError("Positive folds required")
    return [
        temporal_split(
            timestamps[: int(len(timestamps) * (0.6 + 0.4 * (i + 1) / folds))], horizon, embargo
        )
        for i in range(folds)
    ]


def assert_no_leakage(feature_times: list[float], decision_times: list[float]) -> None:
    if len(feature_times) != len(decision_times) or any(
        a > b for a, b in zip(feature_times, decision_times)
    ):
        raise ValueError("FEATURE_LOOKAHEAD")


def evaluate_probabilities(labels: list[int], probabilities: list[float]) -> dict[str, float]:
    if (
        not labels
        or len(labels) != len(probabilities)
        or any(x not in (0, 1) for x in labels)
        or any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities)
    ):
        raise ValueError("Invalid evaluation data")
    predicted = [p >= 0.5 for p in probabilities]
    tp = sum(p and y == 1 for p, y in zip(predicted, labels))
    positives = sum(predicted)
    calibration = 0.0
    for bin_index in range(10):
        members = [i for i, p in enumerate(probabilities) if min(9, int(p * 10)) == bin_index]
        if members:
            calibration += (
                len(members)
                / len(labels)
                * abs(mean(probabilities[i] for i in members) - mean(labels[i] for i in members))
            )
    prevalence = mean(labels)
    return {
        "precision": tp / positives if positives else 0,
        "recall": tp / sum(labels) if sum(labels) else 0,
        "brier": mean((p - y) ** 2 for p, y in zip(probabilities, labels)),
        "calibration_error_10_bins": calibration,
        "class_prevalence": prevalence,
        "constant_baseline_brier": mean((prevalence - y) ** 2 for y in labels),
    }
