"""Accès PostgreSQL (Supabase) pour AlternTrack : gestion des candidatures.

Utilise un pool de connexions thread-safe (compatible Gunicorn).
"""

import os
from datetime import datetime

import pytz
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

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
    """Crée la table et les colonnes manquantes si nécessaire."""
    conn = get_connection()
    try:
        cur = conn.cursor()
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
                date_mise_a_jour TEXT NOT NULL
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


def ajouter_candidature(data):
    """Insère une candidature à partir d'un dictionnaire et retourne son id."""
    maintenant = _maintenant()
    ligne = _run(
        """
        INSERT INTO candidatures (
            entreprise, poste, type_contrat, localisation,
            date_candidature, lien_offre, statut, notes, date_entretien,
            source, date_mise_a_jour
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            maintenant,
        ),
        fetch="one",
        commit=True,
    )
    return ligne["id"]


def get_toutes_candidatures():
    """Retourne toutes les candidatures, de la plus récente à la plus ancienne."""
    return _run(
        "SELECT * FROM candidatures ORDER BY date_candidature DESC, id DESC",
        fetch="all",
    )


def get_toutes_candidatures_export():
    """Retourne toutes les candidatures en dictionnaires simples pour l'export."""
    lignes = _run(
        """
        SELECT entreprise, poste, type_contrat, localisation,
               date_candidature, statut
        FROM candidatures
        ORDER BY date_candidature DESC, id DESC
        """,
        fetch="all",
    )
    return [dict(ligne) for ligne in lignes]


def get_candidature(id):
    """Retourne une candidature par son id, ou None si elle n'existe pas."""
    return _run(
        "SELECT * FROM candidatures WHERE id = %s", (id,), fetch="one"
    )


def modifier_statut(id, statut):
    """Met à jour le statut d'une candidature et sa date de mise à jour."""
    _run(
        "UPDATE candidatures SET statut = %s, date_mise_a_jour = %s WHERE id = %s",
        (statut, _maintenant(), id),
        commit=True,
    )


def modifier_notes(id, notes):
    """Met à jour les notes d'une candidature et sa date de mise à jour."""
    _run(
        "UPDATE candidatures SET notes = %s, date_mise_a_jour = %s WHERE id = %s",
        (notes, _maintenant(), id),
        commit=True,
    )


def modifier_entretien(id, date_entretien):
    """Met à jour la date d'entretien d'une candidature et sa date de mise à jour."""
    _run(
        "UPDATE candidatures SET date_entretien = %s, date_mise_a_jour = %s WHERE id = %s",
        (date_entretien, _maintenant(), id),
        commit=True,
    )


def modifier_candidature(id, statut, notes, date_entretien):
    """Met à jour statut, notes et date d'entretien en une seule requête."""
    _run(
        """
        UPDATE candidatures
        SET statut = %s, notes = %s, date_entretien = %s, date_mise_a_jour = %s
        WHERE id = %s
        """,
        (statut, notes, date_entretien, _maintenant(), id),
        commit=True,
    )


def supprimer_candidature(id):
    """Supprime une candidature par son id."""
    _run("DELETE FROM candidatures WHERE id = %s", (id,), commit=True)


if __name__ == "__main__":
    init_db()
    print("Base de données initialisée (PostgreSQL).")
