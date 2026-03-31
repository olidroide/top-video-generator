#!/bin/sh

set -eu

step="${STEP:-${1:-}}"

case "$step" in
    "fetch_data")
        exec python -m src.entrypoints.fetch_data
        ;;
    "vertical_publish")
        exec python -m src.entrypoints.publish_vertical
        ;;
    "weekly_publish")
        exec python -m src.entrypoints.publish_video
        ;;
    "web")
        exec python -m src.entrypoints.api_server
        ;;
    "scheduler")
        exec python -m src.entrypoints.scheduler
        ;;
    *)
        echo "use STEP=[fetch_data | vertical_publish | weekly_publish | web | scheduler]" >&2
        exit 1
        ;;
esac
