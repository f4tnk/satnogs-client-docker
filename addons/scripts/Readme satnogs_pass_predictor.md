# 🛰️ SatNOGS Auto-Scheduler

Un script Python avancé permettant de **détecter**, **filtrer** et **planifier automatiquement** des observations satellites sur le réseau [SatNOGS](https://network.satnogs.org/).

Ce projet est conçu pour fonctionner de façon autonome avec votre station SatNOGS, en respectant vos contraintes (fréquences, modes, élévation, etc.) et en s’appuyant sur les données du réseau SatNOGS.

---

## 🚀 Fonctionnalités principales

- 🔭 Calcul des passages visibles pour votre station avec la bibliothèque Skyfield
- 🛰️ Téléchargement et filtrage des TLEs, satellites et transmetteurs SatNOGS
- 🧠 Association intelligente entre satellite, transmetteur, fréquence et élévation
- 🔁 Filtrage avancé :
  - Par élévation minimum
  - Par modes (USB, FSK, etc.)
  - Par plage de fréquence des antennes de la station
  - Par taux de succès (`success_rate`) des observations précédentes
  - Par récence du lancement du satellite
  - Par exclusion de mots-clés dans le nom du satellite
- 🔗 Programmation automatique sur le réseau SatNOGS (`/api/observations/`)
- 🧾 Résumé final clair : temps observé, taux de succès moyen, satellites planifiés
- 📦 Journalisation complète dans un fichier log

---

## 🧰 Pré-requis

- Python 3.8+
- Compte sur [network.satnogs.org](https://network.satnogs.org)
- Une station SatNOGS configurée
- Clé API SatNOGS (depuis votre profil utilisateur)

---

## 🔧 Installation

1. Clonez le dépôt :

```bash
git clone https://github.com/votre-utilisateur/satnogs-auto-scheduler.git
cd satnogs-auto-scheduler
```

2. Installez les dépendances :

```bash
pip install -r requirements.txt
```

3. Configurez votre environnement dans `station.env` :

```env
SATNOGS_STATION_ID=1234
SATNOGS_API_TOKEN=VotreTokenIci
SATNOGS_STATION_LAT=43.81477
SATNOGS_STATION_LON=4.06576
SATNOGS_STATION_ELEV=52
```

---

## ⚙️ Paramètres principaux (en haut du script)

```python
SEUIL_ELEVATION = 15
FILTER_TX_ALIVE = True
FILTER_TX_NO_FREQ_VIOLATION = True
FILTER_TX_MODES = ["FSK", "MSK", "PSK"]
FILTER_TX_SUCCESS_RATE_MIN = 10
EXCLUDE_SAT_NAMES = ["SITRO", "KINE"]
SAT_RECENT_LAUNCH_DAYS = 30
```

---

## 📈 Exécution

Lancez le script principal :

```bash
python script.py
```

Les journaux seront affichés dans la console et enregistrés dans :

```text
satellite_passes.log
```

---

## 📄 Extrait de sortie

```text
📍 Station 3762 — lat=43.81477, lon=4.06576, elev=52.0 m
✅ Satellites 'alive' retenus : 1421
🎯 Transmetteurs totaux dans l'API : 4114
📊 Transmetteurs correspondant à chaque filtre :
   - alive=True : 3124 transmetteurs
   - frequency_violation=False : 2801 transmetteurs
   - mode contient ['FSK', 'MSK', 'PSK'] : 1745 transmetteurs
   - fréquence dans plage antenne : 1562 transmetteurs
✅ Transmetteurs retenus après tous filtres : 843

🛰 Satellite : UPMSat 2 (NORAD 44387)
  AOS : 2025-04-14 18:12:40 UTC
  MAX : 2025-04-14 18:15:12 UTC
  LOS : 2025-04-14 18:17:43 UTC
  Durée : 0:05:03
  Élévation max : 45.6°
    📡 FSK @ 437.345 MHz | good=43 | success=85%

🗓️ Observation planifiée → UPMSat 2 | ⏰ 18:12:40 ➡ 18:17:43 UTC | 🕒 Durée : 5 min 3 sec | 📡 FSK @ 437.345 MHz | 📈 Élév. max : 45.6° | ✅ Success Rate : 85%

📊 Résumé final de la programmation :
⏱️  Période demandée : 1 h 0 min
⌛  Durée totale des observations : 16 min 25 sec
🛰️  Nombre total de satellites concernés : 4
📈  Taux de succès moyen des transmetteurs : 81.7%
```

---

## 🔐 Notes de sécurité

- Votre `SATNOGS_API_TOKEN` est sensible, ne le partagez jamais publiquement.
- N'oubliez pas d’ajouter `station.env` à votre `.gitignore`.

---

## 👨‍💻 Auteur

Développé avec ❤️ par **@f4tnk**  
Adapté pour usage personnel ou communautaire avec station SatNOGS.

---

## 📜 Licence

Ce projet est sous licence MIT — libre à utiliser, adapter, redistribuer.  
Toute amélioration ou contribution est bienvenue !