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
LOG_FILE = 'satnogs-auto-scheduler.log'
SEUIL_ELEVATION = 15  # Angle minimum pour qu'un passage soit considéré visible
DUREE_OBSERVATION_HEURES = 1  # ⬅️ Indiquer ici le nombre d'heures souhaitées pour les observations
DELAI_DEPART_MINUTES = 5 # Exigence API SatNOGS Network
MIN_OBSERVATION_DURATION_SEC = 180  # Exigence API SatNOGS Network
MAX_PASSAGE_DURATION_MIN = 20  # Durée maximale d'un passage en minutes
FILTER_SAT_STATUS = "alive" # 🔘 Ex: "alive" / None pour ignorer
FILTER_TX_ALIVE = True  # 🔘 Filtrer uniquement les transmetteurs actifs : True / False / None
FILTER_TX_STATUS = "active"  # 🔘 Filtrer sur le champ 'status' des transmetteurs : "active" / "inactive" / None
FILTER_TX_NO_FREQ_VIOLATION = True  # 🔘 Exclure les transmetteurs avec violation de fréquence True : True / None
FILTER_TX_MODES = ["FSK", "MSK", "PSK"]  # 🔘 Filtrer par mode (ex: 'USB', 'CW', 'FM'), insensible à la casse et match partiel / Liste vide [] pour désactiver
FILTER_TX_SUCCESS_RATE_MIN = 25 # # 🔘 Filtrer les transmetteurs selon un success_rate minimum (en %) ou None pour désactivé
EXCLUDE_SAT_NAMES = ["SITRO", "KINE", "ISS", "ION-MK", "DOSAAF"]  # 🔘 Liste de mots-clés dans les noms de satellites à exclure (insensible à la casse) : ["ISS", "KINE"] / None ou [] pour ignorer


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

logger = logging.getLogger(__name__)

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

def get_satellites_actifs(status_filter=FILTER_SAT_STATUS, exclude_names=EXCLUDE_SAT_NAMES):
    """Récupère tous les satellites et applique des filtres dynamiques sur le statut et le nom."""
    try:
        tqdm.write("🔍 Téléchargement des satellites depuis SatNOGS...")

        url = "https://db.satnogs.org/api/satellites/"
        satellites = get_paginated_endpoint(url)

        if not satellites:
            logging.warning("⚠️ Aucun satellite récupéré depuis l'API SatNOGS.")
            return {}

        filtered = {}
        excluded = 0
        without_norad = 0

        for s in tqdm(satellites, desc="🛰️ Traitement satellites", unit="sat"):
            name = s.get("name", "").lower()
            norad = s.get("norad_cat_id")
            status = s.get("status")

            # ⛔ Pas de NORAD → on ignore
            if not norad:
                without_norad += 1
                continue

            # 🎯 Filtre sur le status (ex: 'alive') si activé
            if status_filter is not None and status != status_filter:
                continue

            # 🎯 Filtre par exclusion de nom (si liste non vide)
            if exclude_names:
                if any(substr.lower() in name for substr in exclude_names):
                    excluded += 1
                    continue

            # ✅ Satellite retenu
            filtered[norad] = s

        # 🧾 Résumé
        tqdm.write(f"✅ Satellites retenus : {len(filtered)}")
        if excluded > 0:
            tqdm.write(f"🚫 Satellites exclus par nom : {excluded}")
        if without_norad > 0:
            tqdm.write(f"❓ Satellites ignorés (pas de NORAD) : {without_norad}")

        return filtered

    except Exception as e:
        logging.error(f"Erreur récupération satellites : {e}")
        return {}

    
def get_all_tles():
    """Récupère tous les TLEs disponibles avec barre de progression"""
    try:
        tqdm.write("🛰️ Téléchargement des TLE depuis SatNOGS...")
        url = "https://db.satnogs.org/api/tle/"
        tles = get_paginated_endpoint(url)

        if not tles:
            logging.warning("⚠️ Aucun TLE récupéré depuis l'API SatNOGS.")
            return {}

        tle_dict = {}
        for tle in tqdm(tles, desc="📦 Parsing TLEs", unit="tle"):
            if tle['tle1'] and tle['tle2']:
                tle_dict[tle['norad_cat_id']] = tle

        return tle_dict
    except Exception as e:
        logging.error(f"Erreur récupération TLEs : {e}")
        return {}



def get_all_transmitters(alive_filter=FILTER_TX_ALIVE,
                         status_filter=FILTER_TX_STATUS,
                         no_freq_violation=FILTER_TX_NO_FREQ_VIOLATION,
                         modes=FILTER_TX_MODES,
                         antenna_ranges=None):
    """Récupère et filtre les émetteurs SatNOGS avec logique AND sur les filtres actifs uniquement."""
    try:
        tqdm.write("📡 Téléchargement de tous les émetteurs depuis SatNOGS...")
        url = "https://db.satnogs.org/api/transmitters/"
        transmitters = get_paginated_endpoint(url)

        if not transmitters:
            logging.warning("⚠️ Aucun transmetteur récupéré depuis l’API.")
            return {}

        total = len(transmitters)
        transmitters_dict = {}
        selected = 0

        # Stats de filtrage
        counts = {
            "alive": 0,
            "status": 0,
            "freq_violation": 0,
            "modes": 0,
            "antenna": 0
        }

        for tx in transmitters:
            if not tx.get('uuid'):
                continue

            uuid = tx['uuid']
            mode = (tx.get('mode') or "").lower()
            freq = tx.get('downlink_low')

            # Comptage pour log (même si désactivé)
            if tx.get('alive'):
                counts["alive"] += 1
            if tx.get('status') == "active":
                counts["status"] += 1
            if not tx.get('frequency_violation'):
                counts["freq_violation"] += 1
            if any(m.lower() in mode for m in (modes or [])):
                counts["modes"] += 1
            if freq and any(min_f <= freq <= max_f for (min_f, max_f) in (antenna_ranges or [])):
                counts["antenna"] += 1

            # 💡 Appliquer seulement les filtres actifs
            if alive_filter is not None and tx.get('alive') != alive_filter:
                continue
            if status_filter is not None and tx.get('status') != status_filter:
                continue
            if no_freq_violation is True and tx.get('frequency_violation') is True:
                continue
            if modes and not any(m.lower() in mode for m in modes):
                continue
            if antenna_ranges:
                if not freq or not any(min_f <= freq <= max_f for (min_f, max_f) in antenna_ranges):
                    continue

            transmitters_dict[uuid] = tx
            selected += 1

        # 🧾 Logs détaillés
        logging.info(f"🎯 Transmetteurs totaux dans l’API : {total}")
        if alive_filter is not None:
            logging.info(f"   - alive={alive_filter} : {counts['alive']} transmetteurs")
        if status_filter is not None:
            logging.info(f"   - status={status_filter} : {counts['status']} transmetteurs")
        if no_freq_violation is not None:
            logging.info(f"   - frequency_violation=False : {counts['freq_violation']} transmetteurs")
        if modes:
            logging.info(f"   - mode contient {modes} : {counts['modes']} transmetteurs")
        if antenna_ranges:
            logging.info(f"   - fréquence dans plage antenne : {counts['antenna']} transmetteurs")
        logging.info(f"✅ Transmetteurs retenus après tous filtres actifs : {selected}")

        return transmitters_dict

    except Exception as e:
        logging.error(f"Erreur récupération émetteurs : {e}")
        return {}

    
def calculer_tous_les_passages(satellites, tle_dict, position, start_time, end_time):
    """Calcule tous les passages de tous les satellites, triés globalement par AOS croissante"""
    tous_les_passages = []

    tqdm.write("🧠 Calcul des passages pour chaque satellite...")

    for norad_id, sat_data in tqdm(satellites.items(), desc="📈 Calcul passages", unit="sat"):
        tle = tle_dict.get(norad_id)
        if not tle:
            continue

        tle_lines = [tle['tle0'], tle['tle1'], tle['tle2']]
        passages = calcul_passages(tle_lines, position, start_time, end_time)

        for p in passages:
            duration = p['LOS'] - p['AOS']
            if duration.total_seconds() > 30:  # passage trop court = ignoré
                p['SAT_NAME'] = sat_data['name']
                p['NORAD_ID'] = norad_id
                tous_les_passages.append(p)

    tous_les_passages.sort(key=lambda p: p['AOS'])  # Tri AOS croissant
    return tous_les_passages


def calcul_passages(tle_lines, location, start_time, end_time, max_duration_min=MAX_PASSAGE_DURATION_MIN):
    """Calcule les passages visibles, filtre par élévation, durée min et durée max (en minutes)"""
    try:
        ts = load.timescale()
        satellite = EarthSatellite(tle_lines[1], tle_lines[2], tle_lines[0], ts)
        observer = wgs84.latlon(*location)

        t0 = ts.from_datetime(start_time)
        t1 = ts.from_datetime(end_time)

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

                if 'AOS' in current_pass and 'MAX' in current_pass and 'LOS' in current_pass:
                    try:
                        max_dt = current_pass['MAX'].replace(tzinfo=utc)
                        t_max = ts.utc(max_dt)

                        difference = satellite - observer
                        topocentric = difference.at(t_max)
                        alt, az, distance = topocentric.altaz()
                        max_elev = alt.degrees
                        current_pass['MAX_ELEV'] = max_elev

                        duration_sec = (current_pass['LOS'] - current_pass['AOS']).total_seconds()
                        duration_min = duration_sec / 60

                        if max_elev < SEUIL_ELEVATION:
                            current_pass = {}
                            continue
                        if duration_sec < MIN_OBSERVATION_DURATION_SEC:
                            logging.debug(f"⏳ Passage ignoré — trop court ({duration_sec:.1f}s)")
                            current_pass = {}
                            continue
                        if duration_min > max_duration_min:
                            logging.debug(f"⏳ Passage ignoré — trop long ({duration_min:.1f} min)")
                            current_pass = {}
                            continue

                        passages.append(current_pass)
                    except Exception as e:
                        logging.warning(f"Erreur calcul élévation max : {e}")
                        current_pass = {}
                else:
                    logging.debug("⛔ Passage incomplet ignoré (AOS, MAX ou LOS manquant).")
                current_pass = {}

        passages.sort(key=lambda p: p['AOS'])  # tri croissant
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
                uuid = tx.get("uuid", "N/A")
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
                logging.info(f"    📡 {mode} ({uuid}) @ {freq} Hz{stats_str}")

        logging.info("-" * 40)

def get_station_info(station_id, api_token):
    """Récupère les informations d'une station SatNOGS + plages antennes"""
    url = f"https://network.satnogs.org/api/stations/{station_id}/"
    headers = {"Authorization": f"Token {api_token}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        # ✅ Logs informatifs
        logging.info("📡 Infos station depuis SatNOGS Network :")
        logging.info(f"  📍 Nom       : {data.get('name')}")
        logging.info(f"  🆔 ID        : {data.get('id')}")
        logging.info(f"  🗺️  Loc      : lat={data.get('lat')}, lon={data.get('lng')}, alt={data.get('altitude')} m")
        logging.info(f"  💬 Statut    : {data.get('status')}")
        logging.info(f"  📈 Observ.   : {data.get('observations')} passés, {data.get('future_observations')} futurs")
        logging.info(f"  💻 Client    : {data.get('client_version')}")
        logging.info(f"  👤 Owner     : {data.get('owner')}")

        # 📡 Extraction des plages d'antennes
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

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Erreur réseau pour récupération station {station_id} : {e}")
    except Exception as e:
        logging.error(f"❗ Erreur inattendue pour la station {station_id} : {e}")

    return None, []


def enrichir_transmetteurs_avec_stats(transmitters, api_token):
    """Ajoute les stats (success_rate, good_count) à chaque transmetteur via un fetch global
       avec pagination. Applique aussi un filtre success_rate min, et sélectionne 1 transmetteur
       max par satellite.
    """
    try:
        tqdm.write("📊 Téléchargement global des stats de transmetteurs depuis SatNOGS Network...")

        url = "https://network.satnogs.org/api/transmitters/"
        all_tx_data = get_paginated_endpoint(url, token=api_token)

        # Map des stats par uuid
        stats_map = {
            tx["uuid"]: tx.get("stats", {}) for tx in all_tx_data if "uuid" in tx
        }

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

            if FILTER_TX_SUCCESS_RATE_MIN is not None:
                if sr is None or sr < FILTER_TX_SUCCESS_RATE_MIN:
                    continue

            transmitters_by_sat.setdefault(norad, []).append(tx)

        best_transmitters = {}
        for norad, tx_list in transmitters_by_sat.items():
            def tri_qualite(tx):
                return (
                    tx.get("success_rate") or 0,
                    tx.get("good_count") or 0
                )
            meilleur = sorted(tx_list, key=tri_qualite, reverse=True)[0]
            best_transmitters[meilleur['uuid']] = meilleur

        logging.info(f"✅ Transmetteurs retenus après filtrage & sélection (1/sat) : {len(best_transmitters)}")
        return best_transmitters

    except Exception as e:
        logging.error(f"❌ Erreur récupération bulk des stats : {e}")
        return transmitters


def filtrer_passages_sans_chevauchement(passages):
    passages = sorted(passages, key=lambda p: p['AOS'])
    selection = []

    for p in passages:
        overlap = False
        for s in selection:
            # Seul cas d'exclusion : vrai chevauchement
            if p['AOS'] < s['LOS'] and p['LOS'] > s['AOS']:
                overlap = True
                break

        if not overlap:
            selection.append(p)

    logging.info(f"📆 Passages sélectionnés sans chevauchement : {len(selection)} (sur {len(passages)} initiaux)")
    return sorted(selection, key=lambda p: p['AOS'])


def programmer_observations_satnogs(passages, station_id, api_token, start_time, end_time):
    """
    Programme les observations sur SatNOGS Network et affiche un résumé clair,
    incluant les observations déjà planifiées (409), la durée, les taux de succès,
    le nombre de satellites et transmetteurs uniques, etc.
    """
    url = "https://network.satnogs.org/api/observations/"
    headers = {
        "Authorization": f"Token {api_token}",
        "Content-Type": "application/json"
    }

    durations = []
    success_rates = []
    satellites_programmes = set()
    transmetteurs_programmes = set()

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

            drifted_freq_mhz = freq_mhz
            if freq and drift_ppb:
                drifted_freq_mhz = (freq * (1 + drift_ppb / 1e9)) / 1_000_000

            duration_sec = (p["LOS"] - p["AOS"]).total_seconds()
            if duration_sec < MIN_OBSERVATION_DURATION_SEC:
                logging.debug(f"⏳ Passage ignoré ({sat_name}) — durée trop courte ({duration_sec:.1f}s)")
                continue

            start_str = p["AOS"].strftime("%Y-%m-%d %H:%M:%S")
            end_str = p["LOS"].strftime("%Y-%m-%d %H:%M:%S")

            payload = [{
                "ground_station": int(station_id),
                "transmitter_uuid": uuid,
                "start": start_str,
                "end": end_str
            }]

            response = requests.post(url, headers=headers, json=payload)

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

            if response.status_code in (200, 201, 409):
                durations.append(duration_sec)
                satellites_programmes.add(norad_id)
                transmetteurs_programmes.add(uuid)
                if sr is not None:
                    success_rates.append(sr)

        except Exception as e:
            logging.error(f"❌ Exception durant la programmation de {p.get('SAT_NAME', '?')} : {e}")

    # ✅ Résumé final
    total_req = (end_time - start_time).total_seconds()
    total_obs = sum(durations)
    taux_succes_moyen = round(sum(success_rates) / len(success_rates), 1) if success_rates else 0.0

    logging.info("📊 Résumé final de la programmation :")
    logging.info(f"⏱  Période demandée : {int(total_req // 60)} min {int(total_req % 60)} sec")
    logging.info(f"⌛  Durée totale des observations (programmées ou déjà existantes) : {int(total_obs // 60)} min {int(total_obs % 60)} sec")
    logging.info(f"🛰️  Nombre total de satellites concernés : {len(satellites_programmes)}")
    logging.info(f"🔢 Nombre de satellites uniques : {len(set(satellites_programmes))}")
    logging.info(f"📡 Nombre de transmetteurs uniques : {len(set(transmetteurs_programmes))}")
    logging.info(f"📈  Taux de succès moyen des transmetteurs : {taux_succes_moyen:.1f}%")




def get_paginated_endpoint(url,
                           max_entries=None,
                           token=None,
                           max_retries=0,
                           filter_output_callback=None,
                           stop_criterion_callback=None,
                           timeout=10):
    """
    Fetch data from a paginated SatNOGS API endpoint.

    Args:
        url (str): Base URL of the endpoint.
        max_entries (int, optional): Max number of entries to retrieve.
        token (str, optional): API Token for Authorization.
        max_retries (int): Max number of retries on network failures.
        filter_output_callback (function, optional): A function to process/filter results.
        stop_criterion_callback (function, optional): A function to stop early based on results.
        timeout (int): Timeout per request in seconds.
    Returns:
        list: Aggregated list of results from all pages.
    """
    try:
        session = requests.Session()
        session.mount('https://', requests.adapters.HTTPAdapter(max_retries=max_retries))

        headers = {'Authorization': f'Token {token}'} if token else None

        data = []
        while url:
            response = session.get(url=url, headers=headers, timeout=timeout)
            response.raise_for_status()

            new_data = response.json()
            if filter_output_callback:
                new_data = filter_output_callback(new_data)

            data.extend(new_data)

            if stop_criterion_callback and stop_criterion_callback(new_data):
                break

            url = response.links.get('next', {}).get('url')

            if max_entries and len(data) >= max_entries:
                break

        return data

    except requests.HTTPError as e:
        logger.error(f'🌐 API HTTP error for {url}: {e}')
    except requests.exceptions.RequestException as e:
        logger.error(f'🌐 API request exception for {url}: {e}')
    except Exception as e:
        logger.error(f'🌐 Unexpected error with {url}: {e}')

    return []


# ------------------------ SCRIPT PRINCIPAL ------------------------

def main():
    logging.info("🚀 Lancement du calcul des passages satellites visibles...")

    try:
        # ============================================================
        # 📡 1. Récupération des infos de la station (et antennes)
        # ============================================================
        station_info, antenna_ranges = get_station_info(station_id, api_token)
        if not station_info:
            logging.critical("❌ Impossible de récupérer les infos de la station. Arrêt.")
            return

        # ============================================================
        # 🛰️ 2. Récupération des satellites filtrés (status + exclusion nom)
        # ============================================================
        satellites = get_satellites_actifs(
            status_filter=FILTER_SAT_STATUS,
            exclude_names=EXCLUDE_SAT_NAMES
        )
        if not satellites:
            logging.critical("❌ Aucun satellite valide trouvé. Arrêt.")
            return

        logging.info(f"✅ {len(satellites)} satellites retenus après filtrage.")

        # ============================================================
        # 📄 3. Récupération des TLEs pour les satellites
        # ============================================================
        tle_dict = get_all_tles()
        if not tle_dict:
            logging.critical("❌ Impossible de récupérer les TLEs. Arrêt.")
            return
        logging.info(f"✅ {len(tle_dict)} TLEs récupérés.")

        # ============================================================
        # 📡 4. Récupération et filtrage des transmetteurs
        # ============================================================
        transmitters_filtres = get_all_transmitters(
            alive_filter=FILTER_TX_ALIVE,
            status_filter=FILTER_TX_STATUS,
            no_freq_violation=FILTER_TX_NO_FREQ_VIOLATION,
            modes=FILTER_TX_MODES,
            antenna_ranges=antenna_ranges
        )
        if not transmitters_filtres:
            logging.critical("❌ Aucun transmetteur retenu après filtrage. Arrêt.")
            return

        # ============================================================
        # 📈 5. Enrichissement des transmetteurs avec stats réseau
        # ============================================================
        transmitters = enrichir_transmetteurs_avec_stats(transmitters_filtres, api_token)
        if not transmitters:
            logging.critical("❌ Enrichissement des transmetteurs échoué. Arrêt.")
            return
        logging.info(f"✅ {len(transmitters)} transmetteurs enrichis.")

        # ============================================================
        # ⏱️ 6. Calcul de la période d’observation
        # ============================================================
        start_time = datetime.utcnow().replace(tzinfo=utc) + DELAI_DEPART
        end_time = start_time + DUREE_OBSERVATION
        logging.info(f"🕒 Observation de {start_time} ➡ {end_time} UTC")

        # ============================================================
        # 📉 7. Calcul des passages visibles
        # ============================================================
        passages_bruts = calculer_tous_les_passages(satellites, tle_dict, position, start_time, end_time)
        if not passages_bruts:
            logging.warning("⚠️ Aucun passage trouvé dans la période définie.")
            return

        # ============================================================
        # 🔗 8. Lier les transmetteurs aux passages
        # ============================================================
        passages_avec_tx = lier_transmetteurs_aux_passages(passages_bruts, transmitters)
        if not passages_avec_tx:
            logging.warning("⚠️ Aucun passage avec transmetteur associé.")
            return

        afficher_passages_satellites(passages_avec_tx)

        # ============================================================
        # 📆 9. Filtrage des passages sans chevauchement
        # ============================================================
        passages_filtres = filtrer_passages_sans_chevauchement(passages_avec_tx)
        if not passages_filtres:
            logging.warning("⚠️ Aucun passage retenu après suppression des chevauchements.")
            return

        afficher_passages_satellites(passages_filtres)

        # ============================================================
        # 🗓️ 10. Programmation des observations
        # ============================================================
        programmer_observations_satnogs(passages_filtres, station_id, api_token, start_time, end_time)

        
    except Exception as e:
        logging.critical(f"💥 Erreur critique durant le traitement : {e}")


if __name__ == "__main__":
    main()
