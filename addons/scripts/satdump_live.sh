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


SATNAME=$(echo "$TLE" | jq .tle0 | sed -e 's/ /_/g' | sed -e 's/[^A-Za-z0-9._-]//g')
NORAD=$(echo "$TLE" | jq .tle2 | awk '{print $2}')

if [ "${CMD^^}" = "START" ]; then
  if [ -z "$UDP_DUMP_HOST" ]; then
	  echo "$PRG WARNING! UDP_DUMP_HOST not set, no data will be sent to the demod"
  fi
  SAMP=$(find_samp_rate.py "$BAUD" "$SCRIPT")
  if [ -z "$SAMP" ]; then
    SAMP=66560
    echo "$PRG WARNING! find_samp_rate.py did not return valid sample rate!"
  fi
  OPT=""
  SATNUM=""
  echo "$PRG search $SATNAME with mode $MODE"
  case "$NORAD" in
      "25338" | "28654" | "33591") # NOAA 15 # NOAA 18 # NOAA 19
        case "$MODE" in 
          *"APT"*) # Mode APT
              case "$SATNAME" in 
                *"15"*)  SATNUM="15"
                ;;
                *"18"*)  SATNUM="18"
                ;;
                *"19"*)  SATNUM="19"
                ;;
                *)  echo "Satdump : NOAA satellite number ${SATNUM} not found"
                    exit 0
                ;;
              esac
              echo "$PRG running at $SAMP sps on $SATNAME with mode $MODE"
              OPT="live noaa_apt $OUT --source net_source --mode udp --source_id 0 --port $UDP_DUMP_PORT --samplerate $SAMP --frequency $FREQ --satellite_number $SATNUM --start_timestamp $UNIXTD --sdrpp_noise_reduction --finish_processing"
          ;;
         
          *"HRPT"*) # Mode HRPT
              echo "$PRG running at $SAMP sps on $SATNAME with mode $MODE"
              OPT="live noaa_hrpt $OUT --source net_source --mode udp --source_id 0 --port $UDP_DUMP_PORT --samplerate $SAMP --frequency $FREQ --finish_processing"
          ;;
          *) echo "$PRG Mode Satellite NOAA not supported"
        esac
      ;;
      "44387" | "57166" | "59051" | "40069") # METEOR-M N2-2 # METEOR-M N2-3 # METEOR-M N2-4 # METEOR-M N2
        case "$MODE" in 
          *"LRPT"* | *"FSK"*) # Mode LRPT
              case "$NORAD" in 
                "40069")  SATNUM="M2"
                ;;
                "44387")  SATNUM="M2-2"
                ;;
                "57166")  SATNUM="M2-3"
                ;;
                "59051")  SATNUM="M2-4"
                ;;
                *)  echo "Satdump : METEOR satellite number ${SATNUM} not found"
                    exit 0
                ;;
              esac
              echo "$PRG running at $SAMP sps on $SATNAME with mode $MODE"
              OPT="live meteor_m2_lrpt $OUT --source net_source --mode udp --source_id 0 --port $UDP_DUMP_PORT --samplerate $SAMP --frequency $FREQ --satellite_number $SATNUM --finish_processing"
          ;;
          *"HRPT"*) # Mode LRPT
              echo "$PRG running at $SAMP sps on $SATNAME with mode $MODE"
              OPT="live meteor_hrpt $OUT --source net_source --mode udp --source_id 0 --port $UDP_DUMP_PORT --samplerate $SAMP --frequency $FREQ --start_timestamp $UNIXTD --finish_processing"
          ;;
          *) echo "$PRG Mode Satellite METEOR not supported"
             exit 0 
          ;;
        esac
      ;;
      "38771" | "43689") # METOP-B AHRPT (1701.3MHz) METOP-C AHRPT (1701.3MHz)
          case "$MODE" in 
            *"AHRPT"*) # Mode AHRPT
              echo "$PRG running at $SAMP sps on $SATNAME with mode $MODE"
              OPT="live metop_ahrpt $OUT --source net_source --mode udp --source_id 0 --port $UDP_DUMP_PORT --samplerate $SAMP --frequency $FREQ --finish_processing"
            ;;
            *)  echo "$PRG Mode Satellite METOP not supported"
                exit 0
            ;;
          esac
      ;;
      *) echo "$PRG Satellite not supported"
      ;;
  esac

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

#Securing data transfer to disk
sync