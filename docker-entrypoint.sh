#!/bin/bash
#!/usr/bin/env python3


#set -exo pipefail


arg1=${STEP:-NO}

case $arg1 in
    "fetch_data" )
        python src/script_fetch_yt_data.py
        ;;
    "vertical_publish" )
        python src/script_generate_vertical_publish_top_video.py
        ;;
    "weekly_publish" )
        python src/script_generate_publish_top_video.py
        ;;
    "web" )
        uvicorn src.web.main:app --port 8080 --host 0.0.0.0
        ;;
    *)
      echo "use STEP=[fetch_data | vertical_publish | weekly_publish | web]"
esac

#make schedule
#python src/script_fetch_yt_data.py
#python src/script_generate_publish_top_video.py