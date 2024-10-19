#!/bin/bash
if [[ ! "${SATDUMP_ENABLE^^}" =~ (TRUE|YES|1) ]]; then exit; fi
set -eu

# {command} {{ID}} {{FREQ}} {{TLE}} {{TIMESTAMP}} {{BAUD}} {{SCRIPT_NAME}}
CMD="$1"     # $1 [start|stop]
ID="$2"      # $2 observation ID
FREQ="$3"    # $3 frequency
TLE="$4"     # $4 used tle's
DATE="$5"    # $5 timestamp Y-m-dTH-M-S
BAUD="$6"    # $6 baudrate
SCRIPT="$7"  # $7 script name, satnogs_bpsk.py

PRG="SatDump:"
: "${SATNOGS_APP_PATH:=/tmp/.satnogs}"
: "${SATNOGS_OUTPUT_PATH:=/tmp/.satnogs/data/}"
: "${UDP_DUMP_PORT:=57356}"
: "${SATDUMP_KEEPLOGS:=yes}"
BIN=$(command -v satdump)
LOG="$SATNOGS_APP_PATH/satdump_$ID.log"
OUT="$SATNOGS_APP_PATH/satdump_$ID"
PID="$SATNOGS_APP_PATH/satdump_$SATNOGS_STATION_ID.pid"
UNIXTD="${3:-$(date -u +%s)}" # date -d "2024-04-25T14:07:37" -u +%s

SATNAME=$(echo "$TLE" | jq .tle0 | sed -e 's/ /_/g' | sed -e 's/[^A-Za-z0-9._-]//g')
NORAD=$(echo "$TLE" | jq .tle2 | awk '{print $2}')

if [ "${CMD^^}" == "START" ]; then
  if [ -z "$UDP_DUMP_HOST" ]; then
	  echo "$PRG WARNING! UDP_DUMP_HOST not set, no data will be sent to the demod"
  fi
  SAMP=$(find_samp_rate.py "$BAUD" "$SCRIPT")
  if [ -z "$SAMP" ]; then
    SAMP=66560
    echo "$PRG WARNING! find_samp_rate.py did not return valid sample rate!"
  fi
  OPT=""
  case "$NORAD" in
      "25338" | "28654" | "33591") # NOAA 15 # NOAA 18 # NOAA 19
          case "$SATNAME" in 
            *"15"*)  satellite_number="15"
            ;;
            *"18"*)  satellite_number="18"
            ;;
            *"19"*)  satellite_number="19"
            ;;
            *) echo "Satdump : noaa satellite_number not found"
          esac
          OPT="live noaa_apt baseband $OBS $OUT --start_timestamp $UNIXTD --samplerate $SAMP --baseband_format cs16 --satellite_number $satellite_number"
      ;;
      "44387" | "57166" | "59051" | "40069") # METEOR-M N2-2 # METEOR-M N2-3 # METEOR-M N2-4 # METEOR-M N2
          OPT="live meteor_m2_lrpt baseband $OBS $OUT --start_timestamp $UNIXTD --samplerate $SAMP --baseband_format cs16"
      ;;
      "38771" | "43689") # METOP-B AHRPT (1701.3MHz)
          OPT="live metop_ahrpt baseband $OBS $OUT --start_timestamp $UNIXTD --samplerate $SAMP --baseband_format cs16"
      ;;
      *) echo "Satdump : satellite not found"
  esac

  if [ -n "$OPT" ]; then
    mkdir -p "$OUT"
    echo "$PRG running at $SAMP sps on $SATNAME"
    echo "$OPT"
    $BIN $OPT > "$LOG" 2>> "$LOG" &
    echo $! > "$PID"
  fi
fi

if [ "${CMD^^}" == "STOP" ]; then
  if [ -f "$PID" ]; then
    echo "$PRG Stopping observation $ID"
    kill "$(cat "$PID")"
    rm -f "$PID"
  fi

  if [ -s "$OUT" ]; then
    echo "$PRG processing data to network"
    # find images, rename/move to ${SATNOGS_OUTPUT_PATH}/data_<obsid>_YYYY-MM-DDTHH-MM-SS.png
    # data_obs/2024/10/19/17/10422188/data_10422188_2024-10-19T17-27-17.png
    date_obs=date +"%Y-%d-%mT%H-%M-%C"

    sleep 1
    for file in $OUT/*.png; do
      year=date +"%Y"
      month=date +"%m"
      day=date "+%d"
      file_dest="${SATNOGS_OUTPUT_PATH}/${year}/${month}/${day}/data_$date_obs.png"
      mv $file $file_dest
      echo "Satdump : Update image $file_dest successful to satnogs"
    done

    if [ ! "${SATDUMP_KEEPLOGS^^}" == "YES" ]; then
      rm -rf "$OUT"
    fi

  fi

  if [ ! -s "$LOG" ] || [ ! "${SATDUMP_KEEPLOGS^^}" == "YES" ]; then
    # rm -f "$LOG"
    echo $LOG
  else
    echo "$PRG Keeping logs, you need to purge them manually."
  fi
fi