"""AlternTrack : application Flask de suivi des candidatures en alternance.

Accès protégé par login (un seul compte admin défini dans .env).
"""

import os
from datetime import datetime
from io import BytesIO

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
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
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Paragraph,
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


class User(UserMixin):
    """Utilisateur de l'application chargé depuis la table users."""

    def __init__(self, id, username, is_admin):
        self.id = id
        self.username = username
        self.is_admin = is_admin


@login_manager.user_loader
def load_user(user_id):
    """Recharge l'utilisateur à partir de son identifiant de session."""
    try:
        row = database.get_utilisateur_par_id(int(user_id))
    except (ValueError, TypeError):
        return None
    if row is None:
        return None
    return User(row["id"], row["username"], row["is_admin"])


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

    if database.verifier_password(username, password):
        row = database.get_utilisateur_par_username(username)
        login_user(User(row["id"], row["username"], row["is_admin"]))
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
    toutes = database.get_toutes_candidatures(current_user.id)

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
    source = request.form.get("source", "").strip()
    if source == "Autre":
        source = request.form.get("source_autre", "").strip() or "Autre"

    type_candidature = request.form.get("type_candidature", "").strip() or "Offre publiée"

    data = {
        "entreprise": request.form.get("entreprise", "").strip(),
        "poste": request.form.get("poste", "").strip(),
        "type_contrat": request.form.get("type_contrat", "").strip(),
        "localisation": request.form.get("localisation", "").strip(),
        "date_candidature": _convertir_date(request.form.get("date_candidature", "")),
        "lien_offre": (request.form.get("lien_offre") or "").strip() or None,
        "statut": request.form.get("statut", "En attente").strip() or "En attente",
        "notes": request.form.get("notes", "").strip(),
        "source": source,
        "type_candidature": type_candidature,
        "contact_nom": (request.form.get("contact_nom") or "").strip() or None,
        "contact_lien": (request.form.get("contact_lien") or "").strip() or None,
    }

    nouvel_id = database.ajouter_candidature(data, current_user.id)

    if request.form.get("enregistrer_entreprise") == "on":
        ent_nom = request.form.get("ent_nom", "").strip()
        if ent_nom:
            if database.get_entreprise_par_nom(ent_nom, current_user.id) is not None:
                flash("L'entreprise '%s' est déjà dans votre carnet." % ent_nom, "info")
            else:
                ent_data = {
                    "nom": ent_nom,
                    "lien": (request.form.get("ent_lien") or "").strip() or None,
                    "telephone": (request.form.get("ent_telephone") or "").strip() or None,
                    "email": (request.form.get("ent_email") or "").strip() or None,
                }
                database.ajouter_entreprise(ent_data, current_user.id)

    flash("Candidature enregistrée.", "success")
    return redirect(url_for("detail", id=nouvel_id))


# --- Détail et modifications -------------------------------------------------


@app.route("/candidature/<int:id>")
@login_required
def detail(id):
    """Affiche le détail d'une candidature."""
    candidature = database.get_candidature(id, current_user.id)
    if candidature is None:
        flash("Candidature introuvable.", "danger")
        return redirect(url_for("index"))
    return render_template(
        "detail.html", candidature=candidature, statuts=STATUTS
    )


@app.route("/candidature/<int:id>/modifier", methods=["POST"])
@login_required
def modifier(id):
    """Met à jour statut, notes et entretien d'une candidature en une fois."""
    statut = request.form.get("statut", "En attente").strip() or "En attente"
    notes = request.form.get("notes", "").strip()
    date_entretien = request.form.get("date_entretien", "").strip() or None
    database.modifier_candidature(id, statut, notes, date_entretien, current_user.id)
    flash("Candidature mise à jour.", "success")
    return redirect(url_for("detail", id=id))


@app.route("/candidature/<int:id>/supprimer", methods=["POST"])
@login_required
def supprimer(id):
    """Supprime une candidature."""
    database.supprimer_candidature(id, current_user.id)
    flash("Candidature supprimée.", "success")
    return redirect(url_for("index"))


# --- Carnet d'entreprises ----------------------------------------------------


@app.route("/entreprises", methods=["GET"])
@login_required
def entreprises():
    """Affiche le carnet d'entreprises de l'utilisateur."""
    liste = database.get_toutes_entreprises(current_user.id)
    return render_template("entreprises.html", entreprises=liste)


@app.route("/entreprises/ajouter", methods=["POST"])
@login_required
def entreprises_ajouter():
    """Enregistre une nouvelle entreprise."""
    data = {
        "nom": request.form.get("nom", "").strip(),
        "lien": (request.form.get("lien") or "").strip() or None,
        "telephone": (request.form.get("telephone") or "").strip() or None,
        "email": (request.form.get("email") or "").strip() or None,
    }
    if not data["nom"]:
        flash("Le nom de l'entreprise est requis.", "danger")
        return redirect(url_for("entreprises"))

    if database.get_entreprise_par_nom(data["nom"], current_user.id) is not None:
        flash("L'entreprise '%s' est déjà dans votre carnet." % data["nom"], "info")
        return redirect(url_for("entreprises"))

    database.ajouter_entreprise(data, current_user.id)
    flash("Entreprise enregistrée.", "success")
    return redirect(url_for("entreprises"))


@app.route("/entreprises/<int:id>/supprimer", methods=["POST"])
@login_required
def entreprises_supprimer(id):
    """Supprime une entreprise."""
    database.supprimer_entreprise(id, current_user.id)
    flash("Entreprise supprimée.", "success")
    return redirect(url_for("entreprises"))


@app.route("/api/entreprise/existe")
@login_required
def api_entreprise_existe():
    """Indique si une entreprise avec ce nom existe déjà pour l'utilisateur."""
    nom = request.args.get("nom", "").strip()
    if not nom:
        return jsonify({"existe": False})
    existe = database.get_entreprise_par_nom(nom, current_user.id) is not None
    return jsonify({"existe": existe})


# --- Administration des utilisateurs -----------------------------------------

MAX_USERS = 10


@app.route("/admin/users", methods=["GET"])
@login_required
def admin_users():
    """Affiche la liste des utilisateurs (réservé aux administrateurs)."""
    if not current_user.is_admin:
        abort(403)
    users = database.get_tous_utilisateurs()
    return render_template("admin.html", users=users, max_users=MAX_USERS)


@app.route("/admin/users", methods=["POST"])
@login_required
def admin_users_create():
    """Crée un nouvel utilisateur (réservé aux administrateurs)."""
    if not current_user.is_admin:
        abort(403)

    if len(database.get_tous_utilisateurs()) >= MAX_USERS:
        flash("Nombre maximum d'utilisateurs atteint (%d)." % MAX_USERS, "danger")
        return redirect(url_for("admin_users"))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    is_admin = request.form.get("is_admin") == "on"

    if not username or not password:
        flash("Nom d'utilisateur et mot de passe requis.", "danger")
        return redirect(url_for("admin_users"))

    nouvel_id = database.creer_utilisateur(username, password, is_admin)
    if nouvel_id is None:
        flash("Ce nom d'utilisateur est déjà pris.", "danger")
    else:
        flash("Utilisateur créé.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:id>/supprimer", methods=["POST"])
@login_required
def admin_users_delete(id):
    """Supprime un utilisateur, sauf soi-même (réservé aux administrateurs)."""
    if not current_user.is_admin:
        abort(403)
    if id == current_user.id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "danger")
        return redirect(url_for("admin_users"))
    database.supprimer_utilisateur(id)
    flash("Utilisateur supprimé.", "success")
    return redirect(url_for("admin_users"))


# --- Export PDF --------------------------------------------------------------


@app.route("/export/tuteur")
@login_required
def export_tuteur():
    """Génère un PDF récapitulatif des candidatures à envoyer au tuteur."""
    candidatures = database.get_toutes_candidatures_export(current_user.id)

    tampon = BytesIO()
    doc = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    titre_style = styles["Title"]
    titre_style.textColor = colors.black
    sous_titre_style = styles["Normal"]
    cellule_style = styles["BodyText"]
    cellule_style.fontSize = 9
    cellule_style.leading = 11

    elements = [
        Paragraph("Suivi des candidatures en alternance", titre_style),
        Spacer(1, 0.2 * cm),
        Paragraph(datetime.now().strftime("%d/%m/%Y"), sous_titre_style),
        Spacer(1, 0.6 * cm),
    ]

    entetes = [
        "Entreprise",
        "Poste",
        "Contrat",
        "Localisation",
        "Date",
        "Statut",
    ]
    donnees = [[Paragraph("<b>%s</b>" % e, cellule_style) for e in entetes]]

    for c in candidatures:
        donnees.append(
            [
                Paragraph(c.get("entreprise") or "", cellule_style),
                Paragraph(c.get("poste") or "", cellule_style),
                Paragraph(c.get("type_contrat") or "", cellule_style),
                Paragraph(c.get("localisation") or "", cellule_style),
                Paragraph(c.get("date_candidature") or "", cellule_style),
                Paragraph(c.get("statut") or "", cellule_style),
            ]
        )

    tableau = Table(
        donnees,
        colWidths=[3.5 * cm, 3.8 * cm, 2.2 * cm, 2.8 * cm, 2.2 * cm, 3.5 * cm],
        repeatRows=1,
    )
    tableau.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(tableau)

    doc.build(elements)
    tampon.seek(0)

    nom_fichier = "candidatures_%s.pdf" % datetime.now().strftime("%Y-%m-%d")
    return send_file(
        tampon,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nom_fichier,
    )


@app.route("/export/entreprises")
@login_required
def export_entreprises():
    """Génère un PDF du carnet d'entreprises."""
    liste = database.get_toutes_entreprises_export(current_user.id)

    tampon = BytesIO()
    doc = SimpleDocTemplate(
        tampon,
        pagesize=A4,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()
    titre_style = styles["Title"]
    titre_style.textColor = colors.black
    sous_titre_style = styles["Normal"]
    cellule_style = styles["BodyText"]
    cellule_style.fontSize = 9
    cellule_style.leading = 11

    elements = [
        Paragraph("Carnet d'entreprises", titre_style),
        Spacer(1, 0.2 * cm),
        Paragraph(datetime.now().strftime("%d/%m/%Y"), sous_titre_style),
        Spacer(1, 0.6 * cm),
    ]

    entetes = ["Entreprise", "Lien", "Téléphone", "Email", "Date"]
    donnees = [[Paragraph("<b>%s</b>" % e, cellule_style) for e in entetes]]

    for e in liste:
        date_ajout = (e.get("date_ajout") or "")[:10]
        if len(date_ajout) == 10:
            date_ajout = "%s/%s/%s" % (date_ajout[8:10], date_ajout[5:7], date_ajout[0:4])
        donnees.append(
            [
                Paragraph(e.get("nom") or "", cellule_style),
                Paragraph(e.get("lien") or "", cellule_style),
                Paragraph(e.get("telephone") or "", cellule_style),
                Paragraph(e.get("email") or "", cellule_style),
                Paragraph(date_ajout, cellule_style),
            ]
        )

    tableau = Table(
        donnees,
        colWidths=[3.8 * cm, 4.2 * cm, 2.6 * cm, 3.9 * cm, 2.5 * cm],
        repeatRows=1,
    )
    tableau.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(tableau)

    doc.build(elements)
    tampon.seek(0)

    nom_fichier = "entreprises_%s.pdf" % datetime.now().strftime("%Y-%m-%d")
    return send_file(
        tampon,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=nom_fichier,
    )


# --- Démarrage ---------------------------------------------------------------

database.init_db()

# Au premier démarrage, crée le compte admin depuis le .env si aucun user n'existe.
if not database.get_tous_utilisateurs():
    if ADMIN_USERNAME and ADMIN_PASSWORD:
        database.creer_utilisateur(ADMIN_USERNAME, ADMIN_PASSWORD, is_admin=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
