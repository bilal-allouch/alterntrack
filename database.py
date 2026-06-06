"""Accès PostgreSQL (Supabase) pour AlternTrack : gestion des candidatures."""

import os
from datetime import datetime

import psycopg2
import pytz
from psycopg2.extras import RealDictCursor


def get_connection():
    """Ouvre une connexion PostgreSQL avec accès aux colonnes par nom."""
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def init_db():
    """Crée la table et les colonnes manquantes si nécessaire."""
    conn = get_connection()
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
    conn.close()


def ajouter_candidature(data):
    """Insère une candidature à partir d'un dictionnaire et retourne son id."""
    maintenant = datetime.now(pytz.timezone("Europe/Paris")).replace(tzinfo=None).isoformat(timespec="seconds")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
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
    )
    nouvel_id = cur.fetchone()["id"]
    conn.commit()
    cur.close()
    conn.close()
    return nouvel_id


def get_toutes_candidatures():
    """Retourne toutes les candidatures, de la plus récente à la plus ancienne."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM candidatures ORDER BY date_candidature DESC, id DESC"
    )
    lignes = cur.fetchall()
    cur.close()
    conn.close()
    return lignes


def get_toutes_candidatures_export():
    """Retourne toutes les candidatures en dictionnaires simples pour l'export."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT entreprise, poste, type_contrat, localisation,
               date_candidature, statut
        FROM candidatures
        ORDER BY date_candidature DESC, id DESC
        """
    )
    lignes = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(ligne) for ligne in lignes]


def get_candidature(id):
    """Retourne une candidature par son id, ou None si elle n'existe pas."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM candidatures WHERE id = %s", (id,))
    ligne = cur.fetchone()
    cur.close()
    conn.close()
    return ligne


def modifier_statut(id, statut):
    """Met à jour le statut d'une candidature et sa date de mise à jour."""
    maintenant = datetime.now(pytz.timezone("Europe/Paris")).replace(tzinfo=None).isoformat(timespec="seconds")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE candidatures SET statut = %s, date_mise_a_jour = %s WHERE id = %s",
        (statut, maintenant, id),
    )
    conn.commit()
    cur.close()
    conn.close()


def modifier_notes(id, notes):
    """Met à jour les notes d'une candidature et sa date de mise à jour."""
    maintenant = datetime.now(pytz.timezone("Europe/Paris")).replace(tzinfo=None).isoformat(timespec="seconds")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE candidatures SET notes = %s, date_mise_a_jour = %s WHERE id = %s",
        (notes, maintenant, id),
    )
    conn.commit()
    cur.close()
    conn.close()


def modifier_entretien(id, date_entretien):
    """Met à jour la date d'entretien d'une candidature et sa date de mise à jour."""
    maintenant = datetime.now(pytz.timezone("Europe/Paris")).replace(tzinfo=None).isoformat(timespec="seconds")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE candidatures SET date_entretien = %s, date_mise_a_jour = %s WHERE id = %s",
        (date_entretien, maintenant, id),
    )
    conn.commit()
    cur.close()
    conn.close()


def modifier_candidature(id, statut, notes, date_entretien):
    """Met à jour statut, notes et date d'entretien en une seule requête."""
    maintenant = datetime.now(pytz.timezone("Europe/Paris")).replace(tzinfo=None).isoformat(timespec="seconds")
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE candidatures
        SET statut = %s, notes = %s, date_entretien = %s, date_mise_a_jour = %s
        WHERE id = %s
        """,
        (statut, notes, date_entretien, maintenant, id),
    )
    conn.commit()
    cur.close()
    conn.close()


def supprimer_candidature(id):
    """Supprime une candidature par son id."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM candidatures WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Base de données initialisée (PostgreSQL).")
