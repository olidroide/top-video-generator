#!/usr/bin/env python3
"""
TinyFlux time-series example: Basic ingest, query, and analysis workflow.
Demonstrates Point creation, buffered writes, and pandas integration.
"""

from datetime import datetime, timezone, timedelta
from tinyflux import TinyFlux, Point, TimeQuery, TagQuery, MeasurementQuery
import pandas as pd
import random
import tempfile
import os

def main():
    # Create a temporary database for demo
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "demo_metrics.csv")
    
    print(f"📊 TinyFlux Demo: {db_path}\n")
    
    # Initialize database
    db = TinyFlux(db_path)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 1. INGEST: Create sample temperature readings
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("1️⃣  INGESTING data...")
    
    now = datetime.now(timezone.utc)
    devices = ["sensor_1", "sensor_2", "sensor_3"]
    regions = {"sensor_1": "us-west", "sensor_2": "us-east", "sensor_3": "eu-west"}
    
    for hours_ago in range(24, 0, -1):
        timestamp = now - timedelta(hours=hours_ago)
        
        for device_id in devices:
            # Simulate temperature readings with slight variation
            base_temp = 20 + random.gauss(0, 3)
            
            point = Point(
                time=timestamp,
                measurement="temperature",
                tags={
                    "device_id": device_id,
                    "region": regions[device_id]
                },
                fields={
                    "value": base_temp,
                    "humidity": 40 + random.gauss(0, 5)
                }
            )
            db.insert(point)
    
    print(f"   ✅ Inserted {len(devices) * 24} points\n")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 2. QUERY: Retrieve data with filters
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("2️⃣  QUERYING data...")
    
    # Last 12 hours from sensor_1
    start = now - timedelta(hours=12)
    end = now
    
    q_time = (TimeQuery() >= start) & (TimeQuery() < end)
    q_device = TagQuery().device_id == "sensor_1"
    
    results = db.search(q_time & q_device)
    print(f"   ✅ Found {len(results)} points for sensor_1 (last 12h)\n")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 3. ANALYSIS: Convert to DataFrame and analyze
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("3️⃣  ANALYZING with pandas...")
    
    # Convert points to DataFrame
    records = []
    for point in results:
        records.append({
            "time": point.time,
            "device_id": point.tags["device_id"],
            "region": point.tags["region"],
            "temperature": point.fields["value"],
            "humidity": point.fields["humidity"]
        })
    
    df = pd.DataFrame(records)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    df = df.set_index("time").sort_index()
    
    # Calculate statistics
    temp_mean = df["temperature"].mean()
    temp_std = df["temperature"].std()
    temp_min = df["temperature"].min()
    temp_max = df["temperature"].max()
    
    print(f"   Temperature stats:")
    print(f"     Mean: {temp_mean:.1f}°C")
    print(f"     Std:  {temp_std:.1f}°C")
    print(f"     Min:  {temp_min:.1f}°C")
    print(f"     Max:  {temp_max:.1f}°C\n")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 4. AGGREGATION: Hourly resampling
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("4️⃣  RESAMPLING to hourly...")
    
    hourly_mean = df["temperature"].resample("1H").mean()
    hourly_count = df["temperature"].resample("1H").count()
    
    print(f"   Hourly averages:")
    for ts, value in hourly_mean.items():
        print(f"     {ts.strftime('%Y-%m-%d %H:%M')} → {value:.1f}°C (count: {int(hourly_count[ts])})")
    
    print()
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 5. MULTI-DEVICE: Aggregate across all devices
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("5️⃣  MULTI-DEVICE aggregation (all devices, last 6h)...")
    
    start = now - timedelta(hours=6)
    end = now
    
    q_time = (TimeQuery() >= start) & (TimeQuery() < end)
    
    all_points = db.search(q_time)
    
    records = [
        {
            "time": p.time,
            "device_id": p.tags["device_id"],
            "region": p.tags["region"],
            "temperature": p.fields["value"]
        }
        for p in all_points
    ]
    
    df_all = pd.DataFrame(records)
    df_all["time"] = pd.to_datetime(df_all["time"], utc=True)
    df_all = df_all.set_index("time")
    
    # Average by device
    avg_by_device = df_all.groupby("device_id")["temperature"].mean()
    
    print("   Average temperature by device:")
    for device, temp in avg_by_device.items():
        print(f"     {device}: {temp:.1f}°C")
    
    print()
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # 6. CLEANUP
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    print("6️⃣  Demo complete!")
    print(f"   Database preserved at: {db_path}")
    print(f"   (This is a temporary directory; remove manually if desired)\n")

if __name__ == "__main__":
    main()
