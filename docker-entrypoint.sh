#!/bin/bash

set -euo pipefail


arg1=${STEP:-NO}

case $arg1 in
    "fetch_data" )
        python -m src.entrypoints.fetch_data
        ;;
    "vertical_publish" )
        python -m src.entrypoints.publish_vertical
        ;;
    "weekly_publish" )
        python -m src.entrypoints.publish_video
        ;;
    "web" )
        python -m src.entrypoints.api_server
        ;;
    *)
      echo "use STEP=[fetch_data | vertical_publish | weekly_publish | web]"
esac

#make schedule
#python -m src.entrypoints.fetch_data
#python -m src.entrypoints.publish_video
