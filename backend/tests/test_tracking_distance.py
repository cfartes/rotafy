from datetime import datetime, timedelta, timezone

import pytest
from app.tracking_distance import DistanceCounter

NOW = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)


def point(minute, latitude=0, longitude=0, accuracy=10, session="a"):
    return {
        "captured_at": NOW + timedelta(minutes=minute),
        "latitude": latitude,
        "longitude": longitude,
        "accuracy_m": accuracy,
        "session_id": session,
    }


def calculate(*points):
    counter = DistanceCounter()
    for p in points:
        counter.add(p)
    return counter.summary()


def test_sum_and_zero_are_distinct_from_insufficient_gps():
    assert calculate()["distance_m"] is None
    assert calculate(point(0))["distance_m"] is None
    assert calculate(point(0), point(1))["distance_m"] == 0
    result = calculate(point(0), point(1, 0.01), point(2, 0.02))
    assert result["distance_m"] == pytest.approx(2224, abs=1)
    assert result["valid_intervals"] == 2
    assert not result["partial"]


def test_stationary_noise_does_not_accumulate_or_create_false_time_gaps():
    result = calculate(*(point(i, (i % 3 - 1) * 0.00002) for i in range(120)))
    assert result["distance_m"] == 0
    assert result["gaps"] == 0
    # Retaining the distance anchor still measures a sequence of small real moves.
    result = calculate(*(point(i, i * 0.00005, accuracy=5) for i in range(7)))
    assert result["distance_m"] == pytest.approx(33, abs=1)


def test_spike_is_not_added_on_departure_or_return_and_noise_cannot_hide_a_spike():
    result = calculate(point(0), point(1, 0.005), point(2, 20), point(3, 0.01))
    assert result["distance_m"] == pytest.approx(1112, abs=1)
    assert result["rejected_jumps"] == 1 and result["partial"]
    result = calculate(*(point(i) for i in range(10)), point(10, 0.2), point(11, 0.001))
    assert result["distance_m"] == pytest.approx(111, abs=1)
    assert result["rejected_jumps"] == 1


def test_inaccurate_points_break_the_chain_and_timestamps_do_not_double_count():
    result = calculate(
        point(0), point(1, 0.01, accuracy=101), point(2, 0.02), point(3, 0.03)
    )
    assert result["distance_m"] == pytest.approx(1112, abs=1)
    assert result["rejected_accuracy"] == 1 and result["partial"]
    result = calculate(point(0), point(0), point(0, 0.001), point(1, 0.002))
    assert result["distance_m"] == pytest.approx(222, abs=1)
    assert result["invalid_timestamps"] == 1
    assert (
        calculate(point(0, accuracy=200), point(1, accuracy=300))["distance_m"] is None
    )


def test_gaps_transfers_and_separate_counters_never_join_unknown_distances():
    result = calculate(point(0), point(11, 0.01), point(12, 0.02))
    assert result["distance_m"] == pytest.approx(1112, abs=1)
    assert result["gaps"] == 1 and result["partial"]
    result = calculate(
        point(0),
        point(1, 0.01),
        point(2, 0.02, session="b"),
        point(3, 0.03, session="b"),
    )
    assert result["distance_m"] == pytest.approx(2224, abs=1)
    assert result["session_breaks"] == 1
    assert calculate(point(0, 30), point(1, 30))["distance_m"] == 0


def test_coverage_boundaries_retention_and_date_line():
    counter = DistanceCounter()
    counter.add(point(0))
    counter.add(point(1, 0.01))
    result = counter.summary(NOW - timedelta(minutes=11), NOW + timedelta(minutes=12))
    assert result["gaps"] == 2 and result["partial"]
    assert counter.summary(NOW - timedelta(days=91), cutoff=NOW - timedelta(days=90))[
        "retention_limited"
    ]
    result = calculate(point(0, longitude=179.999), point(1, longitude=-179.999))
    assert result["distance_m"] == pytest.approx(222, abs=1)


def test_near_simultaneous_jitter_within_accuracy_is_not_a_speed_spike():
    first, second = point(0), point(0, 0.00002)
    second["captured_at"] += timedelta(milliseconds=1)
    result = calculate(first, second, point(1))
    assert result["distance_m"] == 0
    assert result["rejected_jumps"] == result["invalid_timestamps"] == 0
