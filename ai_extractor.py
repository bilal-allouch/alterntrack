"""Extraction des informations d'une candidature à partir de texte libre.

Utilise Gemini 1.5 Flash en priorité, puis Groq (llama-3.3-70b-versatile)
en fallback. Renvoie un dictionnaire propre ou None si tout échoue.
"""

import json
import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

GEMINI_MODEL = "gemini-1.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Champs attendus dans le JSON renvoyé par l'IA.
CHAMPS = [
    "entreprise",
    "poste",
    "type_contrat",
    "localisation",
    "date_candidature",
    "lien_offre",
    "statut",
    "notes",
]

PROMPT = """Tu es un assistant qui extrait les informations d'une offre ou d'une \
candidature d'alternance à partir du texte fourni.

Réponds UNIQUEMENT avec un objet JSON valide, sans texte autour et sans bloc de \
code markdown. Le JSON doit contenir exactement ces clés :
- "entreprise" : nom de l'entreprise (string)
- "poste" : intitulé du poste (string)
- "type_contrat" : type de contrat, ex. "Alternance", "Stage", "CDI" (string)
- "localisation" : ville ou région (string)
- "date_candidature" : date de candidature au format YYYY-MM-DD (string)
- "lien_offre" : URL de l'offre, ou null si absent
- "statut" : un parmi "En attente", "Entretien planifié", "Retenu", "Refusé", \
"Sans réponse" (utilise "En attente" par défaut)
- "notes" : informations complémentaires utiles (string, "" si rien)

Si une information est absente du texte, mets une chaîne vide "" (ou null pour \
"lien_offre"). Ne devine pas d'URL.

Texte à analyser :
\"\"\"
{texte}
\"\"\""""


def _nettoyer_reponse(brut):
    """Extrait et normalise le dictionnaire à partir de la réponse brute de l'IA."""
    if not brut:
        return None

    texte = brut.strip()

    # Retire un éventuel bloc de code markdown ```json ... ```
    if texte.startswith("```"):
        texte = texte.split("```")[1] if "```" in texte[3:] else texte[3:]
        if texte.lstrip().lower().startswith("json"):
            texte = texte.lstrip()[4:]
        texte = texte.strip("`").strip()

    # Ne garde que ce qui est entre la première { et la dernière }
    debut = texte.find("{")
    fin = texte.rfind("}")
    if debut == -1 or fin == -1:
        return None
    texte = texte[debut : fin + 1]

    try:
        data = json.loads(texte)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict):
        return None

    # Normalise : on ne garde que les champs attendus, avec des valeurs propres.
    resultat = {}
    for champ in CHAMPS:
        valeur = data.get(champ)
        if isinstance(valeur, str):
            valeur = valeur.strip()
        resultat[champ] = valeur

    if not resultat.get("statut"):
        resultat["statut"] = "En attente"

    if not resultat.get("lien_offre"):
        resultat["lien_offre"] = None

    return resultat


def _extraire_avec_gemini(texte):
    """Appelle Gemini 1.5 Flash. Lève une exception en cas d'échec."""
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)
    reponse = model.generate_content(
        PROMPT.format(texte=texte),
        generation_config={"response_mime_type": "application/json"},
    )
    return reponse.text


def _extraire_avec_groq(texte):
    """Appelle Groq (llama-3.3-70b-versatile). Lève une exception en cas d'échec."""
    from groq import Groq

    client = Groq(api_key=GROQ_API_KEY)
    reponse = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": PROMPT.format(texte=texte)}],
        response_format={"type": "json_object"},
    )
    return reponse.choices[0].message.content


def extraire_candidature(texte):
    """Extrait les infos de candidature du texte.

    Essaie Gemini, puis Groq en fallback. Retourne un dictionnaire propre
    ou None si les deux services échouent.
    """
    if not texte or not texte.strip():
        return None

    # 1) Gemini 1.5 Flash en priorité.
    if GEMINI_API_KEY:
        try:
            data = _nettoyer_reponse(_extraire_avec_gemini(texte))
            if data:
                return data
        except Exception as erreur:
            print(f"[ai_extractor] Gemini a échoué : {erreur}")

    # 2) Groq en fallback.
    if GROQ_API_KEY:
        try:
            data = _nettoyer_reponse(_extraire_avec_groq(texte))
            if data:
                return data
        except Exception as erreur:
            print(f"[ai_extractor] Groq a échoué : {erreur}")

    # 3) Les deux ont échoué.
    return None
