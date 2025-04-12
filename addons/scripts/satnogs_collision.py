import os
import json
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd
from skyfield.api import Loader, EarthSatellite, wgs84, utc
from dotenv import load_dotenv

# ===============================================
# Chargement des variables d'environnement (au cas où, elles seront remplacées par l'observation)
# ===============================================
load_dotenv(".env")

# On définit des valeurs par défaut éventuelles
latitude = float(os.getenv("SATNOGS_STATION_LAT", 0))
longitude = float(os.getenv("SATNOGS_STATION_LON", 0))
altitude = float(os.getenv("SATNOGS_STATION_ELEV", 0))

# Les variables frequency_mhz, date_start et date_end seront récupérées dynamiquement depuis l'API observation
frequency_mhz = None
date_start = None
date_end = None
frequency_range_khz = 25

satellite_excluded = []  # Exemple : [12345, 67890]

# ===============================================
# Fonction de récupération des données d'observation
# ===============================================
def fetch_observation_data(obs_id):
    """
    Récupère les données de l'observation via l'API SatNOGS et renvoie :
      - la fréquence (en MHz) extraite depuis "observation_frequency" (ou "frequency" en secours),
      - la date de début (start) et la date de fin (end) avec le "Z" remplacé par "+00:00",
      - la latitude, la longitude et l'élévation issues de l'observation.
    """
    try:
        url = f"https://network.satnogs.org/api/observations/{obs_id}/?format=json"
        print(f"[LOG] Récupération des données d'observation depuis : {url}")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Récupération et conversion de la fréquence (en Hz) en MHz
        freq = data.get("observation_frequency")
        if freq is None:
            freq = data.get("frequency")
        if freq is not None:
            frequency_mhz_obs = freq / 1e6
        else:
            frequency_mhz_obs = None

        # Récupération des dates start/end et remplacement du "Z" par "+00:00" pour la compatibilité ISO
        date_start_obs = data.get("start")
        date_end_obs = data.get("end")
        if date_start_obs and date_start_obs.endswith("Z"):
            date_start_obs = date_start_obs.replace("Z", "+00:00")
        if date_end_obs and date_end_obs.endswith("Z"):
            date_end_obs = date_end_obs.replace("Z", "+00:00")

        # Récupération des paramètres de position
        station_lat = data.get("station_lat")
        station_lng = data.get("station_lng")
        station_alt = data.get("station_alt")

        return frequency_mhz_obs, date_start_obs, date_end_obs, station_lat, station_lng, station_alt
    except Exception as e:
        print(f"[LOG] Erreur lors de la récupération de l'observation {obs_id} : {e}")
        return None, None, None, None, None, None

# ===============================================
# Partie B : Données SatNOGS et calcul des passages
# ===============================================
def fetch_satnogs_transmitters(frequency_mhz, freq_range_khz):
    try:
        # Calcul de la plage en Hz en se basant sur la fréquence en MHz
        freq_min = int((frequency_mhz - freq_range_khz / 1000) * 1e6)
        freq_max = int((frequency_mhz + freq_range_khz / 1000) * 1e6)
        print(f"[LOG] SatNOGS - Recherche des transmetteurs entre {freq_min} Hz et {freq_max} Hz.")
        
        url = 'https://db.satnogs.org/api/transmitters/?format=json'
        all_transmitters = []
        while url:
            print(f"[LOG] SatNOGS - Appel URL transmetteurs : {url}")
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if 'results' in data:
                all_transmitters.extend(data['results'])
                url = data.get('next')
            else:
                all_transmitters = data
                url = None

        filtered = [
            tx for tx in all_transmitters 
            if tx.get('downlink_low') is not None and freq_min <= tx['downlink_low'] <= freq_max
        ]
        return filtered
    except Exception as e:
        print(f"[LOG] Erreur dans fetch_satnogs_transmitters : {e}")
        return []

def fetch_satellite(norad_id):
    try:
        url = f'https://db.satnogs.org/api/satellites/{norad_id}/?format=json'
        print(f"[LOG] SatNOGS - Appel URL satellite : {url}")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list):
            return data[0] if data else {}
        elif isinstance(data, dict):
            return data
        else:
            return {}
    except Exception as e:
        print(f"[LOG] SatNOGS - Erreur lors de la récupération du satellite {norad_id} : {e}")
        return {}

def fetch_tle_by_id(norad_id):
    try:
        url = f'https://db.satnogs.org/api/tle/?norad_cat_id={norad_id}&format=json'
        print(f"[LOG] SatNOGS - Appel URL TLE : {url}")
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            entry = data[0]
        elif isinstance(data, dict):
            entry = data
        else:
            return None
        return (
            entry.get('tle0'),
            entry.get('tle1'),
            entry.get('tle2'),
            entry.get('tle_source', ''),
            entry.get('updated', '')
        )
    except Exception as e:
        print(f"[LOG] SatNOGS - Erreur lors de la récupération du TLE pour {norad_id} : {e}")
        return None

def find_passes(satellite, observer, ts, t_start, t_end):
    try:
        t0 = ts.utc(t_start.replace(tzinfo=utc))
        t1 = ts.utc(t_end.replace(tzinfo=utc))
        times, events = satellite.find_events(observer, t0, t1, altitude_degrees=10.0)
        passes = []
        pass_start = None
        max_elev = None
        for ti, event in zip(times, events):
            if event == 0:
                pass_start = ti
            elif event == 1:
                satpos = satellite.at(ti)
                obspos = observer.at(ti)
                difference = satpos - obspos
                alt, az, distance = difference.altaz()
                max_elev = alt.degrees
                print(f"[LOG] Skyfield - Altitude à {ti.utc_datetime()} : {max_elev:.2f}°")
            elif event == 2:
                if pass_start is None:
                    continue
                pass_end = ti
                duration = (pass_end.utc_datetime() - pass_start.utc_datetime()).total_seconds()
                passes.append((pass_start.utc_datetime(), pass_end.utc_datetime(), max_elev, duration))
        return passes
    except Exception as e:
        print(f"[LOG] Erreur dans find_passes : {e}")
        return []

def compute_satellite_passes():
    try:
        loader = Loader('./skyfield_data')
        ts = loader.timescale()
        observer = wgs84.latlon(latitude, longitude, altitude)
        transmitters = fetch_satnogs_transmitters(frequency_mhz, frequency_range_khz)
        results = []
        # Conversion des dates récupérées en objets datetime
        t_start = datetime.fromisoformat(date_start)
        t_end   = datetime.fromisoformat(date_end)
        
        for tx in transmitters:
            norad_id = tx.get('norad_cat_id')
            if norad_id is None or norad_id in satellite_excluded:
                continue
            try:
                norad_id = int(norad_id)
            except Exception:
                continue

            sat_info = fetch_satellite(norad_id)
            tle_data = fetch_tle_by_id(norad_id)
            if not sat_info or not tle_data:
                continue

            sat_name   = sat_info.get('name', 'N/A')
            sat_status = sat_info.get('status', 'N/A')

            print(f"\n[LOG] SatNOGS - Transmetteur NORAD ID: {norad_id} - Satellite : {sat_name} | Status: {sat_status} | Source TLE : {tle_data[3]} | Updated : {tle_data[4]}")
            
            if tx.get('downlink_low') is not None:
                downlink_mhz = float(tx.get('downlink_low')) / 1e6
                downlink_mhz = "{:.3f}".format(downlink_mhz)
            else:
                downlink_mhz = "N/A"
            description = tx.get('description', 'N/A')
            mode = tx.get('mode', 'N/A')
            
            satellite_obj = EarthSatellite(tle_data[1], tle_data[2], tle_data[0], ts)
            passes = find_passes(satellite_obj, observer, ts, t_start, t_end)
            for p in passes:
                results.append({
                    'norad_id': norad_id,
                    'satellite_name': sat_name,
                    # Le champ satellite_names a été supprimé
                    'satellite_status': sat_status,
                    'transmitter_uuid': tx.get('uuid'),
                    'transmitter_downlink_mhz': downlink_mhz,
                    'transmitter_description': description,
                    'mode': mode,
                    'frequency_mhz': float(tx.get('frequency', 0) or 0) / 1e6,
                    'pass_start': p[0],
                    'pass_end': p[1],
                    'max_elevation_deg': round(p[2], 2),
                    'duration_sec': int(p[3]),
                    'tle_source': tle_data[3],
                    'tle_updated': tle_data[4]
                })

        df = pd.DataFrame(results)
        if not df.empty and 'pass_start' in df.columns:
            df = df.sort_values('pass_start')
        else:
            print("[LOG] SatNOGS - Aucun passage calculé pour les satellites.")
        return df

    except Exception as e:
        print(f"[LOG] SatNOGS - Erreur dans compute_satellite_passes : {e}")
        return pd.DataFrame()

# ===============================================
# Exécution du script principal
# ===============================================
if __name__ == '__main__':
    # Saisie de l'ID de l'observation
    obs_id_input = input("Entrez l'ID de l'observation (ex: 11390361) : ")
    try:
        observation_id = int(obs_id_input)
    except Exception as e:
        print("Erreur lors de la conversion de l'ID d'observation :", e)
        exit(1)
    
    # Saisie de la plage en kHz pour filtrer les transmetteurs
    range_input = input("Entrez la plage en kHz (ex: 25) : ")
    try:
        frequency_range_khz = float(range_input)
    except Exception as e:
        print("Erreur lors de la conversion de la plage en kHz :", e)
        exit(1)
    
    # Récupération des données d'observation (fréquence, dates, et position)
    freq_obs, date_start_obs, date_end_obs, obs_lat, obs_lng, obs_alt = fetch_observation_data(observation_id)
    if freq_obs is None or date_start_obs is None or date_end_obs is None or obs_lat is None or obs_lng is None or obs_alt is None:
        print("Erreur lors de la récupération des données de l'observation.")
        exit(1)
    
    # Mise à jour des variables globales avec les données récupérées
    frequency_mhz = freq_obs
    date_start = date_start_obs
    date_end = date_end_obs

    try:
        latitude = float(obs_lat)
        longitude = float(obs_lng)
        altitude = float(obs_alt)
    except Exception as e:
        print(f"[LOG] Erreur lors du traitement de la position : {e}")
        exit(1)
    
    print(f"[LOG] Observation récupérée : Frequency = {frequency_mhz} MHz, date_start = {date_start}, date_end = {date_end}")
    print(f"[LOG] Position de l'observation : Latitude = {latitude}, Longitude = {longitude}, Altitude = {altitude}")
    
    print("\n=== Partie 1 : Passages satellites (SatNOGS) ===\n")
    df = compute_satellite_passes()
    print("\n=== Résultat Final (SatNOGS) ===\n")
    print(df)
    
    # Export du DataFrame en fichier JSON
    if not df.empty:
        output_filename = "resultats.json"
        df.to_json(output_filename, orient="records", date_format="iso", indent=4)
        print(f"\n[LOG] Le résultat a été enregistré dans le fichier {output_filename}.")
    else:
        print("\n[LOG] Aucun résultat à enregistrer dans le fichier JSON.")
