# AlternTrack

> Application web de suivi de candidatures en alternance, propulsée par l'IA.

🔗 **Live** : https://alterntrack.onrender.com

## Stack

Python · Flask · SQLite · Gemini · Groq · Bootstrap 5 · Render

## Fonctionnalités

- Ajout de candidatures par description en langage naturel (IA)
- Tableau de bord avec filtres et compteurs
- Suivi des entretiens
- Export PDF pour le tuteur
- Accès sécurisé par login
- Responsive mobile

## Lancement local

```bash
git clone https://github.com/bilal-allouch/alterntrack.git
cd alterntrack
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Créer un fichier `.env` à la racine avec :

```env
GEMINI_API_KEY=...
GROQ_API_KEY=...
ADMIN_USERNAME=...
ADMIN_PASSWORD=...
SECRET_KEY=...
```
