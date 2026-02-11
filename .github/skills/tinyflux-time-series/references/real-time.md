# Real-Time Considerations and Architecture

## TinyFlux Limitations

TinyFlux is **single-user**, **append-only**, and **local-only**:

- ❌ No built-in replication or HA
- ❌ No queues or message buffers
- ❌ No distributed writes
- ❌ Single file per database instance
- ✅ Append-only writes (fast)
- ✅ No transaction overhead
- ✅ Suitable for moderate data volumes on single machine

## Real-Time Ingest Patterns

### Pattern 1: Direct Write (Single-Threaded, Low-Volume)

Suitable for: Scripts, hobby IoT, sampling every few seconds

```python
from datetime import datetime, timezone
from tinyflux import TinyFlux, Point

db = TinyFlux("metrics.csv")

# Ingest loop (sampling every 30 seconds)
while True:
    value = read_sensor()
    point = Point(
        time=datetime.now(timezone.utc),
        measurement="temperature",
        tags={"device_id": "sensor_1"},
        fields={"value": value}
    )
    db.insert(point)
    time.sleep(30)
```

**Limits:** Works up to ~100s queries/sec depending on disk I/O. Beyond that, add buffering.

### Pattern 2: Buffered Batch Writes (Higher Volume)

Suitable for: Local aggregation, then periodic flushes

```python
import asyncio
from datetime import datetime, timezone

class TinyFluxBuffer:
    def __init__(self, db_path, batch_size=1000, flush_interval=30):
        self.db_path = db_path
        self.batch = []
        self.batch_size = batch_size
        self.flush_interval = flush_interval
    
    def add_point(self, point):
        self.batch.append(point)
        if len(self.batch) >= self.batch_size:
            self.flush()
    
    def flush(self):
        if not self.batch:
            return
        
        db = TinyFlux(self.db_path)
        for point in self.batch:
            db.insert(point)
        self.batch = []
        print(f"Flushed {len(self.batch)} points")
    
    async def auto_flush_loop(self):
        """Flush every N seconds, even if batch not full."""
        while True:
            await asyncio.sleep(self.flush_interval)
            self.flush()

# Usage
buffer = TinyFluxBuffer("metrics.csv", batch_size=1000, flush_interval=60)

# Ingest loop
for reading in sensor_stream:
    point = Point(time=datetime.now(timezone.utc), ...)
    buffer.add_point(point)
    # Flush happens automatically
```

**Limits:** Reduces disk I/O overhead; suitable for thousands of ingest events/sec on a single machine.

### Pattern 3: Message Bus Decoupling (Multi-Producer)

Suitable for: Multiple data producers, asynchronous ingest

Recommended message buses: **Kafka**, **Redis Streams**, **RabbitMQ**

Architecture:
```
Producers → Message Bus (Kafka/Redis) → Consumer → TinyFlux Writer
```

**Example with Redis Streams:**

```python
import redis
import json
from tinyflux import TinyFlux, Point
from datetime import datetime, timezone

# Producer (e.g., sensor application)
r_producer = redis.Redis(host='redis-server')

def publish_reading(device_id, value):
    msg = {
        "device_id": device_id,
        "value": value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    r_producer.xadd("sensor_readings", msg)

# Consumer (single writer to TinyFlux)
r_consumer = redis.Redis(host='redis-server')
db = TinyFlux("metrics.csv")
consumer_group = "tinyflux_writers"

# Create consumer group if not exists
try:
    r_consumer.xgroup_create("sensor_readings", consumer_group, id='0', mkstream=True)
except:
    pass

def consume_and_write():
    """Single consumer process writing to TinyFlux."""
    while True:
        messages = r_consumer.xreadgroup(
            consumer_group,
            "worker_1",
            {"sensor_readings": ">"},
            count=1000,
            block=0
        )
        
        for stream, stream_messages in messages:
            for msg_id, data in stream_messages:
                point = Point(
                    time=datetime.fromisoformat(data[b"timestamp"].decode()),
                    measurement="temperature",
                    tags={"device_id": data[b"device_id"].decode()},
                    fields={"value": float(data[b"value"])}
                )
                db.insert(point)
                r_consumer.xack("sensor_readings", consumer_group, msg_id)

consume_and_write()
```

**Benefits:**
- Decouples producers from TinyFlux write performance
- Automatic retry/buffering in message bus
- Easy to scale: add more consumers for other databases/processing

### Pattern 4: Data Reduction (High-Frequency Sources)

Suitable for: Sub-second sampling that should be downsampled

```python
def downsample_ingest(high_freq_stream, target_interval_ms=1000):
    """Downsample high-frequency readings."""
    
    last_write = time.time()
    buffer = []
    
    for reading in high_freq_stream:
        buffer.append(reading)
        
        if (time.time() - last_write) * 1000 >= target_interval_ms:
            # Write aggregated point
            avg_value = sum(b["value"] for b in buffer) / len(buffer)
            
            point = Point(
                time=datetime.now(timezone.utc),
                measurement="temperature",
                tags={"device_id": "sensor_1"},
                fields={"value": avg_value, "sample_count": len(buffer)}
            )
            db.insert(point)
            
            buffer = []
            last_write = time.time()
```

## For Critical Data

If data loss or duplication is unacceptable (compliance, billing, etc.):

### Dual Write Pattern

```python
def write_to_tinyflux_and_tsdb(point):
    """Write to both local TinyFlux and central TSDB for durability."""
    
    # Local (fast, for analysis)
    local_db = TinyFlux("local_metrics.csv")
    local_db.insert(point)
    
    # Central (durable backup)
    from influxdb import InfluxDBClient
    client = InfluxDBClient(host='tsdb-server')
    client.write_points([{
        "measurement": point.measurement,
        "tags": point.tags,
        "fields": point.fields,
        "time": point.time
    }])
```

### Dead Letter Queue

```python
def write_with_retry(db, point, max_retries=3):
    """Write with retry; log failures to dead letter queue."""
    
    import json
    
    for attempt in range(max_retries):
        try:
            db.insert(point)
            return True
        except Exception as e:
            if attempt == max_retries - 1:
                # Log to dead letter queue
                with open("dead_letter_queue.jsonl", "a") as f:
                    f.write(json.dumps({
                        "error": str(e),
                        "point": str(point)
                    }) + "\n")
                return False
            time.sleep(2 ** attempt)  # Exponential backoff
```

## Monitoring Real-Time Performance

Track ingest rate and latency:

```python
import time
from collections import deque

class IngestMetrics:
    def __init__(self, window_size=100):
        self.write_times = deque(maxlen=window_size)
        self.start_time = time.time()
    
    def record_write(self, duration_ms):
        self.write_times.append(duration_ms)
    
    def report(self):
        elapsed = time.time() - self.start_time
        avg_latency = sum(self.write_times) / len(self.write_times) if self.write_times else 0
        throughput = len(self.write_times) / elapsed
        
        print(f"Avg latency: {avg_latency:.1f}ms, Throughput: {throughput:.0f} points/sec")

metrics = IngestMetrics()

for point in ingest_stream:
    start = time.time()
    db.insert(point)
    metrics.record_write((time.time() - start) * 1000)
    
    if /* periodic */ :
        metrics.report()
```

## Scaling Decision Tree

```
┌─ How many ingest points/second?
│
├─ <10                  → Direct write pattern
├─ 10–1,000              → Buffered writes
├─ 1,000–10,000         → Message bus + single writer
├─ 10,000+              → Message bus + multiple consumers
│                         OR migrate to dedicated TSDB
```

## Summary

- **TinyFlux is single-writer**: Suitable for one appending process
- **Buffer batches** to reduce I/O overhead
- **Use message bus** (Kafka/Redis) for multi-producer scenarios
- **Downsample** if ingest rate is extremely high
- **Dual-write** (TinyFlux + TSDB) for critical data
- **Monitor latency and throughput** to catch bottlenecks
