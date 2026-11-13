## This will downsample the propane_tank_level metric from 1h to 1d and write it to the target VM instance
## This is the daily sync script that will be run as a cron job to keep the data in sync

import logging
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30  # seconds
SOURCE_QUERY = "zigbee_tank_level"
TARGET_TAGS = "source=sinope,data_source=zigbee"
# Look back 30d for the last target point; this matches the source's 30-day
# retention, so a longer gap couldn't be backfilled from the source anyway.
LAST_POINT_QUERY = (
    'max(tlast_over_time(propane_tank_level{source="sinope",data_source="zigbee"}[30d]))'
)


def downsample_daily(values):
    """Downsample [[unix_ts, "value"], ...] (VM query_range format) to daily means rounded to 0.1.

    Days with no samples are dropped rather than returned as NaN.
    """
    df = pd.DataFrame(
        {
            "timestamp": [v[0] for v in values],
            "value": [float(v[1]) for v in values],
        }
    )

    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
    df.set_index("timestamp", inplace=True)

    downsampled = df.resample("1d").mean().dropna()
    downsampled["value"] = downsampled["value"].round(1)
    return downsampled


def vm_get(url, params):
    """GET a VictoriaMetrics query endpoint and return data.result."""
    response = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()["data"]["result"]


def main():
    load_dotenv()
    logging.basicConfig(level=logging.INFO)

    missing = [v for v in ("SOURCE_URL", "TARGET_URL") if not os.getenv(v)]
    if missing:
        logger.error("Required environment variable(s) not set: %s", ", ".join(missing))
        return 1

    source_url = os.getenv("SOURCE_URL").rstrip("/")
    target_url = os.getenv("TARGET_URL").rstrip("/")

    logger.info("Starting sync at %s", datetime.now(tz=timezone.utc))

    result = vm_get(f"{target_url}/api/v1/query", {"query": LAST_POINT_QUERY})
    if not result:
        logger.error(
            "No data found in target within the last 30 days; cannot determine sync start time"
        )
        return 1

    start_time = int(float(result[0]["value"][1])) + 86400
    end_time = (
        int(
            datetime.now(tz=timezone.utc)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        - 1
    )

    if start_time > end_time:
        logger.info("No new data to process")
        return 0

    logger.info(
        "Processing from %s to %s",
        datetime.fromtimestamp(start_time, tz=timezone.utc),
        datetime.fromtimestamp(end_time, tz=timezone.utc),
    )

    result = vm_get(
        f"{source_url}/api/v1/query_range",
        {"query": SOURCE_QUERY, "start": start_time, "end": end_time, "step": "1h"},
    )
    if not result:
        logger.error("No source data found for the sync window")
        return 1
    if len(result) > 1:
        labels = [r["metric"] for r in result]
        logger.error("Expected one source series, got %d: %s", len(result), labels)
        return 1

    downsampled = downsample_daily(result[0]["values"])
    if downsampled.empty:
        logger.error("Source data produced no daily values")
        return 1

    lines = [
        f"propane,{TARGET_TAGS} tank_level={row['value']} {index.value}"
        for index, row in downsampled.iterrows()
    ]
    for line in lines:
        logger.info("Writing: %s", line)

    response = requests.post(
        f"{target_url}/api/v2/write", data="\n".join(lines), timeout=REQUEST_TIMEOUT
    )
    response.raise_for_status()

    logger.info("Wrote %d point(s)", len(lines))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        logger.exception("Sync failed")
        sys.exit(1)
