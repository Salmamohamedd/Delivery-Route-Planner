"""
Delivery Route Planner
-----------------------
Reads a list of delivery requests from a CSV file and organizes them into
delivery trips, respecting vehicle capacity, delivery priority, and area
grouping preferences.

Run:
    python delivery_planner.py sample_deliveries.csv
    python delivery_planner.py sample_deliveries.csv --capacity 12.5
"""

import csv
import argparse
from dataclasses import dataclass
from typing import List


@dataclass
class Delivery:
    id: str
    area: str
    priority: int
    weight: float


def read_deliveries(path: str) -> List[Delivery]:
    """Reads deliveries from a CSV file with columns: id, area, priority, weight_kg."""
    deliveries = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row["id"] or not row["area"] or not row["priority"] or not row["weight_kg"]:
                continue  # skip rows with missing data
            deliveries.append(
                Delivery(
                    id=row["id"].strip(),
                    area=row["area"].strip(),
                    priority=int(row["priority"]),
                    weight=float(row["weight_kg"]),
                )
            )
    return deliveries


def split_valid_and_oversized(deliveries: List[Delivery], capacity: float):
    """Separates deliveries that can never fit in any trip (weight > capacity)
    from ones that can be scheduled normally."""
    valid, oversized = [], []
    for d in deliveries:
        (oversized if d.weight > capacity else valid).append(d)
    return valid, oversized


def group_by_priority(deliveries: List[Delivery]):
    """Groups deliveries into priority tiers, preserving original input order
    within each tier. Lower priority number = more urgent = earlier tier.
    This is a hard ordering rule: nothing below ever reorders across tiers."""
    tiers = {}  # priority -> list of deliveries
    for d in deliveries:
        tiers.setdefault(d.priority, []).append(d)
    return [tiers[p] for p in sorted(tiers)]  # return a list of lists, sorted by priority


def build_trips(deliveries: List[Delivery], capacity: float):
    """
    Builds delivery trips using a tiered Next-Fit strategy with a same-tier
    lookahead:

    - Deliveries are processed strictly in priority-tier order; a trip never
      mixes deliveries from two different priority tiers, so urgent
      deliveries are never delayed for the sake of area grouping.
    - Within a tier, one trip is "open" at a time (Next-Fit). Instead of
      closing the trip the instant the next item in line doesn't fit, we
      scan the rest of the tier for an item that (a) still fits in the
      remaining capacity and (b) shares an area with what's already in the
      trip, preferring that over an item from a new area. If nothing left
      in the tier fits, the trip is closed and a new one is opened.
    """
    tiers = group_by_priority(deliveries)
    print(tiers)  # debug print to show the tiers list
    trips = []

    for tier in tiers:
        remaining = list(tier)
        while remaining:
            trip = []
            trip_weight = 0.0
            trip_areas = set()

            # seed the trip with the next item in tier order
            first = remaining.pop(0)
            trip.append(first)
            trip_weight += first.weight
            trip_areas.add(first.area)

            while True:
                # 1) prefer a same-area item that still fits
                pick_idx = None
                for i, d in enumerate(remaining):
                    if d.area in trip_areas and trip_weight + d.weight <= capacity:
                        pick_idx = i
                        break

                # 2) otherwise fall back to the next item in order that fits
                if pick_idx is None:
                    for i, d in enumerate(remaining):
                        if trip_weight + d.weight <= capacity:
                            pick_idx = i
                            break

                if pick_idx is None:
                    break  # nothing left in this tier fits; trip is done

                d = remaining.pop(pick_idx)
                trip.append(d)
                trip_weight += d.weight
                trip_areas.add(d.area)

            trips.append(trip)

    return trips


def format_report(trips, oversized, capacity) -> str:
    lines = []
    if not trips and not oversized:
        lines.append("No deliveries to process.")
        return "\n".join(lines)

    for i, trip in enumerate(trips, start=1):
        total = sum(d.weight for d in trip)
        util = (total / capacity) * 100
        areas = ", ".join(sorted({d.area for d in trip}))
        lines.append(
            f"Trip {i}  ({total:.1f}/{capacity:.1f} kg, {util:.0f}% utilized, areas: {areas})"
        )
        for d in trip:
            lines.append(f"  - #{d.id} {d.area} priority={d.priority} weight={d.weight}kg")

    if oversized:
        lines.append("\nUnassignable deliveries (exceed vehicle capacity):")
        for d in oversized:
            lines.append(f"  - #{d.id} {d.area} weight={d.weight}kg > {capacity:.1f}kg capacity")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Delivery Route Planner")
    parser.add_argument("input", help="Path to the deliveries CSV file")
    parser.add_argument(
        "--capacity",
        type=float,
        default=10.0,
        help="Vehicle capacity in kg (default: 10.0)",
    )
    args = parser.parse_args()

    deliveries = read_deliveries(args.input)
    valid, oversized = split_valid_and_oversized(deliveries, args.capacity)
    trips = build_trips(valid, args.capacity)
    # print(format_report(trips, oversized, args.capacity))


if __name__ == "__main__":
    main()