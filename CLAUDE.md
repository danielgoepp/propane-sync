# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based data synchronization tool for propane tank level monitoring. The system fetches propane tank level metrics from a source VictoriaMetrics instance, downsamples the data, and writes it to a target instance using InfluxDB line protocol.

## Architecture

- **Main Script**: `vm_propane_sync.py` - Daily sync script designed to run as a cron job
- **Data Flow**: Source VM → Query/Downsample → Target VM (InfluxDB format)
- **Containerized**: Dockerfile provided for deployment

## Key Components

### Data Pipeline
- Fetches metrics using VictoriaMetrics HTTP API (`/api/v1/query_range`)
- Downsamples hourly data to daily averages using pandas
- Writes data in InfluxDB line protocol format to target instance
- Resumes from the last timestamp already present in the target

### Data Format
- Source metric: `zigbee_tank_level` or `propane_tank_level{db='zigbee'}`
- Target format: `propane,source=sinope,data_source=zigbee tank_level={value} {timestamp}`
- Timestamps converted to nanosecond precision for InfluxDB

## Development Commands

### Running Scripts
```bash
# Main sync script
python vm_propane_sync.py
```

### Dependencies
```bash
pip install -r requirements.txt
```

### Docker
```bash
# Build container
docker build -t propane-sync .

# Run container
docker run propane-sync

# Build on the dev server and push to GHCR (ghcr.io/danielgoepp/propane-sync)
./build-and-push.sh
```

Images are published to GitHub Container Registry (not Docker Hub), tagged `:latest` and `:<git-short-sha>`. CI (`.github/workflows/docker-image.yml`) builds on every push/PR and pushes to GHCR on pushes to `main` using `GITHUB_TOKEN`. Running `build-and-push.sh` manually requires a one-time `docker login ghcr.io -u danielgoepp` with a PAT that has `write:packages`.

## Configuration Points

Source/target URLs come from the required `SOURCE_URL` and `TARGET_URL` environment variables (or a `.env` file). Everything else is hardcoded in the script:
- Metric queries
- Step intervals (1h source, 1d target)
- Output measurement and tags

The sync window is computed at runtime: from the day after the last point in the target up to the end of yesterday (UTC).

## Data Sources

- **Source**: `https://vms-prod.goepp.net` (short-term, 30-day retention), metric `zigbee_tank_level`
- **Target**: `https://vms-prod-lt.goepp.net` (long-term, 100-year retention, no dedup), metric `propane_tank_level`, written via `/api/v2/write`
- **Metrics**: Zigbee-based propane tank level sensors

Because the target has no dedup, writing a timestamp that already exists stores a second value rather than replacing it, and VictoriaMetrics can only delete whole series. Values written before the daily-mean fix are midnight readings, not daily means. The difference is ≤0.4 and the history was intentionally left as is.