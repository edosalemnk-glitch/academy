"""Règles de frais et d'inscription du centre (secrétariat / réception).

Frais généraux : valeurs initiales issues de la fiche de renseignements INPP ; les montants réellement appliqués sont lus depuis `settings` et les fichières depuis `filieres`.
  - Inscription : 58 000 Fc, obligatoire
  - Matériel    : variable selon la filière
  - Formation   : 60 000 Fc par mois
  - Jury        : 25 000 Fc, obligatoire avant de passer le jury

Types de stagiaires
  - Non recommandé      : paie tous les frais
  - Recommandé total    : vient d'une institution privée, ne paie rien (l'institution prend en charge)
  - Recommandé partiel  : vient d'une institution étatique, paie le matériel et le jury

Ce module ne dépend pas de Flask : il ne fait que des calculs sur des lignes de base de données.
"""
import time

KINDS = {                       # code : (libellé, devise)
    "inscription": ("Frais d'inscription", "FC"),
    "materiel": ("Frais matériel", "USD"),
    "formation": ("Frais de formation (mensuel)", "FC"),
    "jury": ("Frais de jury", "FC"),
}

TYPES = {                       # code : (libellé, libellé court, frais à payer)
    "non_recommande": ("Non recommandé", "Non recommandé",
                       {"inscription", "materiel", "formation", "jury"}),
    "recommande_total": ("Recommandé total (institution privée)", "Recommandé total", set()),
    "recommande_partiel": ("Recommandé partiel (institution étatique)", "Recommandé partiel",
                           {"materiel", "jury"}),
}

# Un stagiaire est « en ordre avec les frais » quand ces frais sont soldés (ou ne lui sont pas dus).
# La formation (mensuelle) et le jury restent suivis à part.
ORDER_KINDS = ("inscription", "materiel")

STATUS = {                      # code : (libellé, classe CSS)
    "lettre_attente": ("Lettre en attente d'approbation", "warn"),
    "lettre_refusee": ("Lettre refusée", "bad"),
    "attente_paiement": ("En attente de paiement", "warn"),
    "en_ordre": ("En ordre", "ok"),
}
LETTER = {"none": "—", "pending": "En attente", "approved": "Approuvée", "rejected": "Refusée"}


def is_recommended(trainee_type):
    return trainee_type != "non_recommande"


def month_of(date_text):
    return (date_text or time.strftime("%Y-%m-%d"))[:7]


def add_months(period, n):
    y, m = int(period[:4]), int(period[5:7])
    idx = y * 12 + (m - 1) + n
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def fee_snapshot(trainee_type, settings, filiere):
    """Montants dus à l'inscription pour ce type de stagiaire et cette filière (0 = non dû)."""
    due = TYPES[trainee_type][2]
    return {
        "fee_inscription": float(settings["inscription_fee"]) if "inscription" in due else 0.0,
        "fee_material": float(filiere["material_fee"]) if "materiel" in due else 0.0,
        "fee_formation": float(settings["formation_fee"]) if "formation" in due else 0.0,
        "fee_jury": float(settings["jury_fee"]) if "jury" in due else 0.0,
    }


def summarize(reg, payments):
    """Situation financière d'un stagiaire. `payments` : lignes non annulées."""
    due_by_kind = {"inscription": reg["fee_inscription"], "materiel": reg["fee_material"],
                   "formation": reg["fee_formation"], "jury": reg["fee_jury"]}
    paid = {k: 0.0 for k in KINDS}
    periods = []
    for p in payments:
        if p["voided"]:
            continue
        paid[p["kind"]] += p["amount"]
        if p["kind"] == "formation" and p["period"]:
            periods.append(p["period"])
    periods.sort()

    kinds = {}
    for k, due in due_by_kind.items():
        applicable = due > 0
        if k == "formation":
            kinds[k] = {"applicable": applicable, "monthly": due, "paid": paid[k], "months": periods,
                        "balance": 0.0, "settled": True}
        else:
            balance = max(0.0, due - paid[k]) if applicable else 0.0
            kinds[k] = {"applicable": applicable, "due": due, "paid": paid[k], "balance": balance,
                        "settled": balance <= 0.004}

    recommended = is_recommended(reg["trainee_type"])
    if recommended and reg["letter_status"] == "rejected":
        status = "lettre_refusee"
    elif recommended and reg["letter_status"] != "approved":
        status = "lettre_attente"
    elif all(kinds[k]["settled"] for k in ORDER_KINDS):
        status = "en_ordre"
    else:
        status = "attente_paiement"

    current = time.strftime("%Y-%m")
    kinds["formation"]["current_ok"] = bool(periods) and periods[-1] >= current
    return {"kinds": kinds, "status": status, "en_ordre": status == "en_ordre",
            "jury_ok": status == "en_ordre" and kinds["jury"]["settled"]}


def next_periods(reg, payments, months):
    """Les `months` prochains mois à payer : à la suite du dernier mois payé (ou du mois d'inscription)."""
    done = sorted(p["period"] for p in payments if p["kind"] == "formation" and not p["voided"] and p["period"])
    start = add_months(done[-1], 1) if done else month_of(reg["created_at"])
    return [add_months(start, i) for i in range(months)]


def format_money(value, currency):
    value = float(value or 0)
    text = f"{int(round(value)):,}".replace(",", "\u202f") if abs(value - round(value)) < 0.005 \
        else f"{value:,.2f}".replace(",", "\u202f")
    return f"{text}\u00a0$" if currency == "USD" else f"{text}\u00a0Fc"
