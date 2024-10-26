#!/bin/bash
if [[ ! "${SATDUMP_ENABLE^^}" =~ (TRUE|YES|1) ]]; then exit 0; fi

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
 
    if if [[ "$MODE" == "APT" ]]; then
    #------------------------NOAA APT---------------------------------#
        noaa_apt_images_upload=(
            "avhrr_3_rgb_Cloud_Top_IR"
            "avhrr_3_rgb_MCIR"
            "avhrr_3_rgb_MCIR_Rain"
            "avhrr_3_rgb_MSA"
            "avhrr_3_rgb_10.8µm_Thermal_IR"
            "avhrr_3_rgb_Day_Cloud_Convection"
            "avhrr_3_rgb_NO_enhancement"
            )

        noaa_images_satdump=()
        while IFS= read -r -d '' file; do
            noaa_images_satdump+=("$file") 
        done < <(find "$OUT" -type f -iname "*.png" -print0)

        for image in "${noaa_apt_images_upload[@]}"; do     
            
            DATE_OBS=$(date +"%Y-%m-%dT%H-%M-%S")
            block="0"

            for file in "${noaa_images_satdump[@]}"; do
                basename=$(basename "$file") 
                file_name=$(echo "$basename" | cut -f1 -d '.')
                basename_dest="${SATNOGS_OUTPUT_PATH}/data_${ID}_${DATE_OBS}_$basename"
                if [[ "$basename" == "$image""_map.png" ]]; then
                    if cp "$file" "$basename_dest"; then
                    ((image_count++))
                        echo "$PRG The image $basename_dest was transferred to the Satnogs network"
                    else
                        echo "$PRG Error transferring the image $file"
                    fi
                    block="1"
                    sleep 1
                    break
                fi
            done
            if [[ "$block" != "1" ]]; then
                for file in "${noaa_images_satdump[@]}"; do
                    basename=$(basename "$file") 
                    file_name=$(echo "$basename" | cut -f1 -d '.')
                    basename_dest="${SATNOGS_OUTPUT_PATH}/data_${ID}_${DATE_OBS}_$basename"
                    if [[ "$basename" == "$image"".png"  ]]; then
                        if cp "$file" "$basename_dest"; then
                            ((image_count++))
                            echo "$PRG The image $basename_dest was transferred to the Satnogs network"
                        else
                            echo "$PRG Error transferring the image $file"
                        fi
                        block="1"
                        sleep 1
                        break
                    fi
                done
            fi
            if [[ "$block" != "1" ]]; then
                for file in "${noaa_images_satdump[@]}"; do
                    basename=$(basename "$file") 
                    file_name=$(echo "$basename" | cut -f1 -d '.')
                    basename_dest="${SATNOGS_OUTPUT_PATH}/data_${ID}_${DATE_OBS}_$basename"
                    if [[ "$basename" == "$image""_(Uncalibrated)_map.png" ]]; then
                        if cp "$file" "$basename_dest"; then
                            ((image_count++))
                            echo "$PRG The image $basename_dest was transferred to the Satnogs network"
                        else
                            echo "$PRG Error transferring the image $file"
                        fi
                        block="1"
                        sleep 1
                        break
                    fi
                done
            fi
            if [[ "$block" != "1" ]]; then
                for file in "${noaa_images_satdump[@]}"; do
                    basename=$(basename "$file") 
                    file_name=$(echo "$basename" | cut -f1 -d '.')
                    basename_dest="${SATNOGS_OUTPUT_PATH}/data_${ID}_${DATE_OBS}_$basename"
                    if [[ "$basename" == "$image""_(Uncalibrated).png" ]]; then
                        if cp "$file" "$basename_dest"; then
                            ((image_count++))
                            echo "$PRG The image $basename_dest was transferred to the Satnogs network"
                        else
                            echo "$PRG Error transferring the image $file"
                        fi
                        block="1"
                        sleep 1
                        break
                    fi
                done
            fi
        done

        if [ "$image_count" -ne 0 ]; then
            echo "$PRG All images ($image_count) have been transferred to the Satnogs network!"
        else
            echo "$PRG No images were found to transfer."
        fi
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