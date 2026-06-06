# AlternTrack

Application web Flask pour suivre ses candidatures en alternance.
Accès protégé par login. Un seul compte admin.

## Stack
- Python + Flask + Flask-Login
- SQLite
- Gemini 1.5 Flash (fallback Groq)
- Bootstrap 5 (français)

## Fichiers
- `app.py` → routes Flask
- `database.py` → SQLite CRUD
- `ai_extractor.py` → appel Gemini/Groq
- `templates/` → login, index, ajouter, detail
- `.env` → clés API et credentials admin

## Base de données
Table `candidatures` : id, entreprise, poste, type_contrat, localisation,
date_candidature, lien_offre (optionnel), statut, notes, date_mise_a_jour

Statuts : En attente / Entretien planifié / Retenu / Refusé / Sans réponse

## Authentification
Toutes les pages redirigent vers /login si non connecté.
Credentials définis dans .env : ADMIN_USERNAME, ADMIN_PASSWORD

## Lancement
source venv/bin/activate
python app.py
→ http://localhost:5000
