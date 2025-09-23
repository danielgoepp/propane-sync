#!/usr/bin/python3

import requests
import pandas as pd
from datetime import timezone, datetime, timedelta
import logging

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_time_chunks(start_time, end_time, chunk_size_days):
    start_time = datetime.fromisoformat(start_time).timestamp()
    end_time = datetime.fromisoformat(end_time).timestamp()
    logger.info(f"Start time: {start_time}")
    logger.info(f"End time: {end_time}")

    chunk_size = timedelta(days=chunk_size_days).total_seconds() - 1
    current_start = start_time

    while current_start < end_time:
        current_end = min(current_start + chunk_size, end_time)
        yield current_start, current_end
        current_start = current_end + 1


if __name__ == "__main__":

    source_url = "https://vmsingle-lt-prod.goepp.net"
    target_url = "https://vmsingle-lt-prod.goepp.net/api/v2/write"
    metric_query = "propane_tank_level{db='zigbee'}"
    metric_name = "propane"
    start_time = "2024-12-01T00:00:00+00:00"
    end_time = "2025-01-31T23:59:59+00:00"
    source_step = "1h"
    target_step = "1d"
    chunk_size_days = 7

    for chunk_start, chunk_end in get_time_chunks(
        start_time, end_time, chunk_size_days
    ):

        logger.info(
            f"Processing chunk from {datetime.fromtimestamp(chunk_start,tz=timezone.utc)} to {datetime.fromtimestamp(chunk_end,tz=timezone.utc)}"
        )

        try:
            params = {
                "query": metric_query,
                "start": chunk_start,
                "end": chunk_end,
                "step": source_step,
            }

            logger.info(f"Fetching data from {source_url} with params: {params}")
            response = requests.get(f"{source_url}/api/v1/query_range", params=params)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {response.text}")
            logger.info(f"Response: {response.json()}")

            if not response.json()["data"]["result"]:
                logger.warning(
                    f"No data found for chunk {datetime.fromtimestamp(chunk_start)} to {datetime.fromtimestamp(chunk_end)}"
                )
                continue

            for result in response.json()["data"]["result"]:

                df = pd.DataFrame(
                    {
                        "timestamp": [v[0] for v in result["values"]],
                        "value": [float(v[1]) for v in result["values"]],
                    }
                )

                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                df.set_index("timestamp", inplace=True)

                downsampled = df.resample(target_step).mean()
                downsampled["value"] = df["value"].round(1)
                logger.info(f"Downsampled data: {downsampled}")

                for index, row in downsampled.iterrows():
                    timestamp = int(index.timestamp() * 1e9)
                    value = row["value"]
                    influx_line = f"{metric_name},source=sinope,data_source=zigbee tank_level={value} {timestamp}"
                    logger.info(f"Influx line: {influx_line}")

                    try:
                        response = requests.post(target_url, data=influx_line)
                        logger.info(f"Write response status: {response.status_code}")
                        if response.status_code not in [204, 200]:
                            logger.error(f"Error writing data: {response.text}")
                    except Exception as e:
                        logger.error(f"Exception during write: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing chunk: {str(e)}")
            continue
