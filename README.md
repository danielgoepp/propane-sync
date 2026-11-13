# propane-sync

Daily job that copies propane tank level readings from a short-term VictoriaMetrics instance into a long-term one, downsampled from hourly to daily values.

```
Source VM ──(query_range, 1h step)──▶ pandas resample to 1d ──(InfluxDB line protocol)──▶ Target VM
```

## How it works

Each run of [vm_propane_sync.py](vm_propane_sync.py):

1. Asks the target for the timestamp of the most recent `propane_tank_level` sample (`tlast_over_time(propane_tank_level)`, 30-day lookback).
2. Sets the sync window from the day after that sample up to the end of yesterday (UTC, 23:59:59). If the window is empty, it exits with nothing to do.
3. Fetches `zigbee_tank_level` from the source at a 1-hour step for that window.
4. Resamples each series to the mean of each UTC day, rounded to one decimal place.
5. Writes each daily point to the target's `/api/v2/write` endpoint as:

   ```
   propane,source=sinope,data_source=zigbee tank_level=<value> <timestamp_ns>
   ```

   VictoriaMetrics stores this as the metric `propane_tank_level{source="sinope",data_source="zigbee"}`, which is what step 1 reads on the next run.

Because the start time comes from the target, the job can resume after missed runs, as long as the gap is under 30 days (see [Limitations](#limitations)).

## Configuration

Set these as environment variables, or put them in a `.env` file in the working directory (loaded with `python-dotenv`):

| Variable     | Description                                         | Example                              |
|--------------|-----------------------------------------------------|--------------------------------------|
| `SOURCE_URL` | Base URL of the VictoriaMetrics instance to read from | `https://vms-prod.example.net`       |
| `TARGET_URL` | Base URL of the VictoriaMetrics instance to write to  | `https://vmsingle-lt-prod.example.net` |

Both are required, and a trailing slash is stripped. The metric names, the 1h/1d steps, and the output tags are hardcoded in the script.

## Running locally

Requires Python 3.9+.

```bash
pip install -r requirements.txt
export SOURCE_URL=https://source-vm.example.net
export TARGET_URL=https://target-vm.example.net
python vm_propane_sync.py
```

Exit codes:

- `0`: sync completed, or there was nothing new to sync
- `1`: a required variable is missing, the target has no existing data, or the source returned no data for the window
- non-zero with a traceback: an HTTP or processing error

## Docker

Images are published to GitHub Container Registry at `ghcr.io/danielgoepp/propane-sync`, tagged `:latest` and `:<git-short-sha>`.

```bash
docker run --rm \
  -e SOURCE_URL=https://source-vm.example.net \
  -e TARGET_URL=https://target-vm.example.net \
  ghcr.io/danielgoepp/propane-sync:latest
```

The container runs one sync and exits, so schedule it once a day after midnight UTC (for example as a cron job or a Kubernetes `CronJob`).

### Building

- **CI**: [.github/workflows/docker-image.yml](.github/workflows/docker-image.yml) builds the image on every push and pull request to `main`, and pushes to GHCR on pushes to `main`.
- **Manually**: [build-and-push.sh](build-and-push.sh) builds on the current host and pushes `:latest` and `:<sha>` (with a `-dirty` suffix if the tree has uncommitted changes). Set `NO_PUSH=1` to build only. Pushing needs a one-time login with a PAT that has the `write:packages` scope:

  ```bash
  echo "$GHCR_TOKEN" | docker login ghcr.io -u danielgoepp --password-stdin
  ./build-and-push.sh
  ```

## Limitations

- **The target must already have data.** The start time comes from the last point in the target, so on an empty target the script exits with an error. Load initial history some other way before the first run.
- **30-day lookback.** If the newest point in the target is more than 30 days old, step 1 finds nothing and the script exits as if the target were empty.
- **Write failures are logged, not fatal.** A failed write for one day is logged and the run continues. Because the next run starts after the newest point written, a day that failed in the middle of a batch is not retried automatically.
