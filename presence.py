"""Règles de présence et de pointage des stagiaires (source : demande du 25/09/2026).

Chaque section de formation a son propre horaire (heure de début, tolérance en minutes,
heure de fin), posé par le formateur responsable. Un pointage (scan de la carte QR du
stagiaire) est comparé à cet horaire pour déterminer automatiquement « présent » ou
« en retard ». Les statuts malade / permission / absent sont posés à la main par le
formateur, éventuellement à la suite d'un message envoyé par le stagiaire.

Ce module ne dépend pas de Flask : il ne fait que des calculs sur des horaires et lignes
de base de données.
"""
import re
import time

STATUS = {                      # code : (libellé, classe CSS "tag")
    "present": ("Présent", "ok"),
    "retard": ("En retard", "warn"),
    "malade": ("Malade", "warn"),
    "permission": ("En permission", "warn"),
    "absent": ("Absent", "bad"),
}
# Statuts qu'un formateur peut poser à la main (le scan ne produit que present/retard).
MANUAL_STATUS = ("present", "retard", "malade", "permission", "absent")

NOTICE_KIND = {"absence": "Absence", "retard": "Retard annoncé"}

HM_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def valid_hm(text):
    return bool(HM_RE.fullmatch(text or ""))


def hm_to_minutes(hm):
    h, m = hm.split(":")
    return int(h) * 60 + int(m)


def minutes_to_hm(total):
    total = max(0, min(23 * 60 + 59, total))
    return f"{total // 60:02d}:{total % 60:02d}"


def today():
    return time.strftime("%Y-%m-%d")


def now_hm():
    return time.strftime("%H:%M")


def grace_limit(section):
    """Dernière minute (HH:MM incluse) comptant encore comme « présent »."""
    return minutes_to_hm(hm_to_minutes(section["start_time"]) + int(section["grace_minutes"]))


def compute_status(section, at_hm=None):
    """Statut automatique d'un pointage (scan de carte) : present si dans la tolérance, sinon retard."""
    at_hm = at_hm or now_hm()
    return "present" if at_hm <= grace_limit(section) else "retard"


def extract_card_code(raw):
    """Le lecteur QR peut renvoyer soit le code brut, soit l'URL complète de vérification."""
    raw = (raw or "").strip()
    if "/" in raw:
        raw = raw.rstrip("/").rsplit("/", 1)[-1]
    return raw.upper()
