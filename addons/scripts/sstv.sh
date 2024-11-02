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
  if [ "$MODE" == "SSTV" ]; then
  sox -e float -t raw -r 192000 -b 32 -c 2 "$SATNOGS_APP_PATH/iq_$ID.raw" -t ogg -e float -b 32 -c 2 -r 192000 "$SATNOGS_APP_PATH/iq_$ID.ogg" 
  OPT="-d "$SATNOGS_APP_PATH/iq_$ID.ogg" -o sstv_$ID.png"
  if [ -n "$OPT" ]; then
    mkdir -p "$OUT"
    echo "$PRG $OPT"
    $BIN $OPT > "$LOG" 2>> "$LOG" &
    echo $! > "$PID"
  fi
fi

if [ "${CMD^^}" = "STOP" ]; then
  if [ -f "$PID" ]; then
    PID_number="$(cat "$PID")"
    echo "$PRG Stopping observation $ID - $SATNAME - Process $PID_number"
    kill $PID_number 2>/dev/null

    # Waiting for process to terminate and zombie process to terminate with watchdog
    timeout=120 
    for (( elapsed=0; elapsed<timeout; elapsed+=2 )); do
        if ps -p $PID_number > /dev/null && [ -d /proc/$PID_number ]; then   
            echo "$PRG Waiting for the image processing process ($PID_number) to complete..."
            sleep 2
        else
            echo "$PRG The image processing process is completed."
            rm -f "$PID"
            break
        fi

        if [ $elapsed -ge $timeout ]; then
            echo "$PRG Error - The process ($PID_number) exceeds the allowable time --> Force kill satdump process and stop script !!!"
            kill -9 $PID_number
            rm -f "$PID"
            exit 0
        fi
    done

    echo "$PRG The observation and image processing process are now complete!"
 
    if [ ! "${SATDUMP_KEEPLOGS^^}" == "YES" ]; then
      echo "$PRG Remove log $LOG"
      #rm -rf "$LOG"
    else
      echo "$PRG Keeping logs file $LOG, you need to purge them manually or restarted the container."
    fi
  fi
fi