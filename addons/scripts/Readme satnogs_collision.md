# 🛰️ SatNOGS Satellite signal collision

## 📝 Description

Ce script Python permet de récupérer les données des observations planifiées via l'API SatNOGS, puis d'analyser et calculer les passages des satellites en fonction des paramètres spécifiés par l'utilisateur (ID d'observation, plage de fréquence, etc.). Les résultats sont ensuite affichés sous forme de tableau et exportés en fichier JSON.

### Fonctionnalités principales :
- 📡 **Récupération des données d'observation** : Le script récupère la fréquence, les dates de début et de fin de l'observation, ainsi que la position de la station depuis l'API SatNOGS.
- 🛰️ **Calcul des passages des satellites** : Pour chaque satellite, le script calcule les passages visibles, leur élévation maximale et leur durée.
- 🔍 **Filtrage par fréquence** : Les satellites sont filtrés en fonction de la fréquence des transmetteurs, avec la possibilité de spécifier une plage de fréquence.
- 📈 **Affichage des résultats sous forme de tableau** : Les résultats sont affichés sous forme de DataFrame et peuvent être triés par date de début des passages.
- 💾 **Export des résultats en JSON** : Le script exporte les résultats sous forme de fichier JSON pour une utilisation ultérieure.

---

## ⚙️ Prérequis

1. **Python 3.6+**.
2. Installer les bibliothèques nécessaires avec `pip` :
   ```bash
   pip install requests tqdm skyfield pandas python-dotenv