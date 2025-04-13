#!/usr/bin/env python3
import os
import re
import logging
import requests
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from skyfield.api import EarthSatellite, Topos, load
from dateutil.parser import parse as parse_date
from tqdm import tqdm

# --- CONFIGURATION ---
CONFIG = {
    "modes": ["FSK", "MSK", "GFSK"],
    "min_elevation": 15,
    "visible_hours": 1,
    "min_pass_duration": 180,
    "is_frequency_violator": False,
    "max_scheduled_observations": 100,
    "env_path": "station.env",
    "log_level": logging.INFO,
    "min_success_rate": 5.0,  # Pourcentage minimum de success rate accepté
    "min_time_before_pass_sec": 300  # 5 minutes
}

# --- LOGGING ---
logging.basicConfig(level=CONFIG["log_level"], format="%(asctime)s - %(levelname)s - %(message)s")
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# --- ENV ---
load_dotenv(dotenv_path=CONFIG["env_path"])

def get_env(key, required=True):
    value = os.getenv(key)
    if required and not value:
        logging.error(f"Variable d'environnement manquante : {key}")
        exit(1)
    return value

def get_env_float(key):
    try:
        return float(get_env(key))
    except ValueError:
        logging.error(f"Variable d'environnement invalide : {key}")
        exit(1)

SATNOGS_LAT = get_env_float('SATNOGS_STATION_LAT')
SATNOGS_LON = get_env_float('SATNOGS_STATION_LON')
SATNOGS_ELEV = get_env_float('SATNOGS_STATION_ELEV')
SATNOGS_STATION_ID = get_env('SATNOGS_STATION_ID')
SATNOGS_API_TOKEN = get_env('SATNOGS_API_TOKEN')

API_DB = "https://db.satnogs.org/api"
API_NET = "https://network.satnogs.org/api"

def get_station_frequency_ranges(station_id, token):
    url = f"{API_NET}/stations/{station_id}/"
    headers = {"Authorization": f"Token {token}"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        frequency_ranges = []
        for ant in data.get("antenna", []):
            freq_min = ant.get("frequency")
            freq_max = ant.get("frequency_max")
            if freq_min and freq_max:
                frequency_ranges.append({"min": freq_min, "max": freq_max})
        if not frequency_ranges:
            logging.warning("⚠️ Aucune plage trouvée. Valeurs par défaut utilisées (UHF).")
            frequency_ranges = [{"min": 435000000, "max": 438000000}]
        logging.info(f"Plages de fréquences antenne : {frequency_ranges}")
        return frequency_ranges
    except Exception as e:
        logging.error(f"Erreur API Network station {station_id} : {e}")
        return []

def fetch_json(endpoint, base=API_DB, params=None):
    try:
        response = requests.get(f"{base}/{endpoint}", params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Erreur API {endpoint}: {e}")
        return []

def fetch_all_data():
    logging.info("📡 Récupération des données SatNOGS...")
    for step in tqdm(["satellites", "transmitters", "tle"], desc="📥 Fetching", unit="endpoint"):
        pass
    satellites = fetch_json("satellites/")
    transmitters = fetch_json("transmitters/")
    tles = fetch_json("tle/")
    return satellites, transmitters, tles

def build_satellite_objects(tles, norad_ids):
    logging.info("🛰️ Construction des objets satellites...")
    ts = load.timescale()
    sats = {}
    for tle in tqdm(tles, desc="🔧 Création TLE", unit="sat"):
        if tle['norad_cat_id'] in norad_ids:
            try:
                sat = EarthSatellite(tle['tle1'], tle['tle2'], tle['tle0'], ts)
                sats[tle['norad_cat_id']] = sat
            except Exception as e:
                logging.warning(f"TLE invalide NORAD {tle['norad_cat_id']}: {e}")
    return sats

def normalize_mode(mode):
    return re.sub(r'[^a-z0-9]', '', mode.lower()) if mode else ''

def match_mode(mode, filters):
    return any(f in normalize_mode(mode) for f in filters)

def is_frequency_in_range(freq, ranges):
    return any(r['min'] <= freq <= r['max'] for r in ranges)

def is_visible_pass(sat, observer, ts, start, end, min_elevation):
    try:
        times, events = sat.find_events(observer, start, end, altitude_degrees=min_elevation)
        for ti, event in zip(times, events):
            label = ['rise', 'max', 'set'][event]
            if label == 'max':
                alt, _, _ = (sat - observer).at(ti).altaz()
                yield {'event': label, 'peak': ti.utc_datetime(), 'max_elevation_deg': alt.degrees}
            elif label == 'rise':
                yield {'event': label, 'start': ti.utc_datetime()}
            elif label == 'set':
                yield {'event': label, 'end': ti.utc_datetime()}
    except Exception as e:
        logging.warning(f"Erreur calcul passage NORAD {sat.model.satnum}: {e}")

def get_transmitter_success_rate(uuid):
    url = f"{API_NET}/transmitters/{uuid}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        stats = data.get("stats", {})
        return stats.get("success_rate")
    except Exception as e:
        logging.warning(f"⚠️ Impossible de récupérer le success rate pour {uuid} : {e}")
        return None

def safe_launch_date(sat):
    try:
        launched = sat.get("launched")
        return parse_date(launched) if launched else datetime(1970, 1, 1)
    except Exception:
        return datetime(1970, 1, 1)

def main(config):
    frequency_ranges = get_station_frequency_ranges(SATNOGS_STATION_ID, SATNOGS_API_TOKEN)
    if not frequency_ranges:
        logging.error("Aucune plage de fréquence récupérée. Arrêt.")
        return

    satellites, transmitters, tles = fetch_all_data()
    ts = load.timescale()
    observer = Topos(latitude_degrees=SATNOGS_LAT, longitude_degrees=SATNOGS_LON, elevation_m=SATNOGS_ELEV)
    now = datetime.now(timezone.utc)
    ts_now = ts.utc(now)
    ts_future = ts.utc(now + timedelta(hours=config["visible_hours"]))

    allowed_norads = set()
    filtered_transmitters = {}
    mode_filters = [normalize_mode(m) for m in config["modes"]]

    for tx in transmitters:
        norad = tx.get("norad_cat_id")
        if not norad or not tx.get("alive", False):
            continue
        freq = tx.get("downlink_low") or tx.get("downlink_high")
        if freq is None or not is_frequency_in_range(freq, frequency_ranges):
            continue
        if mode_filters and not match_mode(tx.get("mode"), mode_filters):
            continue
        filtered_transmitters.setdefault(norad, []).append(tx)
        allowed_norads.add(norad)

    valid_sats = {
        s['norad_cat_id']: s for s in satellites
        if s['norad_cat_id'] in allowed_norads and
           s.get("status") == "alive" and
           (config["is_frequency_violator"] or s.get("is_frequency_violator") is not True)
    }

    sat_objects = build_satellite_objects(tles, valid_sats.keys())
    logging.info(f"Satellites compatibles : {len(valid_sats)}")

    visible_passes = []
    for norad, sat in sat_objects.items():
        sat_info = valid_sats[norad]
        tx_list = filtered_transmitters.get(norad, [])
        passes = list(is_visible_pass(sat, observer, ts, ts_now, ts_future, 0))
        if not passes:
            continue
        current = {}
        for p in passes:
            if p["event"] == "rise":
                current = {"start": p["start"]}
            elif p["event"] == "max" and "start" in current:
                current["peak"] = p["peak"]
                current["max_elevation_deg"] = p["max_elevation_deg"]
            elif p["event"] == "set" and "start" in current and "peak" in current:
                current["end"] = p["end"]
                if (current["end"] - current["start"]).total_seconds() < config["min_pass_duration"]:
                    continue
                current["norad"] = norad
                current["sat_info"] = sat_info
                current["tx_list"] = tx_list
                visible_passes.append(current)
                current = {}

    visible_passes.sort(key=lambda x: (x["start"], -safe_launch_date(x["sat_info"]).timestamp()))

    filtered_passes = []
    last_end = None
    for p in visible_passes:
        if last_end is None or p["start"] >= last_end:
            filtered_passes.append(p)
            last_end = p["end"]

    scheduled_count = 0
    already_scheduled_count = 0
    total_duration_scheduled = 0
    total_duration_already = 0

    API_SCHEDULE_ENDPOINT = f"{API_NET}/observations/"
    headers = {
        "Authorization": f"Token {SATNOGS_API_TOKEN}",
        "Content-Type": "application/json"
    }

    for p in filtered_passes:
        if (p["start"] - now).total_seconds() < config["min_time_before_pass_sec"]:
            logging.info(f"🚫 Observation ignorée (trop proche dans le temps < {config['min_time_before_pass_sec']}s) : {p['sat_info'].get('name')} | Début à {p['start']}")
            continue

        tx_candidates = [tx for tx in p["tx_list"] if tx.get("uuid") and len(tx["uuid"]) == 22]
        if not tx_candidates:
            logging.warning(f"🚫 Aucun transmetteur valide pour {p['sat_info'].get('name')}")
            continue

        tx = tx_candidates[0]
        uuid = tx["uuid"]
        freq = tx.get("downlink_low") or tx.get("downlink_high")
        success_rate = get_transmitter_success_rate(uuid)
        if success_rate is not None and success_rate < config["min_success_rate"]:
            logging.info(f"🚫 Observation ignorée (success rate trop bas : {success_rate:.1f}%) pour {p['sat_info'].get('name')}")
            continue

        success_str = f"{success_rate:.1f}%" if success_rate is not None else "N/A"
        duration_sec = int((p["end"] - p["start"]).total_seconds())
        duration_str = f"{duration_sec // 60}m{duration_sec % 60:02d}s"
        max_elev = f"{p.get('max_elevation_deg', 0):.1f}°"
        mode = tx.get("mode", "N/A")

        payload = {
            "start": p["start"].strftime("%Y-%m-%d %H:%M:%S"),
            "end": p["end"].strftime("%Y-%m-%d %H:%M:%S"),
            "ground_station": int(SATNOGS_STATION_ID),
            "transmitter_uuid": uuid,
        }
        if freq:
            payload["center_frequency"] = int(freq)

        try:
            response = requests.post(API_SCHEDULE_ENDPOINT, json=[payload], headers=headers)
            if response.status_code in [200, 201]:
                data = response.json()
                scheduled_count += 1
                total_duration_scheduled += duration_sec
                for obs in data:
                    sat_name = p["sat_info"].get("name", "???")
                    start = obs.get("start", payload["start"])
                    end = obs.get("end", payload["end"])
                    logging.info(f"✅ Observation planifiée : {sat_name} | {start} ➞ {end} | 📊 Success Rate: {success_str} | ⏱ {duration_str} | 📈 Max Elev: {max_elev} | 📡 Mode: {mode}")
            elif response.status_code == 409:
                already_scheduled_count += 1
                total_duration_already += duration_sec
                logging.info(f"🗓️ Observation déjà planifiée (conflit d'horaire) : {p['sat_info'].get('name')} | {p['start']} ➞ {p['end']} | 📊 Success Rate: {success_str} | ⏱ {duration_str} | 📈 Max Elev: {max_elev} | 📡 Mode: {mode}")
            else:
                logging.error(f"❌ Erreur API {response.status_code}: {response.text}")
        except Exception as e:
            logging.error(f"❌ Exception lors de l'appel API : {e}")

    def format_duration(seconds):
        return f"{seconds // 60}m{seconds % 60:02d}s"

    total_duration_all = total_duration_scheduled + total_duration_already
    total_observations = scheduled_count + already_scheduled_count

    logging.info("\n📊 Résumé final :")
    logging.info(f"  ➤ Total satellites analysés : {len(valid_sats)}")
    logging.info(f"  ➤ Observations planifiées : {scheduled_count} | Durée cumulée : {format_duration(total_duration_scheduled)}")
    logging.info(f"  ➤ Observations déjà planifiées : {already_scheduled_count} | Durée cumulée : {format_duration(total_duration_already)}")
    logging.info(f"  ✅ Total des observations considérées : {total_observations} | Durée cumulée : {format_duration(total_duration_all)}")

if __name__ == "__main__":
    main(CONFIG)
