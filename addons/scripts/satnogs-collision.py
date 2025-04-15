#!/usr/bin/env python3
# 📡 SatNOGS Observation Automator (modifié)

import os
import logging
import requests
from dotenv import load_dotenv
from tqdm import tqdm
from datetime import datetime

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

# ------------------------ CONFIGURATION ------------------------
FICHIER_ENV = 'station.env'
LOG_FILE = 'satnogs_filtered.log'
SAT_FILTER_ALIVE = True
TX_FILTER_ALIVE = True
OBSERVATION_ID = 11418109
COLLISION_BAND_KHZ = 25  # +/- en kHz

# ------------------------ LOGGING SETUP ------------------------
logging.basicConfig(
    filename=LOG_FILE,
    filemode='w',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# ------------------------ ENV ------------------------
load_dotenv(FICHIER_ENV)
latitude = float(os.getenv("SATNOGS_STATION_LAT", 0))
longitude = float(os.getenv("SATNOGS_STATION_LON", 0))
elevation = float(os.getenv("SATNOGS_STATION_ELEV", 0))
station_id = os.getenv("SATNOGS_STATION_ID", "inconnu")
api_token = os.getenv("SATNOGS_API_TOKEN", "")
position = (latitude, longitude, elevation)

# ------------------------ FUNCTIONS ------------------------
def mhz(freq_hz):
    try:
        return f"{float(freq_hz) / 1_000_000:.3f} MHz"
    except:
        return "N/A"

def get_station_info(station_id, api_token):
    try:
        url = f"https://network.satnogs.org/api/stations/{station_id}/"
        headers = {"Authorization": f"Token {api_token}"}
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()

        logging.info("\n📡 Infos station depuis SatNOGS Network :")
        logging.info(f"  📍 Nom       : {data.get('name')}")
        logging.info(f"  🆔 ID        : {data.get('id')}")
        logging.info(f"  🗺️  Loc      : lat={data.get('lat')}, lon={data.get('lng')}, alt={data.get('altitude')} m")
        logging.info(f"  💬 Statut    : {data.get('status')}")
        logging.info(f"  📈 Observ.   : {data.get('observations')} passés, {data.get('future_observations')} futurs")
        logging.info(f"  💻 Client    : {data.get('client_version')}")
        logging.info(f"  👤 Owner     : {data.get('owner')}")
        return data, []
    except Exception as e:
        logging.error(f"Erreur infos station : {e}")
        return {}, []

def get_satellites_actifs():
    try:
        url = "https://db.satnogs.org/api/satellites/"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            data = list(tqdm(r.json(), desc="⬇️ Téléchargement satellites"))
        sats = {s['norad_cat_id']: s for s in data if s.get("status") == "alive" and s.get("norad_cat_id")}
        logging.info(f"✅ {len(sats)} satellites 'alive' récupérés")
        return sats
    except Exception as e:
        logging.error(f"Erreur satellites : {e}")
        return {}

def get_all_tles():
    try:
        url = "https://db.satnogs.org/api/tle/"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            data = list(tqdm(r.json(), desc="⬇️ Téléchargement TLEs"))
        return {tle['norad_cat_id']: tle for tle in data if tle['tle1'] and tle['tle2']}
    except Exception as e:
        logging.error(f"Erreur TLEs : {e}")
        return {}

def get_all_transmitters(alive_filter=True, antenna_ranges=None):
    try:
        url = "https://db.satnogs.org/api/transmitters/"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            data = list(tqdm(r.json(), desc="⬇️ Téléchargement TX"))
        result = {
            tx['uuid']: tx for tx in data
            if (not alive_filter or tx.get('alive'))
        }
        logging.info(f"✅ {len(result)} transmetteurs 'alive' récupérés")
        return result
    except Exception as e:
        logging.error(f"Erreur TX : {e}")
        return {}

def get_all_network_transmitters():
    """Récupère tous les transmetteurs depuis SatNOGS Network (avec stats et success_rate)."""
    try:
        url = "https://network.satnogs.org/api/transmitters/"
        r = requests.get(url)
        r.raise_for_status()
        transmitters = r.json()

        logging.info(f"✅ {len(transmitters)} transmetteurs récupérés depuis le réseau SatNOGS")
        return transmitters
    except Exception as e:
        logging.error(f"❌ Erreur téléchargement TX réseau : {e}")
        return []

def lier_transmetteurs_aux_satellites(satellites, transmitters):
    tx_par_sat = {}
    for tx in transmitters.values():
        norad_id = tx.get("norad_cat_id")
        if norad_id in satellites:
            tx_par_sat.setdefault(norad_id, []).append(tx)
    logging.info(f"🔗 Transmetteurs liés à {len(tx_par_sat)} satellites")
    return tx_par_sat

def fetch_observation_details(observation_id):
    try:
        url = f"https://network.satnogs.org/api/observations/{observation_id}/"
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()

        start = data.get("start")
        end = data.get("end")
        freq = data.get("observation_frequency")
        mode = data.get("transmitter_mode")
        transmitter = data.get("transmitter")
        sat_name = data.get("tle0")

        logging.info("\n🔍 Détails observation:")
        logging.info(f"  📡 Sat      : {sat_name}")
        logging.info(f"  🛰 Tx UUID  : {transmitter}")
        logging.info(f"  🎛 Mode     : {mode}")
        logging.info(f"  📅 Start    : {start}")
        logging.info(f"  ⏱ End      : {end}")
        logging.info(f"  📶 Freq     : {mhz(freq)}")

        return start, end, freq, sat_name
    except Exception as e:
        logging.error(f"Erreur récupération observation {observation_id} : {e}")
        return None, None, None, None

def detecter_collisions(freq_ref_hz, start_iso, end_iso, transmitters, satellites, sat_name_obs, stats_by_uuid):
    start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    min_freq = freq_ref_hz - (COLLISION_BAND_KHZ * 1000)
    max_freq = freq_ref_hz + (COLLISION_BAND_KHZ * 1000)

    suspects = []
    for tx in tqdm(transmitters.values(), desc="🔎 Vérif collisions"):
        freq = tx.get("downlink_low") or tx.get("frequency")
        if not freq:
            continue

        try:
            freq = float(freq)
        except ValueError:
            continue

        if min_freq <= freq <= max_freq:
            norad = tx.get("norad_cat_id")
            nom_sat = satellites.get(norad, {}).get("name", "???")
            if nom_sat == sat_name_obs:
                continue
            suspects.append((nom_sat, tx))

    logging.info(f"🔍 Transmetteurs potentiellement en collision (+/-{COLLISION_BAND_KHZ} kHz) : {len(suspects)}")
    for nom_sat, tx in suspects:
        mode = tx.get("mode", "N/A")
        freq_affiche = mhz(tx.get("downlink_low") or tx.get("frequency"))
        uuid = tx.get("uuid")
        stats = stats_by_uuid.get(uuid, {})

        success_rate = stats.get("success_rate")
        good_count = stats.get("good_count", 0)
        bad_count = stats.get("bad_count", 0)

        success_txt = f"{success_rate:.1f}%" if success_rate is not None else "N/A"

        logging.info(
            f"  🛰️ {nom_sat} | {freq_affiche} | Mode : {mode} | 🎯 Success rate : {success_txt} "
            f"| ✅ Good: {good_count} | ❌ Bad: {bad_count}"
        )

    return suspects

# ------------------------ MAIN ------------------------
def main():
    logging.info("\n===== Lancement SatNOGS Automator (lite) =====")

    station_data, _ = get_station_info(station_id, api_token)
    sats = get_satellites_actifs()
    tles = get_all_tles()

    txs = get_all_transmitters(alive_filter=TX_FILTER_ALIVE)
    tx_par_sat = lier_transmetteurs_aux_satellites(sats, txs)

    network_txs = get_all_network_transmitters()
    stats_by_uuid = {
        tx["uuid"]: tx.get("stats", {}) for tx in network_txs if tx.get("uuid")
    }

    logging.info(f"\n📦 TLEs : {len(tles)} | 📻 Transmetteurs : {len(txs)}")

    start, end, freq, sat_name = fetch_observation_details(OBSERVATION_ID)
    if start and end and freq and sat_name:
        detecter_collisions(freq, start, end, txs, sats, sat_name, stats_by_uuid)

if __name__ == "__main__":
    main()
