"""Accès SQLite pour AlternTrack : gestion des candidatures en alternance."""

import sqlite3
from datetime import datetime

DB_PATH = "candidatures.db"


def get_connection():
    """Ouvre une connexion SQLite avec accès aux colonnes par nom."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée la table candidatures si elle n'existe pas encore."""
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS candidatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    colonnes = [
        c["name"] for c in conn.execute("PRAGMA table_info(candidatures)").fetchall()
    ]
    if "date_entretien" not in colonnes:
        conn.execute("ALTER TABLE candidatures ADD COLUMN date_entretien TEXT")
    if "source" not in colonnes:
        conn.execute("ALTER TABLE candidatures ADD COLUMN source TEXT")

    conn.commit()
    conn.close()


def ajouter_candidature(data):
    """Insère une candidature à partir d'un dictionnaire et retourne son id."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO candidatures (
            entreprise, poste, type_contrat, localisation,
            date_candidature, lien_offre, statut, notes, date_entretien,
            source, date_mise_a_jour
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    conn.commit()
    nouvel_id = cursor.lastrowid
    conn.close()
    return nouvel_id


def get_toutes_candidatures():
    """Retourne toutes les candidatures, de la plus récente à la plus ancienne."""
    conn = get_connection()
    lignes = conn.execute(
        "SELECT * FROM candidatures ORDER BY date_candidature DESC, id DESC"
    ).fetchall()
    conn.close()
    return lignes


def get_toutes_candidatures_export():
    """Retourne toutes les candidatures en dictionnaires simples pour l'export."""
    conn = get_connection()
    lignes = conn.execute(
        """
        SELECT entreprise, poste, type_contrat, localisation,
               date_candidature, statut
        FROM candidatures
        ORDER BY date_candidature DESC, id DESC
        """
    ).fetchall()
    conn.close()
    return [dict(ligne) for ligne in lignes]


def get_candidature(id):
    """Retourne une candidature par son id, ou None si elle n'existe pas."""
    conn = get_connection()
    ligne = conn.execute(
        "SELECT * FROM candidatures WHERE id = ?", (id,)
    ).fetchone()
    conn.close()
    return ligne


def modifier_statut(id, statut):
    """Met à jour le statut d'une candidature et sa date de mise à jour."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "UPDATE candidatures SET statut = ?, date_mise_a_jour = ? WHERE id = ?",
        (statut, maintenant, id),
    )
    conn.commit()
    conn.close()


def modifier_notes(id, notes):
    """Met à jour les notes d'une candidature et sa date de mise à jour."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "UPDATE candidatures SET notes = ?, date_mise_a_jour = ? WHERE id = ?",
        (notes, maintenant, id),
    )
    conn.commit()
    conn.close()


def modifier_entretien(id, date_entretien):
    """Met à jour la date d'entretien d'une candidature et sa date de mise à jour."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        "UPDATE candidatures SET date_entretien = ?, date_mise_a_jour = ? WHERE id = ?",
        (date_entretien, maintenant, id),
    )
    conn.commit()
    conn.close()


def modifier_candidature(id, statut, notes, date_entretien):
    """Met à jour statut, notes et date d'entretien en une seule requête."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    conn = get_connection()
    conn.execute(
        """
        UPDATE candidatures
        SET statut = ?, notes = ?, date_entretien = ?, date_mise_a_jour = ?
        WHERE id = ?
        """,
        (statut, notes, date_entretien, maintenant, id),
    )
    conn.commit()
    conn.close()


def supprimer_candidature(id):
    """Supprime une candidature par son id."""
    conn = get_connection()
    conn.execute("DELETE FROM candidatures WHERE id = ?", (id,))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Base de données initialisée :", DB_PATH)
