# Query Patterns in TinyFlux

## Query Types

TinyFlux offers four composable query types:

| Query Type | Purpose | Example |
|------------|---------|---------|
| `TimeQuery()` | Filter by time range | `TimeQuery() >= start` |
| `MeasurementQuery()` | Filter by measurement | `MeasurementQuery() == "temperature"` |
| `TagQuery()` | Filter by tag values | `TagQuery().region == "us-west"` |
| `FieldQuery()` | Filter by field values | `FieldQuery().value > 42` |

## Combining Queries

Use `&` (and), `|` (or), and `~` (not):

```python
from tinyflux import TinyFlux, TimeQuery, TagQuery, FieldQuery
from datetime import datetime, timezone, timedelta

db = TinyFlux("metrics.csv")

# Fetch last 7 days of temperature readings from device_1
start = datetime.now(timezone.utc) - timedelta(days=7)
end = datetime.now(timezone.utc)

q_time = (TimeQuery() >= start) & (TimeQuery() < end)
q_device = TagQuery().device_id == "device_1"
q_measurement = MeasurementQuery() == "temperature"

results = db.search(q_time & q_device & q_measurement)

# Multiple devices
q_devices = (TagQuery().device_id == "device_1") | (TagQuery().device_id == "device_2")
results = db.search(q_time & q_devices)

# Exclude values
q_exclude_high = ~(FieldQuery().value > 100)
results = db.search(q_time & q_exclude_high)
```

## API Methods

### search()
Get all matching `Point` records:

```python
points = db.search(query, sorted=False)
# sorted=True returns chronologically ordered results (slower for large sets)
```

### count()
Get count without fetching points:

```python
count = db.count(q_time & q_device)  # Fast for existence checks
```

### contains()
Check if any points match:

```python
exists = db.contains(query)  # Returns True/False
```

### get()
Fetch the first matching point:

```python
point = db.get(q_time & q_device)  # Returns Point or None
```

### select()
Project specific attributes (fields/tags) without loading full points:

```python
selected = db.select(["time", "tags.device_id", "fields.value"], q_time & q_device)
```

## Best Practices

### Always bound by time
Every query should include a `TimeQuery` filter to limit the search space:

```python
# ✅ Good: Bounded query
q = (TimeQuery() >= week_ago) & (TimeQuery() < now) & (TagQuery().region == "us-west")
results = db.search(q)

# ❌ Bad: Unbounded (scans entire file)
q = TagQuery().region == "us-west"  # Will check every point!
results = db.search(q)
```

### Use count/contains for checks
Don't fetch points just to check existence:

```python
# ✅ Good
if db.contains(q_time & q_device):
    print("Device has data")

# ❌ Bad
if len(db.search(q_time & q_device)) > 0:
    print("Device has data")  # Fetches all points unnecessarily
```

### Filter by measurement early
Narrow down the measurement type in your query:

```python
q = (TimeQuery() >= start) & (TimeQuery() < end) & (MeasurementQuery() == "temperature")
```

### Batch correlated queries
If retrieving multiple device metrics:

```python
devices = ["sensor_1", "sensor_2", "sensor_3"]
for device_id in devices:
    q = (TimeQuery() >= start) & (TimeQuery() < end) & (TagQuery().device_id == device_id)
    points = db.search(q)
    # Process points
```

## Common Query Patterns

### Last N points for a device

```python
q = (TimeQuery() >= start) & (TimeQuery() < end) & (TagQuery().device_id == "sensor_1")
points = db.search(q, sorted=True)[-10:]  # Last 10 points
```

### Aggregation by tag
Use pandas for aggregation (see pandas-analysis.md):

```python
points = db.search(q_time & MeasurementQuery() == "temperature")
df = pd.DataFrame([{
    "time": p.time,
    "device": p.tags["device_id"],
    "value": p.fields["value"]
} for p in points])
hourly_avg = df.set_index("time").groupby("device")["value"].resample("1H").mean()
```

### Conditional queries
Build queries programmatically:

```python
def build_query(start, end, devices=None, min_value=None):
    q = (TimeQuery() >= start) & (TimeQuery() < end)

    if devices:
        q = q & ((TagQuery().device_id == devices[0]) |
                 (TagQuery().device_id == devices[1]))

    if min_value is not None:
        q = q & (FieldQuery().value >= min_value)

    return q
```
