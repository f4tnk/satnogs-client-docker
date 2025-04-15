#!/usr/bin/env python3
# ==============================================================================
# 📡 SatNOGS Observation Automator
# ------------------------------------------------------------------------------
# Ce script automatise :
#   ✅ La récupération des satellites actifs depuis la base SatNOGS
#   ✅ Le filtrage intelligent des transmetteurs selon :
#        - statut actif
#        - absence de violation de fréquence
#        - modes de modulation souhaités (FSK, PSK, etc.)
#        - plage de fréquences compatible avec l’antenne de la station
#        - taux de réussite minimum d'observation
#   ✅ Le calcul précis des passages visibles pour la station locale
#   ✅ L'association intelligente d’un seul transmetteur par satellite (meilleur succès)
#   ✅ La suppression des passages qui se chevauchent (priorité : récence, success_rate)
#   ✅ L’affichage clair et lisible des résultats
#   ✅ La programmation automatique des observations via l’API de SatNOGS Network
#
# ℹ️  Utilise la configuration depuis un fichier `.env`
# 🔐 Authentification via token API SatNOGS pour planifier des observations
# 📅 Compatible avec stations SatNOGS déployées sur le réseau mondial
#
# Auteur : F4TNK (Mélaine) 🛰️
# Date   : Avril 2025
# ==============================================================================
import os
import logging
from datetime import datetime, timedelta
import requests
from skyfield.api import load, wgs84
from skyfield.sgp4lib import EarthSatellite
from skyfield.api import load, wgs84, utc
from datetime import timedelta
from tqdm import tqdm
import json
from dotenv import load_dotenv
import requests
import logging


# ------------------------ CONFIGURATION ------------------------

FICHIER_ENV = 'station.env'
SEUIL_ELEVATION = 15  # Angle minimum pour qu'un passage soit considéré visible
DUREE_OBSERVATION_HEURES = 3  # ⬅️ Indiquer ici le nombre d'heures souhaitées pour les observations
DELAI_DEPART_MINUTES = 5
MIN_OBSERVATION_DURATION_SEC = 180  # Exigence API SatNOGS

LOG_FILE = 'satellite_passes.log'

# 🔘 Filtrer uniquement les transmetteurs actifs (alive == True)
FILTER_TX_ALIVE = True  # ou None pour désactiver le filtre

# 🔘 Exclure les transmetteurs avec violation de fréquence
FILTER_TX_NO_FREQ_VIOLATION = True  # False pour désactiver le filtre

# 🔘 Filtrer par mode (ex: 'USB', 'CW', 'FM'), insensible à la casse et match partiel
FILTER_TX_MODES = ["FSK", "MSK", "PSK"]  # Liste vide [] pour désactiver

# 🔘 Filtrer les transmetteurs selon un success_rate minimum (en %)
FILTER_TX_SUCCESS_RATE_MIN = 10 # Exemple : 10 pour 10%, ou None pour désactiver

# 🔘 Liste de mots-clés dans les noms de satellites à exclure (insensible à la casse)
EXCLUDE_SAT_NAMES = ["SITRO", "KINE", "ISS"]  # [] pour désactiver

# 🔘 Priorité aux satellites récents (en jours) avant de départager les passages
SAT_RECENT_LAUNCH_DAYS = 60  # None pour désactiver

DUREE_OBSERVATION = timedelta(hours=DUREE_OBSERVATION_HEURES)
DELAI_DEPART = timedelta(minutes=DELAI_DEPART_MINUTES)

# ------------------------ LOGGING SETUP ------------------------

logging.basicConfig(
    filename=LOG_FILE,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# ------------------------ VAR ENV ------------------------
try:
    load_dotenv(FICHIER_ENV)
    # Lecture de la config depuis FICHIER_ENV
    latitude = float(os.getenv("SATNOGS_STATION_LAT", 0))
    longitude = float(os.getenv("SATNOGS_STATION_LON", 0))
    elevation = float(os.getenv("SATNOGS_STATION_ELEV", 0))
    station_id = os.getenv("SATNOGS_STATION_ID", "inconnu")
    api_token = os.getenv("SATNOGS_API_TOKEN", "")

    position = (latitude, longitude, elevation)
    logging.info(f"📍 Station {station_id} — lat={latitude}, lon={longitude}, elev={elevation} m")
except Exception as e:
    logging.critical(f"Erreur critique lors du chargement de l’environnement : {e}")

# ------------------------ FONCTIONS ------------------------

def get_satellites_actifs():
    """Récupère tous les satellites avec status == 'alive' et filtre par exclusion de nom"""
    try:
        tqdm.write("🔍 Téléchargement des satellites actifs depuis SatNOGS...")
        url = "https://db.satnogs.org/api/satellites/"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            with tqdm.wrapattr(r.raw, "read", total=total, desc="⬇️ Download satellites", unit="B", unit_scale=True) as raw:
                raw_data = raw.read()
            satellites = json.loads(raw_data)

        filtered = {}
        excluded = 0

        for s in satellites:
            name = s.get("name", "").lower()
            norad = s.get("norad_cat_id")
            status = s.get("status")

            if status != 'alive' or not norad:
                continue

            if EXCLUDE_SAT_NAMES:
                if any(substr.lower() in name for substr in EXCLUDE_SAT_NAMES):
                    excluded += 1
                    continue

            filtered[norad] = s

        logging.info(f"✅ Satellites 'alive' retenus : {len(filtered)}")
        if excluded > 0:
            logging.info(f"🚫 Satellites exclus par nom : {excluded}")

        return filtered

    except Exception as e:
        logging.error(f"Erreur récupération satellites : {e}")
        return {}
    
def get_all_tles():
    """Récupère tous les TLEs disponibles avec barre de téléchargement seulement"""
    try:
        tqdm.write("🛰️ Téléchargement des TLE depuis SatNOGS...")
        url = "https://db.satnogs.org/api/tle/"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total = int(r.headers.get('content-length', 0))
            with tqdm.wrapattr(r.raw, "read", total=total, desc="⬇️ Download TLEs", unit="B", unit_scale=True) as raw:
                raw_data = raw.read()
            tles = json.loads(raw_data)

        # ✅ parsing sans barre
        tle_dict = {}
        for tle in tles:
            if tle['tle1'] and tle['tle2']:
                tle_dict[tle['norad_cat_id']] = tle
        return tle_dict
    except Exception as e:
        logging.error(f"Erreur récupération TLEs : {e}")
        return {}

def get_all_transmitters(alive_filter=True, no_freq_violation=True, modes=None, antenna_ranges=None):
    """Récupère et filtre les émetteurs SatNOGS avec logique AND sur tous les critères"""
    try:
        tqdm.write("📡 Téléchargement de tous les émetteurs depuis SatNOGS...")
        url = "https://db.satnogs.org/api/transmitters/"
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_bytes = int(r.headers.get('content-length', 0))
            with tqdm.wrapattr(r.raw, "read", total=total_bytes, desc="⬇️ Download transmitters", unit="B", unit_scale=True) as raw:
                raw_data = raw.read()
            transmitters = json.loads(raw_data)

        total = len(transmitters)
        transmitters_dict = {}
        selected = 0

        # Comptages individuels
        tx_alive = set()
        tx_freq_ok = set()
        tx_mode_ok = set()
        tx_freq_match = set()
        tx_all_filters = set()

        for tx in transmitters:
            if not tx.get('uuid'):
                continue

            uuid = tx['uuid']
            mode = (tx.get('mode') or "").lower()
            freq = tx.get('downlink_low')

            # 📊 Marquage par filtre individuel (non bloquant)
            if alive_filter is None or tx.get('alive') == alive_filter:
                tx_alive.add(uuid)

            if not no_freq_violation or tx.get('frequency_violation') is not True:
                tx_freq_ok.add(uuid)

            if modes:
                if any(m.lower() in mode for m in modes):
                    tx_mode_ok.add(uuid)

            if antenna_ranges and freq:
                if any(min_f <= freq <= max_f for (min_f, max_f) in antenna_ranges):
                    tx_freq_match.add(uuid)

            # ✅ Logique AND combinée (tous critères obligatoires)
            if alive_filter is not None and tx.get('alive') != alive_filter:
                continue
            if no_freq_violation and tx.get('frequency_violation') is True:
                continue
            if modes:
                if not any(m.lower() in mode for m in modes):
                    continue
            if antenna_ranges:
                if not freq or not any(min_f <= freq <= max_f for (min_f, max_f) in antenna_ranges):
                    continue

            # 🎯 Transmetteur validé
            transmitters_dict[uuid] = tx
            tx_all_filters.add(uuid)
            selected += 1

        # 📊 Logs filtrage
        logging.info(f"🎯 Transmetteurs totaux dans l'API : {total}")
        logging.info(f"📊 Transmetteurs correspondant à chaque filtre :")
        if alive_filter is not None:
            logging.info(f"   - alive={alive_filter} : {len(tx_alive)} transmetteurs")
        if no_freq_violation:
            logging.info(f"   - frequency_violation=False : {len(tx_freq_ok)} transmetteurs")
        if modes:
            logging.info(f"   - mode contient {modes} : {len(tx_mode_ok)} transmetteurs")
        if antenna_ranges:
            logging.info(f"   - fréquence dans plage antenne : {len(tx_freq_match)} transmetteurs")
        logging.info(f"✅ Transmetteurs retenus après tous filtres : {selected}")

        return transmitters_dict

    except Exception as e:
        logging.error(f"Erreur récupération émetteurs : {e}")
        return {}

    
def calculer_tous_les_passages(satellites, tle_dict, position, start_time, end_time):
    """Calcule tous les passages de tous les satellites, triés globalement par AOS croissante"""
    tous_les_passages = []

    tqdm.write("🧠 Calcul des passages pour chaque satellite...")
    for norad_id, sat_data in tqdm(satellites.items(), desc="📈 Passage satellites", unit="sat"):
        tle = tle_dict.get(norad_id)
        if not tle:
            continue

        tle_lines = [tle['tle0'], tle['tle1'], tle['tle2']]
        passages = calcul_passages(tle_lines, position, start_time, end_time)

        for p in passages:
            duration = p['LOS'] - p['AOS']
            if duration.total_seconds() > 30:
                p['SAT_NAME'] = sat_data['name']
                p['NORAD_ID'] = norad_id
                tous_les_passages.append(p)

    tous_les_passages.sort(key=lambda p: p['AOS'])  # tri croissant
    return tous_les_passages

def calcul_passages(tle_lines, location, start_time, end_time):
    """Calcule les passages visibles (début à 0° jusqu'à fin à 0°), et filtre sur MAX elevation"""
    try:
        ts = load.timescale()
        satellite = EarthSatellite(tle_lines[1], tle_lines[2], tle_lines[0], ts)
        observer = wgs84.latlon(*location)

        t0 = ts.from_datetime(start_time)
        t1 = ts.from_datetime(end_time)

        # ✅ Trouve tous les passages, sans filtre d’élévation
        times, events = satellite.find_events(observer, t0, t1, altitude_degrees=0.0)
        passages = []
        current_pass = {}

        for t, e in zip(times, events):
            if e == 0:
                current_pass['AOS'] = t.utc_datetime()
            elif e == 1:
                current_pass['MAX'] = t.utc_datetime()
            elif e == 2:
                current_pass['LOS'] = t.utc_datetime()

                # ✅ Passage complet ?
                if 'AOS' in current_pass and 'MAX' in current_pass and 'LOS' in current_pass:
                    try:
                        max_dt = current_pass['MAX'].replace(tzinfo=utc)
                        t_max = ts.utc(max_dt)

                        # Calcule l'élévation max
                        difference = satellite - observer
                        topocentric = difference.at(t_max)
                        alt, az, distance = topocentric.altaz()
                        max_elev = alt.degrees
                        current_pass['MAX_ELEV'] = max_elev

                        # ⛔ Ignorer si l'élévation max est < SEUIL_ELEVATION
                        if max_elev < SEUIL_ELEVATION:
                            current_pass = {}
                            continue

                        # ⛔ Ignorer si durée trop courte
                        duration = (current_pass['LOS'] - current_pass['AOS']).total_seconds()
                        if duration < MIN_OBSERVATION_DURATION_SEC:
                            logging.debug(f"⏳ Passage ignoré — durée trop courte ({duration:.1f}s)")
                            current_pass = {}
                            continue

                        passages.append(current_pass)
                    except Exception as e:
                        logging.warning(f"Erreur calcul élévation max : {e}")
                        current_pass = {}

                else:
                    logging.debug("Passage incomplet ignoré (AOS, MAX ou LOS manquant).")
                current_pass = {}

        passages.sort(key=lambda p: p['AOS'])  # croissant
        return passages

    except Exception as e:
        logging.warning(f"Erreur calcul passage : {e}")
        return []

def lier_transmetteurs_aux_passages(passages, transmitters):
    """Associe les transmetteurs filtrés aux passages, en ne gardant que ceux qui ont au moins un émetteur"""
    transmitters_par_norad = {}
    for tx in transmitters.values():
        norad = tx.get("norad_cat_id")
        if norad:
            transmitters_par_norad.setdefault(norad, []).append(tx)

    passages_avec_tx = []
    for p in passages:
        norad_id = p.get('NORAD_ID')
        tx_lies = transmitters_par_norad.get(norad_id, [])
        if tx_lies:
            p['TRANSMITTERS'] = tx_lies
            passages_avec_tx.append(p)

    logging.info(f"🔗 Passages retenus avec transmetteurs associés : {len(passages_avec_tx)} (sur {len(passages)})")
    return passages_avec_tx


def afficher_passages_satellites(passages):
    """Affiche une liste de passages satellites déjà calculée et triée, avec les transmetteurs associés + stats"""
    for p in passages:
        logging.info(f"🛰 Satellite : {p['SAT_NAME']} (NORAD {p['NORAD_ID']})")
        logging.info(f"  AOS : {p['AOS'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logging.info(f"  MAX : {p['MAX'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logging.info(f"  LOS : {p['LOS'].strftime('%Y-%m-%d %H:%M:%S')} UTC")
        logging.info(f"  Durée : {str(p['LOS'] - p['AOS']).split('.')[0]}")

        if p.get('MAX_ELEV') is not None:
            logging.info(f"  Élévation max : {p['MAX_ELEV']:.1f}°")

        if p.get("TRANSMITTERS"):
            for tx in p["TRANSMITTERS"]:
                mode = tx.get("mode", "N/A")
                freq = tx.get("downlink_low", "N/A")
                success = tx.get("success_rate")
                good = tx.get("good_count")

                # Affichage formaté
                extra = []
                if good is not None:
                    extra.append(f"good={good}")
                if success is not None:
                    extra.append(f"success={success}%")

                stats_str = f" | {' | '.join(extra)}" if extra else ""
                logging.info(f"    📡 {mode} @ {freq} Hz{stats_str}")

        logging.info("-" * 40)


def get_station_info(station_id, api_token):
    """Récupère les informations d'une station SatNOGS + plages antennes"""
    try:
        url = f"https://network.satnogs.org/api/stations/{station_id}/"
        headers = {
            "Authorization": f"Token {api_token}"
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # Logs d'information (inchangés)
        logging.info("📡 Infos station depuis SatNOGS Network :")
        logging.info(f"  📍 Nom       : {data.get('name')}")
        logging.info(f"  🆔 ID        : {data.get('id')}")
        logging.info(f"  🗺️  Loc      : lat={data.get('lat')}, lon={data.get('lng')}, alt={data.get('altitude')} m")
        logging.info(f"  💬 Statut    : {data.get('status')}")
        logging.info(f"  📈 Observ.   : {data.get('observations')} passés, {data.get('future_observations')} futurs")
        logging.info(f"  💻 Client    : {data.get('client_version')}")
        logging.info(f"  👤 Owner     : {data.get('owner')}")

        # 📡 Antennes
        antenna_ranges = []
        for ant in data.get("antenna", []):
            freq = ant.get("frequency")
            freq_max = ant.get("frequency_max")
            if freq and freq_max:
                antenna_ranges.append((freq, freq_max))
                band = ant.get("band", "N/A")
                type_name = ant.get("antenna_type_name", "N/A")
                logging.info(f"  📡 Antenne   : {type_name} ({band}) {freq} Hz - {freq_max} Hz")

        return data, antenna_ranges

    except Exception as e:
        logging.error(f"Erreur récupération des infos de la station {station_id} : {e}")
        return None, []

def enrichir_transmetteurs_avec_stats(transmitters, api_token):
    """Ajoute les stats (success_rate, good_count) à chaque transmetteur via un fetch global.
       Applique aussi un filtre success_rate min, et sélectionne 1 transmetteur max par satellite.
    """
    try:
        tqdm.write("📊 Téléchargement global des stats de transmetteurs depuis SatNOGS Network...")
        url = "https://network.satnogs.org/api/transmitters/"
        headers = {"Authorization": f"Token {api_token}"}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        all_tx_data = response.json()

        # Map global des stats
        stats_map = {
            tx["uuid"]: tx.get("stats", {}) for tx in all_tx_data if "uuid" in tx
        }

        # ✅ Grouper les transmetteurs par satellite (norad_cat_id)
        transmitters_by_sat = {}
        for uuid, tx in transmitters.items():
            norad = tx.get("norad_cat_id")
            if not norad:
                continue

            stats = stats_map.get(uuid, {})
            sr = stats.get("success_rate")
            good = stats.get("good_count")

            tx["success_rate"] = sr
            tx["good_count"] = good

            # ✅ Appliquer filtre success rate si défini
            if FILTER_TX_SUCCESS_RATE_MIN is not None:
                if sr is None or sr < FILTER_TX_SUCCESS_RATE_MIN:
                    continue

            transmitters_by_sat.setdefault(norad, []).append(tx)

        # ✅ Sélection d’un seul transmetteur par satellite
        best_transmitters = {}
        for norad, tx_list in transmitters_by_sat.items():
            def tri_qualite(tx):
                sr = tx.get("success_rate") or 0
                good = tx.get("good_count") or 0
                return (sr, good)  # tri croissant par défaut

            meilleur = sorted(tx_list, key=tri_qualite, reverse=True)[0]
            best_transmitters[meilleur['uuid']] = meilleur

        logging.info(f"✅ Transmetteurs retenus après filtrage & sélection (1/sat) : {len(best_transmitters)}")
        return best_transmitters

    except Exception as e:
        logging.error(f"Erreur récupération bulk des stats : {e}")
        return transmitters

from datetime import datetime, timezone

from datetime import datetime, timezone

from datetime import datetime, timezone

def filtrer_passages_sans_chevauchement(passages):
    """
    Filtre les passages pour éviter les chevauchements temporels.
    🥇 Priorité absolue aux satellites récents (< SAT_RECENT_LAUNCH_DAYS)
    🥈 Sinon, choix par success_rate puis good_count
    """
    passages = sorted(passages, key=lambda p: p['AOS'])
    now = datetime.now(timezone.utc)
    selection = []

    for p in passages:
        overlap = False
        for s in selection:
            if p['AOS'] < s['LOS'] and p['LOS'] > s['AOS']:
                # ⛔ Chevauchement détecté

                def est_recent(passage):
                    tx = passage.get("TRANSMITTERS", [{}])[0]
                    launch_str = tx.get("launched")
                    if launch_str:
                        try:
                            launch_dt = datetime.fromisoformat(launch_str.replace("Z", "+00:00"))
                            return (now - launch_dt).days <= SAT_RECENT_LAUNCH_DAYS
                        except Exception:
                            return False
                    return False

                p_recent = est_recent(p)
                s_recent = est_recent(s)

                if p_recent and not s_recent:
                    selection.remove(s)
                    selection.append(p)
                    logging.info(f"🆕 Priorité au satellite récent : {p['SAT_NAME']}")
                elif not p_recent and s_recent:
                    pass  # garder s
                else:
                    # Sinon départage par success_rate puis good_count
                    def critere(passage):
                        tx = passage.get("TRANSMITTERS", [{}])[0]
                        sr = tx.get("success_rate") or 0
                        gc = tx.get("good_count") or 0
                        return (sr, gc)

                    meilleur = max([p, s], key=critere)
                    if meilleur is not s:
                        selection.remove(s)
                        selection.append(p)

                overlap = True
                break

        if not overlap:
            selection.append(p)

    logging.info(f"📆 Passages sélectionnés sans chevauchement : {len(selection)} (sur {len(passages)} initiaux)")
    return sorted(selection, key=lambda p: p['AOS'])


import logging
import requests
from datetime import datetime

def programmer_observations_satnogs(passages, station_id, api_token, nb_complementaires=0):
    """
    Programme les observations sur SatNOGS Network et affiche un résumé clair,
    incluant les observations déjà planifiées (409) avec durée, success rate, etc.
    """
    url = "https://network.satnogs.org/api/observations/"
    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }

    durations = []
    success_rates = []
    satellites_programmes = set()

    logging.info("🚀 Lancement de la programmation des observations SatNOGS...")

    for p in passages:
        try:
            tx = p["TRANSMITTERS"][0]
            uuid = tx["uuid"]
            sat_name = p['SAT_NAME']
            norad_id = p['NORAD_ID']
            mode = tx.get('mode', 'N/A')
            elev = p.get("MAX_ELEV", 0)
            sr = tx.get("success_rate")

            freq = tx.get("downlink_low") or tx.get("frequency")
            drift_ppb = tx.get("downlink_drift")
            freq_mhz = freq / 1_000_000 if freq else None

            # Affichage log uniquement : drift appliqué pour information
            drifted_freq_mhz = freq_mhz
            if freq and drift_ppb:
                drifted_freq_mhz = (freq * (1 + drift_ppb / 1e9)) / 1_000_000

            duration_sec = (p["LOS"] - p["AOS"]).total_seconds()
            if duration_sec < MIN_OBSERVATION_DURATION_SEC:
                logging.debug(f"⏳ Passage ignoré ({sat_name}) — durée trop courte ({duration_sec:.1f}s)")
                continue

            start_str = p["AOS"].strftime("%Y-%m-%d %H:%M:%S")
            end_str = p["LOS"].strftime("%Y-%m-%d %H:%M:%S")

            # ❌ Pas de center_frequency → SatNOGS décide
            payload = [{
                "ground_station": int(station_id),
                "transmitter_uuid": uuid,
                "start": start_str,
                "end": end_str
            }]

            response = requests.post(url, headers=headers, json=payload)

            # 🪄 Log formaté
            aos = p['AOS'].strftime('%H:%M:%S')
            los = p['LOS'].strftime('%H:%M:%S')
            sr_txt = f" | ✅ Success Rate : {sr}%" if sr is not None else ""
            duree_txt = f"{int(duration_sec // 60)} min {int(duration_sec % 60)} sec"
            freq_display = f"{drifted_freq_mhz:.3f} MHz" if drift_ppb else f"{freq_mhz:.3f} MHz"

            log_line = (
                f"🛰️ {sat_name} | ⏰ {aos} ➡ {los} UTC | 🕒 Durée : {duree_txt} | "
                f"📡 {mode} @ {freq_display} | "
                f"📈 Élév. max : {elev:.1f}°{sr_txt}"
            )

            if response.status_code in (200, 201):
                logging.info(f"🗓️ Observation planifiée → {log_line}")
            elif response.status_code == 409:
                logging.info(f"🗂 Observation déjà planifiée ailleurs → {log_line}")
            else:
                logging.warning(
                    f"❌ Échec programmation : {sat_name} ({uuid}) | "
                    f"Code {response.status_code} | {response.text.strip()}"
                )

            # ✅ Stats cumulées même en cas de doublon (409)
            if response.status_code in (200, 201, 409):
                durations.append(duration_sec)
                satellites_programmes.add(norad_id)
                if sr is not None:
                    success_rates.append(sr)

        except Exception as e:
            logging.error(f"❌ Exception durant la programmation de {p.get('SAT_NAME', '?')} : {e}")

    # 📊 Résumé final
    if passages:
        total_req = (passages[-1]["LOS"] - passages[0]["AOS"]).total_seconds()
    else:
        total_req = 0
    total_obs = sum(durations)
    taux_succes_moyen = round(sum(success_rates) / len(success_rates), 1) if success_rates else 0.0

    logging.info("📊 Résumé final de la programmation :")
    logging.info(f"⏱  Période demandée : {int(total_req // 60)} min {int(total_req % 60)} sec")
    logging.info(f"⌛  Durée totale des observations (programmées ou déjà existantes) : {int(total_obs // 60)} min {int(total_obs % 60)} sec")
    logging.info(f"🧩 Passages complémentaires ajoutés : {nb_complementaires}")
    logging.info(f"🛰️  Nombre total de satellites concernés : {len(satellites_programmes)}")
    logging.info(f"📈  Taux de succès moyen des transmetteurs : {taux_succes_moyen:.1f}%")

def completer_passages_si_besoin(passages_filtres, passages_bruts, api_token, durée_cible_sec, seuils_success_rate, antenna_ranges):
    from copy import deepcopy

    total_sec = sum((p['LOS'] - p['AOS']).total_seconds() for p in passages_filtres)
    logging.info(f"⌛ Durée totale des passages filtrés : {int(total_sec // 60)} min")

    if total_sec >= durée_cible_sec:
        return passages_filtres

    passages_complémentaires = []

    for seuil in seuils_success_rate:
        logging.info(f"🔄 Phase de complétion avec seuil success_rate ≥ {seuil}%")

        # 🔄 Re-télécharge TOUS les transmitters non filtrés
        transmitters_raw = get_all_transmitters(
            alive_filter=FILTER_TX_ALIVE,
            no_freq_violation=FILTER_TX_NO_FREQ_VIOLATION,
            modes=FILTER_TX_MODES,
            antenna_ranges=antenna_ranges   # ou re-récupérer si tu veux la même plage antenne
        )

        # 🧠 Enrichir avec stats, mais appliquer le **nouveau seuil** plus bas
        global FILTER_TX_SUCCESS_RATE_MIN
        ancien_seuil = FILTER_TX_SUCCESS_RATE_MIN
        FILTER_TX_SUCCESS_RATE_MIN = seuil
        transmitters_relax = enrichir_transmetteurs_avec_stats(transmitters_raw, api_token)
        FILTER_TX_SUCCESS_RATE_MIN = ancien_seuil  # rétablir pour éviter effet global

        # ⚡ Relier les passages bruts restants
        passages_restants = [
            p for p in passages_bruts if p not in passages_filtres and p not in passages_complémentaires
        ]
        passages_avec_tx = lier_transmetteurs_aux_passages(passages_restants, transmitters_relax)

        # ⚠️ Éviter chevauchement
        passages_dispo = []
        for p in passages_avec_tx:
            overlap = any(p['AOS'] < s['LOS'] and p['LOS'] > s['AOS'] for s in passages_filtres + passages_complémentaires)
            if not overlap:
                passages_dispo.append(p)

        # 🔽 Tri par success_rate décroissant
        passages_dispo.sort(key=lambda p: p['TRANSMITTERS'][0].get("success_rate") or 0, reverse=True)

        for p in passages_dispo:
            duration = (p['LOS'] - p['AOS']).total_seconds()
            passages_complémentaires.append(p)
            total_sec += duration
            if total_sec >= durée_cible_sec:
                break

        if total_sec >= durée_cible_sec:
            break

    if passages_complémentaires:
        logging.info(f"✅ {len(passages_complémentaires)} passages complémentaires ajoutés")
    else:
        logging.info("❗ Aucun passage complémentaire trouvé malgré abaissement de success_rate")

    return sorted(passages_filtres + passages_complémentaires, key=lambda p: p['AOS']), len(passages_complémentaires)


# ------------------------ SCRIPT PRINCIPAL ------------------------

def main():
    logging.info("Lancement du calcul des passages satellites visibles...")

    try:

        # 📡 Infos station + antennes
        station_info, antenna_ranges = get_station_info(station_id, api_token)


        satellites = get_satellites_actifs()
        logging.info(f"{len(satellites)} satellites 'alive' trouvés depuis SatNOGS DB")

        tle_dict = get_all_tles()
        logging.info(f"{len(tle_dict)} TLEs récupérés depuis SatNOGS DB")

        # 📡 Transmetteurs filtrés selon les critères
        transmitters_filtres = get_all_transmitters(
            alive_filter=FILTER_TX_ALIVE,
            no_freq_violation=FILTER_TX_NO_FREQ_VIOLATION,
            modes=FILTER_TX_MODES,
            antenna_ranges=antenna_ranges
        )

        # 📈 Transmetteurs enrichis avec stats réseau
        transmitters = enrichir_transmetteurs_avec_stats(transmitters_filtres, api_token)

        logging.info(f"{len(transmitters)} émetteurs récupérés et enrichis depuis SatNOGS DB")

        start_time = datetime.utcnow().replace(tzinfo=utc) + DELAI_DEPART
        end_time = start_time + DUREE_OBSERVATION
        logging.info(f"⏱ Observation prévue après {DELAI_DEPART_MINUTES} min pour une durée de {DUREE_OBSERVATION_HEURES} h.")
        passages_bruts = calculer_tous_les_passages(satellites, tle_dict, position, start_time, end_time)

        passages_avec_tx = lier_transmetteurs_aux_passages(passages_bruts, transmitters)

        passages_filtres = filtrer_passages_sans_chevauchement(passages_avec_tx)
        
        # Ajouter complétion si nécessaire
        passages_complets, nb_complementaires = completer_passages_si_besoin(
            passages_filtres=passages_filtres,
            passages_bruts=passages_bruts,
            api_token=api_token,
            durée_cible_sec=int(DUREE_OBSERVATION.total_seconds()),
            seuils_success_rate=[5, 0],  # essayer success rate de 5%, puis 0%
            antenna_ranges=antenna_ranges
        )
        afficher_passages_satellites(passages_complets)

        programmer_observations_satnogs(passages_complets, station_id, api_token, nb_complementaires)

      
    except Exception as e:
        logging.critical(f"Erreur critique : {e}")

if __name__ == "__main__":
    main()
