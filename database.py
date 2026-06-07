"""Accès PostgreSQL (Supabase) pour AlternTrack : candidatures et utilisateurs.

Utilise un pool de connexions thread-safe (compatible Gunicorn).
"""

import os
from datetime import datetime

import pytz
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

_pool = None


def _get_pool():
    """Retourne le pool de connexions, en le créant à la première utilisation."""
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=5,
            dsn=os.environ["DATABASE_URL"],
            cursor_factory=RealDictCursor,
        )
    return _pool


def get_connection():
    """Récupère une connexion depuis le pool."""
    conn = _get_pool().getconn()
    conn.autocommit = False
    return conn


def release_connection(conn):
    """Remet une connexion dans le pool."""
    if conn is not None:
        _get_pool().putconn(conn)


def _run(query, params=None, *, fetch=None, commit=False):
    """Exécute une requête via le pool puis libère la connexion.

    `fetch` vaut "one", "all" ou None ; `commit` valide la transaction.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, params)
        if fetch == "one":
            resultat = cur.fetchone()
        elif fetch == "all":
            resultat = cur.fetchall()
        else:
            resultat = None
        if commit:
            conn.commit()
        cur.close()
        return resultat
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        release_connection(conn)


def _maintenant():
    """Horodatage courant au fuseau Europe/Paris, sans info de fuseau."""
    return (
        datetime.now(pytz.timezone("Europe/Paris"))
        .replace(tzinfo=None)
        .isoformat(timespec="seconds")
    )


def init_db():
    """Crée les tables et les colonnes manquantes si nécessaire."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TEXT NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS candidatures (
                id SERIAL PRIMARY KEY,
                entreprise TEXT NOT NULL,
                poste TEXT NOT NULL,
                type_contrat TEXT NOT NULL,
                localisation TEXT NOT NULL,
                date_candidature TEXT NOT NULL,
                lien_offre TEXT,
                statut TEXT NOT NULL DEFAULT 'En attente',
                notes TEXT,
                date_entretien TEXT,
                source TEXT,
                user_id INTEGER,
                date_mise_a_jour TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS entreprises (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                nom TEXT NOT NULL,
                lien TEXT,
                telephone TEXT,
                email TEXT,
                date_ajout TEXT NOT NULL
            )
            """
        )

        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'candidatures'
            """
        )
        colonnes = [c["column_name"] for c in cur.fetchall()]
        if "date_entretien" not in colonnes:
            cur.execute("ALTER TABLE candidatures ADD COLUMN date_entretien TEXT")
        if "source" not in colonnes:
            cur.execute("ALTER TABLE candidatures ADD COLUMN source TEXT")
        if "user_id" not in colonnes:
            cur.execute("ALTER TABLE candidatures ADD COLUMN user_id INTEGER")

        conn.commit()
        cur.close()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        release_connection(conn)


# --- Utilisateurs ------------------------------------------------------------


def creer_utilisateur(username, password, is_admin=False):
    """Crée un utilisateur. Retourne son id, ou None si le username est pris."""
    if get_utilisateur_par_username(username) is not None:
        return None
    ligne = _run(
        """
        INSERT INTO users (username, password_hash, is_admin, created_at)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """,
        (username, generate_password_hash(password), is_admin, _maintenant()),
        fetch="one",
        commit=True,
    )
    return ligne["id"]


def get_utilisateur_par_username(username):
    """Retourne l'utilisateur correspondant au username, ou None."""
    return _run(
        "SELECT * FROM users WHERE username = %s", (username,), fetch="one"
    )


def get_utilisateur_par_id(id):
    """Retourne l'utilisateur correspondant à l'id, ou None."""
    return _run("SELECT * FROM users WHERE id = %s", (id,), fetch="one")


def get_tous_utilisateurs():
    """Retourne tous les utilisateurs, du plus ancien au plus récent."""
    return _run("SELECT * FROM users ORDER BY id ASC", fetch="all")


def supprimer_utilisateur(id):
    """Supprime un utilisateur par son id."""
    _run("DELETE FROM users WHERE id = %s", (id,), commit=True)


def verifier_password(username, password):
    """Retourne True si le couple username/password est valide."""
    user = get_utilisateur_par_username(username)
    if user is None:
        return False
    return check_password_hash(user["password_hash"], password)


# --- Candidatures ------------------------------------------------------------


def ajouter_candidature(data, user_id):
    """Insère une candidature pour un utilisateur et retourne son id."""
    maintenant = _maintenant()
    ligne = _run(
        """
        INSERT INTO candidatures (
            entreprise, poste, type_contrat, localisation,
            date_candidature, lien_offre, statut, notes, date_entretien,
            source, user_id, date_mise_a_jour
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            data.get("entreprise"),
            data.get("poste"),
            data.get("type_contrat"),
            data.get("localisation"),
            data.get("date_candidature"),
            data.get("lien_offre"),
            data.get("statut", "En attente"),
            data.get("notes"),
            data.get("date_entretien"),
            data.get("source"),
            user_id,
            maintenant,
        ),
        fetch="one",
        commit=True,
    )
    return ligne["id"]


def get_toutes_candidatures(user_id):
    """Retourne les candidatures d'un utilisateur, de la plus récente à l'ancienne."""
    return _run(
        """
        SELECT * FROM candidatures
        WHERE user_id = %s
        ORDER BY date_candidature DESC, id DESC
        """,
        (user_id,),
        fetch="all",
    )


def get_toutes_candidatures_export(user_id):
    """Retourne les candidatures d'un utilisateur en dictionnaires pour l'export."""
    lignes = _run(
        """
        SELECT entreprise, poste, type_contrat, localisation,
               date_candidature, statut
        FROM candidatures
        WHERE user_id = %s
        ORDER BY date_candidature DESC, id DESC
        """,
        (user_id,),
        fetch="all",
    )
    return [dict(ligne) for ligne in lignes]


def get_candidature(id, user_id):
    """Retourne une candidature si elle appartient à l'utilisateur, sinon None."""
    return _run(
        "SELECT * FROM candidatures WHERE id = %s AND user_id = %s",
        (id, user_id),
        fetch="one",
    )


def modifier_candidature(id, statut, notes, date_entretien, user_id):
    """Met à jour statut, notes et entretien d'une candidature de l'utilisateur."""
    _run(
        """
        UPDATE candidatures
        SET statut = %s, notes = %s, date_entretien = %s, date_mise_a_jour = %s
        WHERE id = %s AND user_id = %s
        """,
        (statut, notes, date_entretien, _maintenant(), id, user_id),
        commit=True,
    )


def supprimer_candidature(id, user_id):
    """Supprime une candidature si elle appartient à l'utilisateur."""
    _run(
        "DELETE FROM candidatures WHERE id = %s AND user_id = %s",
        (id, user_id),
        commit=True,
    )


# --- Entreprises -------------------------------------------------------------


def ajouter_entreprise(data, user_id):
    """Insère une entreprise pour un utilisateur et retourne son id."""
    ligne = _run(
        """
        INSERT INTO entreprises (user_id, nom, lien, telephone, email, date_ajout)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            user_id,
            data.get("nom"),
            data.get("lien"),
            data.get("telephone"),
            data.get("email"),
            _maintenant(),
        ),
        fetch="one",
        commit=True,
    )
    return ligne["id"]


def get_toutes_entreprises(user_id):
    """Retourne les entreprises d'un utilisateur, de la plus récente à l'ancienne."""
    return _run(
        """
        SELECT * FROM entreprises
        WHERE user_id = %s
        ORDER BY date_ajout DESC, id DESC
        """,
        (user_id,),
        fetch="all",
    )


def get_entreprise(id, user_id):
    """Retourne une entreprise si elle appartient à l'utilisateur, sinon None."""
    return _run(
        "SELECT * FROM entreprises WHERE id = %s AND user_id = %s",
        (id, user_id),
        fetch="one",
    )


def supprimer_entreprise(id, user_id):
    """Supprime une entreprise si elle appartient à l'utilisateur."""
    _run(
        "DELETE FROM entreprises WHERE id = %s AND user_id = %s",
        (id, user_id),
        commit=True,
    )


def get_toutes_entreprises_export(user_id):
    """Retourne les entreprises d'un utilisateur en dictionnaires pour l'export."""
    lignes = _run(
        """
        SELECT nom, lien, telephone, email, date_ajout
        FROM entreprises
        WHERE user_id = %s
        ORDER BY date_ajout DESC, id DESC
        """,
        (user_id,),
        fetch="all",
    )
    return [dict(ligne) for ligne in lignes]


if __name__ == "__main__":
    init_db()
    print("Base de données initialisée (PostgreSQL).")
