"""
Tests for the Delivery Route Planner.

Run with:
    pytest test_router.py -v
"""

import io
import textwrap

import pytest

from router import (
    Delivery,
    parse_delivery_row,
    read_deliveries,
    split_valid_and_oversized,
    group_by_priority,
    build_trips,
    format_report,
)

CAPACITY = 10.0


# ---------- parse_delivery_row ----------

def test_parse_valid_row():
    row = {"id": "1", "area": "Maadi", "priority": "2", "weight_kg": "4.5"}
    d = parse_delivery_row(row)
    assert d == Delivery(id="1", area="Maadi", priority=2, weight=4.5)


@pytest.mark.parametrize(
    "row",
    [
        {"id": "", "area": "Maadi", "priority": "2", "weight_kg": "4.5"},       # missing id
        {"id": "1", "area": "", "priority": "2", "weight_kg": "4.5"},           # missing area
        {"id": "1", "area": "Maadi", "priority": "two", "weight_kg": "4.5"},    # bad priority
        {"id": "1", "area": "Maadi", "priority": "2", "weight_kg": "heavy"},    # bad weight
        {"id": "1", "area": "Maadi", "priority": "2", "weight_kg": "-3"},       # non-positive weight
        {"id": "1", "area": "Maadi", "priority": "2", "weight_kg": "0"},        # zero weight
    ],
)
def test_parse_invalid_row_raises(row):
    with pytest.raises(ValueError):
        parse_delivery_row(row)


# ---------- read_deliveries (malformed-row handling) ----------

def test_read_deliveries_skips_malformed_rows(tmp_path):
    csv_content = textwrap.dedent(
        """\
        id,area,priority,weight_kg
        1,Maadi,1,3.0
        2,Zamalek,two,4.0
        3,Nasr City,2,
        4,Heliopolis,1,5.0
        """
    )
    path = tmp_path / "deliveries.csv"
    path.write_text(csv_content)

    deliveries, invalid_rows = read_deliveries(str(path))

    assert [d.id for d in deliveries] == ["1", "4"]
    assert len(invalid_rows) == 2
    # line numbers should point at the malformed CSV rows (header = line 1)
    assert invalid_rows[0][0] == 3
    assert invalid_rows[1][0] == 4


# ---------- split_valid_and_oversized ----------

def test_split_valid_and_oversized():
    items = [
        Delivery("1", "A", 1, 5.0),
        Delivery("2", "B", 1, 12.0),  # exceeds capacity
        Delivery("3", "C", 1, 10.0),  # exactly at capacity -> valid
    ]
    valid, oversized = split_valid_and_oversized(items, CAPACITY)
    assert [d.id for d in valid] == ["1", "3"]
    assert [d.id for d in oversized] == ["2"]


# ---------- group_by_priority ----------

def test_group_by_priority_orders_tiers_and_preserves_order_within_tier():
    items = [
        Delivery("1", "A", 2, 1.0),
        Delivery("2", "B", 1, 1.0),
        Delivery("3", "C", 2, 1.0),
        Delivery("4", "D", 1, 1.0),
    ]
    tiers = group_by_priority(items)
    assert [d.id for d in tiers[0]] == ["2", "4"]  # priority 1, input order preserved
    assert [d.id for d in tiers[1]] == ["1", "3"]  # priority 2, input order preserved


# ---------- build_trips ----------

def test_no_deliveries_produces_no_trips():
    assert build_trips([], CAPACITY) == []


def test_trip_never_exceeds_capacity():
    items = [Delivery(str(i), "A", 1, 3.3) for i in range(10)]
    trips = build_trips(items, CAPACITY)
    for trip in trips:
        assert sum(d.weight for d in trip) <= CAPACITY


def test_every_delivery_appears_in_exactly_one_trip():
    items = [
        Delivery("1", "Nasr City", 2, 4.5),
        Delivery("2", "Maadi", 1, 2.0),
        Delivery("3", "Nasr City", 3, 1.2),
        Delivery("4", "Zamalek", 1, 7.0),
        Delivery("5", "Maadi", 2, 3.5),
    ]
    trips = build_trips(items, CAPACITY)
    all_ids = [d.id for trip in trips for d in trip]
    assert sorted(all_ids) == ["1", "2", "3", "4", "5"]
    assert len(all_ids) == len(set(all_ids))  # no duplicates


def test_higher_priority_tier_never_shares_a_trip_with_lower_priority():
    items = [
        Delivery("1", "A", 1, 2.0),
        Delivery("2", "A", 2, 2.0),
    ]
    trips = build_trips(items, CAPACITY)
    priorities_per_trip = [{d.priority for d in trip} for trip in trips]
    assert all(len(p) == 1 for p in priorities_per_trip)


def test_same_area_items_are_grouped_when_capacity_allows():
    items = [
        Delivery("1", "Maadi", 1, 2.0),
        Delivery("2", "Zamalek", 1, 7.0),
        Delivery("3", "Maadi", 1, 3.0),
    ]
    trips = build_trips(items, CAPACITY)
    maadi_trip = next(t for t in trips if any(d.area == "Maadi" for d in t))
    assert {d.id for d in maadi_trip} == {"1", "3"}


# ---------- format_report ----------

def test_format_report_handles_completely_empty_input():
    assert format_report([], [], [], CAPACITY) == "No deliveries to process."


def test_format_report_lists_oversized_and_invalid_rows():
    oversized = [Delivery("9", "Giza", 1, 15.0)]
    invalid_rows = [(3, "priority 'two' is not a whole number")]
    report = format_report([], oversized, invalid_rows, CAPACITY)
    assert "Unassignable deliveries" in report
    assert "#9" in report
    assert "Skipped malformed rows" in report
    assert "line 3" in report