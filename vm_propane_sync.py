## This will downsample the propane_tank_level metric from 1h to 1d and write it to the target VM instance
## This is the daily sync script that will be run as a cron job to keep the data in sync

from datetime import timezone, datetime
import requests
import pandas as pd
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if __name__ == "__main__":

    missing = [v for v in ("SOURCE_URL", "TARGET_URL") if not os.getenv(v)]
    if missing:
        logger.error(f"Required environment variable(s) not set: {', '.join(missing)}")
        exit(1)

    source_url = os.getenv("SOURCE_URL").rstrip("/")
    target_url = os.getenv("TARGET_URL").rstrip("/")

    logger.info(f"Starting sync at {datetime.now(tz=timezone.utc)}")

    try:

        params = {
            "query": "tlast_over_time(propane_tank_level)",
            "step": "30d",
        }

        response = requests.get(f"{target_url}/api/v1/query", params=params)
        if response.status_code != 200:
            raise Exception(f"Error fetching data: {response.text}")

        if not response.json()["data"]["result"]:
            logger.warning(
                f"No data found for chunk {datetime.fromtimestamp(chunk_start)} to {datetime.fromtimestamp(chunk_end)}"
            )

        start_time = int(response.json()["data"]["result"][0]["value"][1]) + 86400
        end_time = (
            datetime.now(tz=timezone.utc)
            .replace(hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
            - 1
        )

        if start_time > end_time:
            logger.info(f"No new data to process")
            exit(0)

        logger.info(
            f"Processing chunk from {datetime.fromtimestamp(start_time,tz=timezone.utc)} to {datetime.fromtimestamp(end_time,tz=timezone.utc)}"
        )

        try:
            params = {
                "query": "zigbee_tank_level",
                "start": start_time,
                "end": end_time,
                "step": "1h",
            }

            response = requests.get(f"{source_url}/api/v1/query_range", params=params)
            if response.status_code != 200:
                raise Exception(f"Error fetching data: {response.text}")

            if not response.json()["data"]["result"]:
                logger.warning(f"No data found")
                exit(1)

            for result in response.json()["data"]["result"]:

                df = pd.DataFrame(
                    {
                        "timestamp": [v[0] for v in result["values"]],
                        "value": [float(v[1]) for v in result["values"]],
                    }
                )

                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s")
                df.set_index("timestamp", inplace=True)

                downsampled = df.resample("1d").mean()
                downsampled["value"] = df["value"].round(1)

                for index, row in downsampled.iterrows():
                    timestamp = int(index.timestamp() * 1e9)
                    value = row["value"]
                    influx_line = f"propane,source=sinope,data_source=zigbee tank_level={value} {timestamp}"
                    logger.info(f"Writing: {influx_line}")
                    try:
                        response = requests.post(
                            f"{target_url}/api/v2/write", data=influx_line
                        )
                        if response.status_code not in [204, 200]:
                            logger.error(f"Error writing data: {response.text}")
                    except Exception as e:
                        logger.error(f"Exception during write: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing: {str(e)}")
            raise e

    except Exception as e:
        logger.error(f"Error processing: {str(e)}")
        raise e
