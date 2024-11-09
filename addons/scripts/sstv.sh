#!/bin/bash

# {command} {{ID}} {{FREQ}} {{TLE}} {{TIMESTAMP}} {{BAUD}} {{SCRIPT_NAME}} {{MODE}}
CMD="$1"     # $1 [start|stop]
ID="$2"      # $2 observation ID
FREQ="$3"    # $3 frequency
TLE="$4"     # $4 used tle's
DATE="$5"    # $5 timestamp Y-m-dTH-M-S
BAUD="$6"    # $6 baudrate
SCRIPT="$7"  # $7 script name, satnogs_bpsk.py
MODE="$8"    # $8 mode FM, FSK

PRG="SSTV:"
: "${SATNOGS_APP_PATH:=/tmp/.satnogs}"
: "${SATNOGS_OUTPUT_PATH:=/tmp/.satnogs/data}"
: "${UDP_DUMP_PORT:=57356}"
: "${SATDUMP_KEEPLOGS:=yes}"
: "${SATNOGS_REMOVE_OGG_FILES=true}"

BIN=$(command -v sstv)
LOG="$SATNOGS_APP_PATH/sstv_$ID.log"
OUT="$SATNOGS_APP_PATH/sstv_$ID"
PID="$SATNOGS_APP_PATH/sstv_$SATNOGS_STATION_ID.pid"
UNIXTD="${3:-$(date -u +%s)}" # date -d "2024-04-25T14:07:37" -u +%s


SATNAME=$(echo "$TLE" | jq .tle0 | sed -e 's/ /_/g' | sed -e 's/[^A-Za-z0-9._-]//g')
NORAD=$(echo "$TLE" | jq .tle2 | awk '{print $2}')

if [ -z "$CMD" ] || [ -z "$ID" ] || [ -z "$FREQ" ] || [ -z "$TLE" ]; then
  echo "$PRG Error: missing variables"
  exit 1
fi

if [ "${CMD^^}" = "START" ]; then
  if [[ "${MODE,,}" =~ "sstv" ]]; then
    DATE_OBS=$(date +"%Y-%m-%dT%H-%M-%S")
    OGG=$(find $SATNOGS_APP_PATH -type f -name "satnogs_${ID}_*.ogg")
    OPT="-d \"$OGG\" -o \"$SATNOGS_APP_PATH/sstv_$ID.png\""
    echo "$PRG $OPT"
    $BIN $OPT

    if [ -f "$SATNOGS_APP_PATH/sstv_$ID.png" ]; then
      echo "$PRG Processing data $OUT to network"
      # find images, rename/move to ${SATNOGS_OUTPUT_PATH}/data_<obsid>_YYYY-MM-DDTHH-MM-SS.png
      year=$(date +"%Y")
      month=$(date +"%m")
      day=$(date "+%d")
      hour=$(date "+%H")
      basename_dest="${SATNOGS_OUTPUT_PATH}/data_${ID}_${DATE_OBS}_sstv.png"
      if cp "$SATNOGS_APP_PATH/sstv_$ID.png" "$basename_dest"; then
        echo "$PRG The image $basename_dest was transferred to the Satnogs network"
        if [ -f "$SATNOGS_APP_PATH/sstv_$ID.png" ] && [ "${SATNOGS_REMOVE_OGG_FILES^^}" = "TRUE" ]; then
          rm "$SATNOGS_APP_PATH/sstv_$ID.png"
        fi
      else
        echo "$PRG Error transferring the image ${SATNOGS_APP_PATH}/sstv_${ID}.png"
      fi
    else
      echo "$PRG No SSTV image gererated !"
    fi
  fi  
fi
