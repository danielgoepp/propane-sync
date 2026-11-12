# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python-based data synchronization tool for propane tank level monitoring. The system fetches propane tank level metrics from a source VictoriaMetrics instance, downsamples the data, and writes it to a target instance using InfluxDB line protocol.

## Architecture

- **Main Script**: `vm_propane_sync.py` - Daily sync script designed to run as a cron job
- **Archive**: `archive/propane_downsample_load.py` - Historical data processing script for bulk operations
- **Data Flow**: Source VM → Query/Downsample → Target VM (InfluxDB format)
- **Containerized**: Dockerfile provided for deployment

## Key Components

### Data Pipeline
- Fetches metrics using VictoriaMetrics HTTP API (`/api/v1/query_range`)
- Downsamples hourly data to daily averages using pandas
- Writes data in InfluxDB line protocol format to target instance
- Includes chunk-based processing for large time ranges

### Data Format
- Source metric: `zigbee_tank_level` or `propane_tank_level{db='zigbee'}`
- Target format: `propane,source=sinope,data_source=zigbee tank_level={value} {timestamp}`
- Timestamps converted to nanosecond precision for InfluxDB

## Development Commands

### Running Scripts
```bash
# Main sync script
python vm_propane_sync.py

# Historical data processing
python archive/propane_downsample_load.py
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

Both scripts contain hardcoded configuration that may need adjustment:
- Source/target URLs
- Time ranges (start_time, end_time)
- Metric queries
- Step intervals (1h source, 1d target)
- Chunk sizes for processing

## Data Sources

- **Source**: VictoriaMetrics instances (vms-prod.goepp.net, vmsingle-lt-prod.goepp.net)
- **Target**: Same instances with InfluxDB write endpoints
- **Metrics**: Zigbee-based propane tank level sensors