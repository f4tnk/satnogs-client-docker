# 🚀 SatNOGS Scheduler Script

## 📝 Description

Ce script Python permet de récupérer les données des satellites, de leurs transmetteurs et des éléments de TLE, puis de planifier automatiquement des observations pour une station SatNOGS. Le script se base sur l'API de SatNOGS pour planifier les observations des satellites visibles à une station donnée en fonction de leur élévation et de la disponibilité des transmetteurs.

### Fonctionnalités principales :
- 📡 **Récupération des données SatNOGS** : Récupère les informations sur les satellites, les transmetteurs et les éléments de TLE.
- 🌍 **Sélection des passes visibles** : Filtre les passes visibles des satellites en fonction de l'heure, de l'élévation minimale et de la durée du passage.
- 📅 **Planification des observations** : Planifie des observations à l'aide de l'API de SatNOGS, en tenant compte des fréquences des transmetteurs et des plages autorisées.
- ⚠️ **Gestion des erreurs de chevauchement** : Les passes en chevauchement avec des observations déjà planifiées sont gérées et comptabilisées avec un log spécifique.
- ⛰️ **Sélection de la passe avec la meilleure score* : Parmi les passes en chevauchement, sélectionne celle ayant la meilleure élévation et le meilleur transmitteur score, sans violationde fréquence

---

## ⚙️ Prérequis

1. Python 3.6+.
2. Installer les bibliothèques nécessaires avec `pip` :
   ```bash
   pip install requests tqdm skyfield python-dotenv dateutil
