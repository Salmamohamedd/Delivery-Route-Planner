# Delivery Route Planner

## How to run

Requires Python 3.8+, no external dependencies.

```bash
python router.py sample_deliveries.csv
```

Optional: override the default 10 kg vehicle capacity:

```bash
python router.py sample_deliveries.csv --capacity 12.5
```

Run the test suite (requires `pytest`, `pip install pytest`):

```bash
pytest test_router.py -v
```

### Input format

CSV with a header row and four columns:

```
id,area,priority,weight_kg
1,Nasr City,2,4.5
```

`sample_deliveries.csv` includes the five deliveries given in the assignment
brief, plus three extra rows (#6, #7, #8) added on purpose to exercise the
same-priority and over-capacity edge cases.

## Reasoning

**1. Solution approach, in my own words**

Deliveries are first split into priority tiers (all priority-1s, then all
priority-2s, and so on) — priority is treated as a hard ordering rule, since
the brief says urgent deliveries "should be handled first," while area
grouping is only described as a "where reasonably possible" preference. A
trip is never allowed to mix deliveries from two different priority tiers.

Within a tier, I build trips one at a time (a "Next-Fit" style approach:
one truck route is open at a time). I seed a trip with the next delivery in
line, then repeatedly look for another delivery in the same tier that (a)
still fits under the capacity and (b) shares an area with what's already in
the trip, preferring that over just taking the next item in sequence. Once
nothing left in the tier fits, the trip is closed and a new one starts.
Deliveries heavier than the vehicle capacity are pulled out up front and
reported separately, since they can never be assigned to any trip. Rows
that fail to parse (missing id/area, non-numeric priority or weight,
non-positive weight) are skipped rather than crashing the program, and are
listed separately in the output with the offending line number and reason.

**2. Most difficult part**

Deciding how priority and area grouping should interact. Both are stated as
rules, but with different strength ("should be handled first" vs. "where
reasonably possible"), so treating them as equally weighted would have been
wrong. Scoping the area-grouping lookahead to *within* a priority tier only
was the key decision — it keeps urgency the dominant rule while still
getting real grouping benefit.

**3. Situations where the algorithm may not produce the best possible grouping**

Yes. This is a greedy heuristic, not an optimal bin-packing solver (true
optimal packing is NP-hard), so it can leave capacity on the table. For
example, if the first two items placed in a trip use 9.5 kg of the 10 kg
capacity, a later same-area 1 kg item that would have fit perfectly may end
up alone in its own near-empty trip instead, simply because of the order
items were seeded. The algorithm also only ever looks *forward* within the
remaining list — it never reopens or reshuffles a trip once it's closed.

**4. With 1,000,000 delivery requests, what would become slow or memory-intensive?**

The area lookahead scans the remaining items in a tier with a plain linear
search, so in the worst case (e.g., one dominant priority tier with poor
area diversity) trip-building degrades toward O(n²) for that tier. Loading
the entire CSV into a single in-memory list would also become a real memory
concern at that scale. The fixes would be the same in both cases: index
deliveries by area (e.g., `dict[area] -> list`, or a per-tier priority
queue) so a same-area match is a lookup instead of a scan, and stream the
CSV row-by-row instead of materializing the whole file at once.

**5. What would I improve with another day?**

- Replace the linear area scan with an indexed structure (dict of area ->
  deque) for O(1) same-area lookups instead of O(n) scans.
- Try a proper bin-packing heuristic (e.g., Best-Fit Decreasing, weighted
  by area affinity) and compare trip counts / utilization against the
  current greedy Next-Fit approach.
- Stream large CSV files instead of loading them fully into memory.

## Extensions

**Configurable vehicle capacity.** The brief hardcodes a 10 kg limit, but
real delivery fleets rarely have a single vehicle size. I added a
`--capacity` CLI flag (default 10.0) so the same planner can be reused for
a bike, a small van, or a larger truck without touching the code.

**Malformed-row handling.** Real-world CSV exports aren't always clean.
Rather than letting a bad row (empty field, non-numeric priority/weight,
zero or negative weight) crash the whole run, `parse_delivery_row` validates
each row individually; invalid rows are skipped and reported with their
line number and reason, while the rest of the file is still processed
normally. This extends the same "handle unusual cases gracefully" idea the
assignment already asks for around oversized packages and empty input.

## Tests

`test_router.py` covers each function in isolation plus the
edge cases named in the brief: no deliveries, an oversized package,
multiple deliveries sharing a priority, malformed CSV rows, trips that
would exceed capacity, and the invariant that every valid delivery ends
up in exactly one trip.