# TinyFlux Data Model Design

## Point Structure

Every record in TinyFlux is a `Point`:

```python
Point(
    time=datetime,        # UTC timestamp, consistent precision
    measurement=str,      # Series type name
    tags=dict[str, str],  # Low-cardinality dimensions
    fields=dict[str, Any] # Metrics to aggregate
)
```

## Design Patterns

### Measurement Naming

Use measurement names to represent **series types**, not entities:

```python
# ✅ Good: Series type is the measurement
Point(time=..., measurement="temperature", tags={"device_id": "sensor_1"}, fields={"value": 22.5})
Point(time=..., measurement="temperature", tags={"device_id": "sensor_2"}, fields={"value": 21.8})

# ❌ Bad: Creating measurements per device
Point(time=..., measurement="device_1_temperature", fields={"value": 22.5})
Point(time=..., measurement="device_2_temperature", fields={"value": 21.8})
```

### Tags (Low-Cardinality Dimensions)

Tags should be strings representing **filtering dimensions** that you query frequently:

- Suitable: device_id, region, host, service, environment
- Not suitable: timestamps, continuous values, frequently-changing attributes

```python
# ✅ Good tags
Point(
    measurement="api_latency",
    tags={"service": "auth", "region": "us-west", "endpoint": "/login"},
    fields={"latency_ms": 125}
)

# ❌ Bad: Continuous value as tag
Point(
    measurement="temperature",
    tags={"temperature_range": "20-30"},  # Don't do this
    fields={"value": 22.5}
)
```

### Fields (Metrics)

Store numeric values and other aggregatable data:

```python
Point(
    measurement="trade",
    tags={"symbol": "AAPL", "exchange": "NASDAQ"},
    fields={
        "price": 150.25,
        "volume": 1_000_000,
        "bid": 150.24,
        "ask": 150.26
    }
)
```

## Timestamp Precision

Normalize all timestamps to UTC with consistent precision:

```python
from datetime import datetime, timezone

# ✅ Seconds precision
point.time = datetime.now(timezone.utc).replace(microsecond=0)

# ✅ Milliseconds precision
point.time = datetime.now(timezone.utc).replace(microsecond=point.time.microsecond // 1000 * 1000)
```

## Append-Only Pattern

TinyFlux is designed for append-only writes. **Never update or delete individual points**. Instead:

### Corrections
Use compensating events:
```python
# Cancel a trade
Point(time=now, measurement="trade", tags={"trade_id": "123"}, fields={"amount": 100})
# Later, correct it
Point(time=later, measurement="trade", tags={"trade_id": "123_correction"}, fields={"amount": 110})
```

### Data Fixes
Rebuild an affected time period offline:
```python
# Delete old file or rename
# Regenerate all points for the affected period
# Re-insert with corrected values
db_new = TinyFlux("metrics_fixed.csv")
for point in corrected_points:
    db_new.insert(point)
# Rename files
```

## Schema Evolution

Schema flexibility is built-in:
- Add new tags or fields to new points; old points keep their structure
- Query only the tags/fields you need
- Avoid adding extremely high-cardinality fields (like UUIDs) to tags

## Partitioning Strategy

For large historical datasets, split by time period to keep files manageable:

```
metrics/
├── metrics_2024-01.csv
├── metrics_2024-02.csv
├── metrics_2024-Q1.csv (or yearly, depending on volume)
└── metrics_2024-Q2.csv
```

Load and query the relevant partition(s) when needed. This avoids single huge files that slow down operations.
