# Performance Optimization

## Diagnosis Checklist

When performance is slow:

- [ ] Does every query include a `TimeQuery()` bound?
- [ ] Is a single file used for years of historical data?
- [ ] Are large datasets being loaded entirely into memory?
- [ ] Are operations in Python loops instead of vectorized pandas/NumPy?
- [ ] Has the use case outgrown a lightweight embedded store?

## Query Performance

### Always use TimeQuery bounds
Unbounded queries scan the entire file:

```python
# ✅ Fast: Bounded to last 30 days
q = (TimeQuery() >= thirty_days_ago) & (TimeQuery() < now) & (TagQuery().device_id == "sensor_1")
results = db.search(q)

# ❌ Slow: Unbounded scan
q = TagQuery().device_id == "sensor_1"  # Checks every point in the file
results = db.search(q)
```

### Use count/contains for existence checks
Avoid fetching full points:

```python
# ✅ Fast
if db.contains(q):
    print("Has data")

# ❌ Slow
if len(db.search(q)) > 0:
    print("Has data")  # Fetches unnecessary data
```

### Sorted parameter
Use `sorted=False` unless you absolutely need chronological order:

```python
# ✅ Fast (unsorted)
results = db.search(q, sorted=False)  # Default behavior

# ❌ Slower
results = db.search(q, sorted=True)  # Sorts before returning
```

## File Size Management

### Problem: Single File Too Large
If a single `.csv` file grows to GB sizes:

**Symptom:** Queries slow down, memory spikes on search operations

**Solution: Time-based partitioning**

```
metrics/
├── metrics_2024-Q1.csv
├── metrics_2024-Q2.csv
├── metrics_2024-Q3.csv
└── metrics_2024-Q4.csv
```

Or by month:
```
metrics/
├── metrics_2024-01.csv
├── metrics_2024-02.csv
├── metrics_2024-03.csv
...
```

**Implementation:**

```python
from datetime import datetime
from tinyflux import TinyFlux

def get_db_for_date(date):
    """Get the appropriate database file for a date."""
    year = date.year
    month = date.month
    filename = f"metrics_{year}-{month:02d}.csv"
    return TinyFlux(filename)

# Write
point_date = point.time
db = get_db_for_date(point_date)
db.insert(point)

# Read (queries typically stay within one month, one query)
start_date = datetime(2025, 1, 1)
db = get_db_for_date(start_date)
results = db.search(...)
```

### Problem: Years of Unpartitioned Data
If you have 5+ years in a single file:

**Solution: Bulk migration to partitioned structure**

```python
def migrate_to_partitioned(old_db_path, output_dir):
    """Read old monolithic database, write to partitioned files."""

    import os
    from collections import defaultdict

    old_db = TinyFlux(old_db_path)
    all_points = old_db.all()  # Load all (be careful with memory!)

    # Group by year-month
    by_month = defaultdict(list)
    for point in all_points:
        key = (point.time.year, point.time.month)
        by_month[key].append(point)

    # Write partitioned files
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for (year, month), points in by_month.items():
        filename = f"{output_dir}/metrics_{year}-{month:02d}.csv"
        new_db = TinyFlux(filename)
        for point in points:
            new_db.insert(point)
```

## Memory Management

### Problem: Large Dataset Load Into Memory
Loading millions of points destroys memory:

```python
# ❌ Bad: All points in memory
all_points = db.search(q)  # Could be millions
df = pd.DataFrame([...])  # Allocates huge DataFrame
```

**Solution: Process in windows**

```python
from datetime import datetime, timezone, timedelta

def process_in_time_windows(db, start, end, window_days=7):
    """Process large date ranges in manageable chunks."""

    current = start
    while current < end:
        window_end = current + timedelta(days=window_days)

        q = (TimeQuery() >= current) & (TimeQuery() < window_end)
        points = db.search(q)

        # Process this window
        df = pd.DataFrame([...])
        result = df["value"].mean()

        current = window_end

        # Window data is garbage collected
```

### Problem: Vectorization in Loops
Loops are slow; use pandas/NumPy:

```python
# ❌ Slow: Loop-based calculation
results = []
for point in points:
    value = point.fields["value"]
    if value > 50:
        results.append(value * 2)

# ✅ Fast: Vectorized pandas
df = pd.DataFrame([...])
results = df[df["value"] > 50]["value"] * 2
```

## Scaling Decisions

### TinyFlux Limits

- **Single writer:** TinyFlux is append-only but not designed for multi-writer concurrency
- **Moderate data:** Works well up to millions of points in a single file; performance degrades with tens of millions
- **Single machine:** Suitable for single-user or small-team tools, not multi-tenant

### When to Stay with TinyFlux
- Prototyping time-series workflows locally
- Small IoT or personal analytics
- Single-user desktop or hobby tools
- Local cache for a centralized database
- Office tools with <10 concurrent users

### When to Migrate

| Scenario | Recommendation |
|----------|-----------------|
| Hundreds of millions of points | Move to **TimescaleDB** (PostgreSQL extension) or **InfluxDB** |
| Multi-tenant access | Move to **TimescaleDB**, **InfluxDB**, or **Prometheus** |
| Sub-second query latency required | Move to **Time Series Database** (InfluxDB, QuestDB, TimescaleDB) |
| Distributed / HA required | Move to **InfluxDB Enterprise** or **TimescaleDB Cloud** |
| Very high ingest rate (millions/sec) | Move to **Kafka** → **InfluxDB** or other dedicated TSDB |
| Complex query language needed | Move to **InfluxQL** / **Flux** (InfluxDB) or **SQL** (TimescaleDB) |

### Hybrid Approach: TinyFlux + TSDB

Keep TinyFlux as a local cache/sandbox while centralizing in a TSDB:

```python
# Local analysis
local_db = TinyFlux("local_metrics.csv")
df = pd.DataFrame([...])
model = train_model(df)

# Persist to central TSDB
from influxdb import InfluxDBClient
client = InfluxDBClient(host='central-server')
for point in points:
    client.write_points([point])  # Write to remote
```

## Profiling Performance Issues

Use Python's `time` module to identify bottlenecks:

```python
import time

start = time.time()
results = db.search(q)
print(f"Query took {time.time() - start:.2f}s")

start = time.time()
df = pd.DataFrame([...])
print(f"DataFrame conversion took {time.time() - start:.2f}s")
```

For detailed profiling:

```python
import cProfile

cProfile.run("""
results = db.search(q)
df = pd.DataFrame([...])
""")
```

## Summary

- **Always bound queries by time**
- **Don't load entire files into memory**—use time windows
- **Partition large files** by year/month
- **Vectorize operations** with pandas/NumPy
- **Monitor file size**—if > 1 GB single file, consider partitioning or migration
- **Plan for scale**—TinyFlux is lightweight, not infinite
