#!/bin/bash
if [[ ! "${SATDUMP_ENABLE^^}" =~ (TRUE|YES|1) ]]; then exit; fi
set -eu

# {command} {{ID}} {{FREQ}} {{TLE}} {{TIMESTAMP}} {{BAUD}} {{SCRIPT_NAME}} {{MODE}
CMD="$1"     # $1 [start|stop]
ID="$2"      # $2 observation ID
FREQ="$3"    # $3 frequency
TLE="$4"     # $4 used tle's
DATE="$5"    # $5 timestamp Y-m-dTH-M-S
BAUD="$6"    # $6 baudrate
SCRIPT="$7"  # $7 script name, satnogs_bpsk.py
MODE="$8"    # $8 mode FM, FSK

PRG="SatDump:"
: "${SATNOGS_APP_PATH:=/tmp/.satnogs}"
: "${SATNOGS_OUTPUT_PATH:=/tmp/.satnogs/data}"
: "${UDP_DUMP_PORT:=57356}"
: "${SATDUMP_KEEPLOGS:=yes}"
BIN=$(command -v satdump)
LOG="$SATNOGS_APP_PATH/satdump_$ID.log"
OUT="$SATNOGS_APP_PATH/satdump_$ID"
PID="$SATNOGS_APP_PATH/satdump_$SATNOGS_STATION_ID.pid"
UNIXTD="${3:-$(date -u +%s)}" # date -d "2024-04-25T14:07:37" -u +%s
image_count=0

SATNAME=$(echo "$TLE" | jq .tle0 | sed -e 's/ /_/g' | sed -e 's/[^A-Za-z0-9._-]//g')
NORAD=$(echo "$TLE" | jq .tle2 | awk '{print $2}')

if [ -s "$OUT" ]; then
  echo "$PRG Processing data $OUT to network"
  # find images, rename/move to ${SATNOGS_OUTPUT_PATH}/data_<obsid>_YYYY-MM-DDTHH-MM-SS.png
  year=$(date +"%Y")
  month=$(date +"%m")
  day=$(date "+%d")
  hour=$(date "+%H")
  mkdir -p "${SATNOGS_OUTPUT_PATH}/${year}/${month}/${day}/${hour}/${ID}"

  
  noaa_apt_images_upload=(
      "avhrr_3_rgb_Cloud_Top_IR_map.png"
      "avhrr_3_rgb_MCIR_Rain_map.png"
      "avhrr_3_rgb_MCIR_map.png"
      "avhrr_3_rgb_MSA_map.png"
      "avhrr_3_rgb_10.8µm_Thermal_IR.png"
      "avhrr_3_rgb_NO_enhancement_map.png"
    )
    find "$OUT" -type f \( -iname "*.png" \) -print0 | while IFS= read -r -d '' file; do
        echo "Image generated : $(basename "$file")"
        for image in "${noaa_apt_images_upload[@]}"; do
            echo "Image TEST : $(basename "$file")" ======== "$image"
            if [[ $(basename "$file") == "$image" ]]; then
                echo "Image transferred OK : $image !!!!!!!! $(basename "$file")"
                DATE_OBS=$(date +"%Y-%m-%dT%H-%M-%S")
                file_dest="${SATNOGS_OUTPUT_PATH}/data_${ID}_${DATE_OBS}_$(basename "$file")"
                    echo "$PRG The image $(basename "$file_dest") was transferred to the Satnogs network"
                    ((image_count++))
                else
                    echo "$PRG Error transferring the image $(basename "$file")"
                sleep 1
            fi
        done
    done


    if [ ! "${MODE^^}" = "APT" ]; then
        find "$OUT" -type f \( -iname "*.png" \) -print0 | while IFS= read -r -d '' file; do 
            DATE_OBS=$(date +"%Y-%m-%dT%H-%M-%S")
            file_dest="${SATNOGS_OUTPUT_PATH}/${year}/${month}/${day}/${hour}/${ID}/data_${ID}_${DATE_OBS}_$(basename "$file")"
            
            if mv "$file" "$file_dest"; then
                echo "$PRG The image $(basename "$file_dest") was transferred to the Satnogs network"
                ((image_count++))
            else
                echo "$PRG Error transferring the image $(basename "$file")"
            fi
            sleep 1
        done
    fi

    if [ "$image_count" -ne 0 ]; then
        echo "$PRG All images ($image_count) have been transferred to the Satnogs network!"
    else
        echo "$PRG No images were found to transfer."
    fi

    if [ ! "${SATDUMP_KEEPLOGS^^}" = "YES" ]; then
        echo "$PRG Remove output files $OUT"
        #rm -rf "$OUT"
    else
        echo "$PRG Keeping output files $OUT, you need to purge them manually or restart the container."
    fi
fi
#Securing data transfer to disk
sync