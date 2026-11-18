---
name: tinyflux-time-series
description: Best practices for modeling, ingesting, querying, and analyzing time-series data with TinyFlux. Use when designing TinyFlux Point schemas, implementing query patterns, managing retention and partitioning, or integrating TinyFlux with pandas/NumPy for analysis and forecasting workflows.
---

# TinyFlux Time-Series Best Practices

## Overview

TinyFlux is a lightweight, embedded Python time-series store designed for single-user applications and small analytics workflows. This skill provides guidance on schema design, ingestion patterns, querying strategies, and integration with data analysis libraries.

**Position TinyFlux appropriately:** For datasets with tens or hundreds of millions of points, multi-tenant access, or strict latency SLAs, recommend TimescaleDB, InfluxDB, or columnar storage (Parquet + Dask/Spark) instead. TinyFlux can still serve as a local cache or prototyping layer.

## Data Model Essentials

Every TinyFlux record is a `Point` with four components:

- **time** (datetime, UTC) - Canonical timestamp with consistent precision
- **measurement** (str) - Logical series name (like a table)
- **tags** (dict of str→str) - Low-cardinality dimensions for filtering (device_id, region, host)
- **fields** (dict of str→Any) - Metrics to aggregate (temperature, price, latency, etc.)

**Design guidance:**
- Use `measurement` for series type, not per-device (e.g., `"temperature"` for all devices, not `"device_42_temperature"`)
- Keep tags low-cardinality and frequently used for queries
- Normalize timestamps to UTC with consistent precision (seconds or milliseconds)

See [data-model.md](references/data-model.md) for schema design patterns.

## Quick Start: Append-Only Events

TinyFlux is append-only—each observation is a new `Point`:

```python
from datetime import datetime, timezone
from tinyflux import TinyFlux, Point, TimeQuery, TagQuery

db = TinyFlux("metrics.csv")

# Insert a single point
point = Point(
    time=datetime.now(timezone.utc),
    measurement="temperature",
    tags={"device_id": "sensor_1", "region": "us-west"},
    fields={"value": 22.5, "humidity": 45},
)
db.insert(point)

# Query by time and tags
q_time = (TimeQuery() >= start_date) & (TimeQuery() < end_date)
q_device = TagQuery().device_id == "sensor_1"
results = db.search(q_time & q_device)
```

**Key advantage:** `insert()` is append-only with no read-before-write penalty.

For corrections, prefer compensating events or offline rebuilds rather than individual updates/deletes.

## Query Patterns

See [query-patterns.md](references/query-patterns.md) for:
- Combining `TimeQuery`, `MeasurementQuery`, `TagQuery`, `FieldQuery`
- Using `.search()`, `.count()`, `.contains()`, `.get()`
- Performance tips (always bound by time first)

## Analysis with Pandas

Typical workflow:

1. Use `db.search(...)` to fetch a time window as a list of `Point`
2. Convert to a `DataFrame`, expanding time/tags/fields
3. Set `time` as UTC datetime index and apply pandas operations
4. Optionally write aggregates back as new `Point` records

See [pandas-analysis.md](references/pandas-analysis.md) for complete examples and feature engineering patterns.

## Partitioning and Retention

TinyFlux has no built-in partitioning or retention. Implement application-level strategies:

- **Time-based partitioning:** Separate files per month/year if single files grow large (e.g., `metrics_2025-01.csv`)
- **Retention:** Periodic jobs export old data to Parquet/CSV and delete old `.csv` files
- **Hot vs cold:** Keep recent months on fast storage; archive historical data to S3/archive tier

## Forecasting Integration

Forecasting sits above TinyFlux as an analysis layer. Extract data, preprocess in pandas, apply models (ARIMA, Prophet, ML), and write predictions back as new `measurement` records.

See [pandas-analysis.md](references/pandas-analysis.md#forecasting) for patterns.

## Performance Checklist

When TinyFlux feels slow:

- Does every query use a `TimeQuery` filter?
- Is a single file used for years of history? → Split by time period
- Are large datasets loaded entirely into memory? → Use bounded queries
- Has ingest rate outgrown single-machine capacity? → Introduce a message bus (Kafka/Redis) with a single writer, or migrate to a TSDB

See [performance.md](references/performance.md) for detailed guidance.

## Real-Time Considerations

TinyFlux provides no queues, replication, or high availability. For real-time ingest:

- Use a message bus (Kafka/Redis/RabbitMQ) to decouple producers from a single TinyFlux writer
- For critical data, maintain a durable backend (TSDB/warehouse) alongside TinyFlux
- Downsample or reduce frequency if ingest rate exceeds machine capacity

See [real-time.md](references/real-time.md) for architectural patterns.

## Before You Start

Ask:
- Approximate point volume (order of magnitude)?
- Sampling frequency (seconds, minutes, hours)?
- Number of writers/readers concurrently?
- Retention and analysis needs (exploration, reporting, alerts, forecasting)?

**Choose architecture:**
- **TinyFlux-only:** Scripts, desktop tools, hobby IoT, single-user/moderate services
- **TinyFlux + TSDB/warehouse:** Local cache or sandbox with centralized org storage
- **TSDB/warehouse only:** High scale, concurrency, or durability requirements
