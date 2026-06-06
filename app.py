"""AlternTrack : application Flask de suivi des candidatures en alternance.

Accès protégé par login (un seul compte admin défini dans .env).
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

import database
from ai_extractor import extraire_candidature

load_dotenv()

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Statuts possibles d'une candidature (cf. README).
STATUTS = [
    "En attente",
    "Entretien planifié",
    "Retenu",
    "Refusé",
    "Sans réponse",
]

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24).hex())

login_manager = LoginManager(app)
login_manager.login_view = "login"


class Admin(UserMixin):
    """Unique utilisateur de l'application."""

    id = "admin"


@login_manager.user_loader
def load_user(user_id):
    """Recharge l'utilisateur admin à partir de son identifiant de session."""
    if user_id == Admin.id:
        return Admin()
    return None


# --- Authentification --------------------------------------------------------


@app.route("/login", methods=["GET"])
def login():
    """Affiche le formulaire de connexion."""
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login_post():
    """Vérifie les identifiants et connecte l'utilisateur."""
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        login_user(Admin())
        return redirect(url_for("index"))

    flash("Identifiants incorrects.", "danger")
    return redirect(url_for("login"))


@app.route("/logout")
@login_required
def logout():
    """Déconnecte l'utilisateur et revient à la page de connexion."""
    logout_user()
    return redirect(url_for("login"))


# --- Tableau de bord ---------------------------------------------------------


@app.route("/")
@login_required
def index():
    """Affiche toutes les candidatures, avec filtre optionnel par statut."""
    statut = request.args.get("statut")
    toutes = database.get_toutes_candidatures()

    if statut:
        candidatures = [c for c in toutes if c["statut"] == statut]
    else:
        candidatures = toutes

    return render_template(
        "index.html",
        toutes=toutes,
        candidatures=candidatures,
        statuts=STATUTS,
        statut_actif=statut,
    )


# --- Ajout d'une candidature -------------------------------------------------


@app.route("/ajouter", methods=["GET"])
@login_required
def ajouter():
    """Affiche le formulaire d'ajout (saisie du texte brut de l'offre)."""
    return render_template("ajouter.html", statuts=STATUTS)


@app.route("/ajouter", methods=["POST"])
@login_required
def ajouter_post():
    """Reçoit le texte brut, appelle l'IA et renvoie le JSON extrait."""
    texte = request.form.get("texte") or (request.json or {}).get("texte", "")

    if not texte or not texte.strip():
        return jsonify({"erreur": "Aucun texte fourni."}), 400

    data = extraire_candidature(texte)
    if data is None:
        return jsonify({"erreur": "L'extraction a échoué."}), 502

    return jsonify(data)


def _convertir_date(valeur):
    """Convertit une date DD/MM/YYYY en YYYY-MM-DD pour le stockage."""
    valeur = (valeur or "").strip()
    if not valeur:
        return ""
    try:
        return datetime.strptime(valeur, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return valeur


@app.route("/confirmer", methods=["POST"])
@login_required
def confirmer():
    """Enregistre la candidature confirmée par l'utilisateur."""
    data = {
        "entreprise": request.form.get("entreprise", "").strip(),
        "poste": request.form.get("poste", "").strip(),
        "type_contrat": request.form.get("type_contrat", "").strip(),
        "localisation": request.form.get("localisation", "").strip(),
        "date_candidature": _convertir_date(request.form.get("date_candidature", "")),
        "lien_offre": (request.form.get("lien_offre") or "").strip() or None,
        "statut": request.form.get("statut", "En attente").strip() or "En attente",
        "notes": request.form.get("notes", "").strip(),
    }

    nouvel_id = database.ajouter_candidature(data)
    flash("Candidature enregistrée.", "success")
    return redirect(url_for("detail", id=nouvel_id))


# --- Détail et modifications -------------------------------------------------


@app.route("/candidature/<int:id>")
@login_required
def detail(id):
    """Affiche le détail d'une candidature."""
    candidature = database.get_candidature(id)
    if candidature is None:
        flash("Candidature introuvable.", "danger")
        return redirect(url_for("index"))
    return render_template(
        "detail.html", candidature=candidature, statuts=STATUTS
    )


@app.route("/candidature/<int:id>/statut", methods=["POST"])
@login_required
def changer_statut(id):
    """Modifie le statut d'une candidature."""
    statut = request.form.get("statut", "").strip()
    if statut:
        database.modifier_statut(id, statut)
        flash("Statut mis à jour.", "success")
    return redirect(url_for("detail", id=id))


@app.route("/candidature/<int:id>/notes", methods=["POST"])
@login_required
def changer_notes(id):
    """Modifie les notes d'une candidature."""
    notes = request.form.get("notes", "").strip()
    database.modifier_notes(id, notes)
    flash("Notes mises à jour.", "success")
    return redirect(url_for("detail", id=id))


@app.route("/candidature/<int:id>/entretien", methods=["POST"])
@login_required
def changer_entretien(id):
    """Modifie la date et l'heure d'entretien d'une candidature."""
    date_entretien = request.form.get("date_entretien", "").strip()
    database.modifier_entretien(id, date_entretien or None)
    flash("Entretien mis à jour.", "success")
    return redirect(url_for("detail", id=id))


@app.route("/candidature/<int:id>/supprimer", methods=["POST"])
@login_required
def supprimer(id):
    """Supprime une candidature."""
    database.supprimer_candidature(id)
    flash("Candidature supprimée.", "success")
    return redirect(url_for("index"))


# --- Démarrage ---------------------------------------------------------------

database.init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
