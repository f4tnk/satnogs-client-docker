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

BIN=$(command -v sstv)
LOG="$SATNOGS_APP_PATH/sstv_$ID.log"
OUT="$SATNOGS_APP_PATH/sstv_$ID"
PID="$SATNOGS_APP_PATH/sstv_$SATNOGS_STATION_ID.pid"
UNIXTD="${3:-$(date -u +%s)}" # date -d "2024-04-25T14:07:37" -u +%s


SATNAME=$(echo "$TLE" | jq .tle0 | sed -e 's/ /_/g' | sed -e 's/[^A-Za-z0-9._-]//g')
NORAD=$(echo "$TLE" | jq .tle2 | awk '{print $2}')

if [ "${CMD^^}" = "START" ]; then
  if [[ "$MODE" =~ SSTV ]]; then
    sox -e float -t raw -r 192000 -b 32 -c 2 "$SATNOGS_APP_PATH/iq.raw" -t wav -e float -b 32 -c 2 -r 192000 "$SATNOGS_APP_PATH/iq_$ID.wav" 
    OPT="-d $SATNOGS_APP_PATH/iq_$ID.ogg -o $SATNOGS_APP_PATH/sstv_$ID.png"
    if [ -n "$OPT" ]; then
      mkdir -p "$OUT"
      echo "$PRG $OPT"
      $BIN $OPT
    fi
    if [ -f "$SATNOGS_APP_PATH/sstv_$ID.png" ]; then
      echo "$PRG Processing data $OUT to network"
      # find images, rename/move to ${SATNOGS_OUTPUT_PATH}/data_<obsid>_YYYY-MM-DDTHH-MM-SS.png
      year=$(date +"%Y")
      month=$(date +"%m")
      day=$(date "+%d")
      hour=$(date "+%H")
      DATE_OBS=$(date +"%Y-%m-%dT%H-%M-%S")
      basename_dest="${SATNOGS_OUTPUT_PATH}/data_${ID}_${DATE_OBS}_sstv.png"
      if cp "$SATNOGS_APP_PATH/sstv_$ID.png" "$basename_dest"; then
        echo "$PRG The image $basename_dest was transferred to the Satnogs network"
      else
        echo "$PRG Error transferring the image $file"
      fi
    else
      echo "$PRG No SSTV image gererated !"
    fi
  fi  
fi
