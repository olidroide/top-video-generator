# Analysis Workflow with Pandas/NumPy

## Data Flow

```
TinyFlux queries → Python list of Point objects
                ↓
Convert to DataFrame (flatten time/tags/fields)
                ↓
Set time as datetime index
                ↓
pandas operations (resample, groupby, rolling, etc.)
                ↓
Analysis/Forecasting/Aggregation
                ↓
(Optional) Write results back as new Point records
```

## Basic Pattern

```python
from datetime import datetime, timezone, timedelta
from tinyflux import TinyFlux, Point, TimeQuery, TagQuery
import pandas as pd

db = TinyFlux("metrics.csv")

# 1. Query a bounded time window
start = datetime(2025, 1, 1, tzinfo=timezone.utc)
end = datetime(2025, 2, 1, tzinfo=timezone.utc)

q_time = (TimeQuery() >= start) & (TimeQuery() < end)
q_device = TagQuery().device_id == "sensor_1"

points = db.search(q_time & q_device)

# 2. Convert to DataFrame
records = []
for point in points:
    records.append({
        "time": point.time,
        "device_id": point.tags["device_id"],
        "region": point.tags.get("region", "unknown"),
        "value": point.fields["value"],
        "humidity": point.fields.get("humidity"),
    })

df = pd.DataFrame(records)

# 3. Prepare for analysis
df["time"] = pd.to_datetime(df["time"], utc=True)
df = df.set_index("time").sort_index()

# 4. Apply operations
hourly_mean = df["value"].resample("1H").mean()
daily_std = df["value"].resample("1D").std()

print(hourly_mean)
```

## Common Operations

### Resampling
Downsample to different frequencies:

```python
df = df.set_index("time")

# Hourly average
hourly_avg = df["value"].resample("1H").mean()

# Daily max
daily_max = df["value"].resample("1D").max()

# Forward-fill missing values
hourly_ffill = df["value"].resample("1H").mean().fillna(method="ffill")
```

### Rolling Windows
Time-based and count-based windows:

```python
# 24-hour rolling average
rolling_24h = df["value"].rolling("24H").mean()

# Last 10 points rolling average
rolling_10 = df["value"].rolling(window=10).mean()
```

### Grouping by Tags
Multi-device aggregation:

```python
# Average per device
avg_by_device = df.groupby("device_id")["value"].mean()

# Hourly average per device
hourly_per_device = df.groupby("device_id")["value"].resample("1H").mean()
```

## Feature Engineering for Forecasting

Create lag features, calendar features, and moving statistics:

```python
def engineer_features(df, measurement_col="value"):
    """Add lag, calendar, and rolling features."""

    df = df.copy()
    df = df.sort_index()

    # Lags
    df["lag_1"] = df[measurement_col].shift(1)
    df["lag_24"] = df[measurement_col].shift(24)  # 24-hour lag
    df["lag_7d"] = df[measurement_col].shift(7 * 24)  # 7-day lag

    # Rolling statistics
    df["rolling_mean_24h"] = df[measurement_col].rolling("24H").mean()
    df["rolling_std_24h"] = df[measurement_col].rolling("24H").std()

    # Calendar features
    df["hour"] = df.index.hour
    df["day_of_week"] = df.index.dayofweek
    df["month"] = df.index.month

    # Drop NaN rows created by lags
    df = df.dropna()

    return df
```

## Detecting Anomalies

Use statistical or ML-based approaches:

```python
def detect_anomalies_statistical(df, measurement_col="value", std_threshold=3):
    """Flag points beyond N standard deviations."""

    mean = df[measurement_col].mean()
    std = df[measurement_col].std()

    df["is_anomaly"] = (df[measurement_col] - mean).abs() > std_threshold * std

    return df[df["is_anomaly"]]

# Usage
anomalies = detect_anomalies_statistical(df, std_threshold=2)
if not anomalies.empty:
    print(f"Found {len(anomalies)} anomalies")
```

## Forecasting (ARIMA / Prophet)

Example with statsmodels ARIMA:

```python
from statsmodels.tsa.arima.model import ARIMA

def forecast_arima(df, measurement_col="value", order=(1, 1, 1), steps=24):
    """Simple ARIMA forecast."""

    # Fit model on historical data
    model = ARIMA(df[measurement_col], order=order)
    fitted = model.fit()

    # Forecast future steps
    forecast = fitted.get_forecast(steps=steps)
    forecast_df = forecast.summary_frame()

    return forecast_df

# Usage
df_clean = df.dropna()
forecast_results = forecast_arima(df_clean, steps=48)  # 48-hour forecast

# Write predictions back to TinyFlux
for idx, row in forecast_results.iterrows():
    prediction_point = Point(
        time=idx,
        measurement="temperature_forecast",
        tags={"device_id": "sensor_1", "model": "arima"},
        fields={"mean": row["mean"], "mean_ci_lower": row["mean_ci_lower"], "mean_ci_upper": row["mean_ci_upper"]}
    )
    db.insert(prediction_point)
```

Example with Prophet:

```python
from prophet import Prophet

def forecast_prophet(df, measurement_col="value", periods=24):
    """Simple Prophet forecast."""

    # Prophet expects columns named 'ds' and 'y'
    prophet_df = df[[measurement_col]].reset_index()
    prophet_df.columns = ["ds", "y"]

    model = Prophet(interval_width=0.95)
    model.fit(prophet_df)

    future = model.make_future_dataframe(periods=periods)
    forecast = model.predict(future)

    return forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']]
```

## Writing Results Back

Persist aggregations or predictions as new measurement types:

```python
def write_hourly_aggregates(db, device_id, hourly_mean):
    """Write hourly aggregates as a new measurement."""

    for timestamp, value in hourly_mean.items():
        agg_point = Point(
            time=timestamp,
            measurement="temperature_hourly_aggregate",
            tags={"device_id": device_id, "aggregation": "mean"},
            fields={"value": value}
        )
        db.insert(agg_point)

# Usage
hourly_mean = df["value"].resample("1H").mean()
write_hourly_aggregates(db, "sensor_1", hourly_mean)
```

## Performance Tips

- **Use bounded queries:** Always include `TimeQuery()` range to avoid scanning entire files
- **Load only relevant windows:** Fetch only the data you need for analysis
- **Vectorize operations:** Use pandas/NumPy instead of Python loops
- **Resample before analysis:** Downsample high-frequency data if full precision isn't needed
- **Memory awareness:** For very large files, process in time chunks:

```python
def process_in_chunks(db, start, end, measurement, chunk_weeks=4):
    """Process large datasets in time chunks."""

    current = start
    while current < end:
        chunk_end = current + timedelta(weeks=chunk_weeks)

        q = (TimeQuery() >= current) & (TimeQuery() < chunk_end) & (MeasurementQuery() == measurement)
        points = db.search(q)

        df = pd.DataFrame([...])  # Convert
        # Process chunk

        current = chunk_end
```
