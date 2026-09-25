"""Terrain d'entraînement SQL : base d'exemple en mémoire, lecture seule."""
import sqlite3
import time

SAMPLE_SQL = """
CREATE TABLE departements (id INTEGER PRIMARY KEY, nom TEXT, ville TEXT);
CREATE TABLE employes (
    id INTEGER PRIMARY KEY, nom TEXT, prenom TEXT, poste TEXT,
    salaire REAL, date_embauche TEXT, departement_id INTEGER
);
CREATE TABLE projets (id INTEGER PRIMARY KEY, nom TEXT, budget REAL, departement_id INTEGER);

INSERT INTO departements VALUES
 (1,'Informatique','Kinshasa'),(2,'Ressources Humaines','Kinshasa'),
 (3,'Finance','Lubumbashi'),(4,'Logistique','Matadi'),(5,'Formation','Kinshasa');

INSERT INTO employes VALUES
 (1,'Mukendi','Patrick','Développeur',1800,'2019-03-12',1),
 (2,'Tshimanga','Grace','Analyste',1600,'2020-07-01',1),
 (3,'Ilunga','Joseph','Administrateur réseau',2000,'2018-01-15',1),
 (4,'Mbuyi','Sarah','Responsable RH',2100,'2017-09-20',2),
 (5,'Kasongo','David','Assistant RH',900,'2022-02-14',2),
 (6,'Lukusa','Ruth','Comptable',1500,'2019-11-05',3),
 (7,'Banza','Emmanuel','Chef comptable',2400,'2016-06-30',3),
 (8,'Ngoy','Esther','Logisticienne',1200,'2021-04-19',4),
 (9,'Kalala','Michel','Chauffeur',700,'2023-01-09',4),
 (10,'Mutombo','Christelle','Formatrice',1400,'2020-10-12',5),
 (11,'Kabongo','Jean','Formateur',1450,'2018-08-27',5),
 (12,'Nkulu','Alice','Formatrice',1350,'2022-09-01',5),
 (13,'Mwamba','Olivier','Technicien support',1000,'2021-12-06',1),
 (14,'Kanku','Bénédicte','Secrétaire',800,'2023-05-22',NULL),
 (15,'Tshibanda','Rodrigue','Gestionnaire de stocks',1100,'2020-03-16',4);

INSERT INTO projets VALUES
 (1,'Migration des serveurs',15000,1),(2,'Portail de formation',22000,1),
 (3,'Audit comptable',8000,3),(4,'Recrutement 2026',5000,2),
 (5,'Entrepôt central',30000,4),(6,'Alphabétisation numérique',12000,5),
 (7,'Étude de faisabilité',4000,NULL);
"""

TABLES = {
    "departements": ["id", "nom", "ville"],
    "employes": ["id", "nom", "prenom", "poste", "salaire", "date_embauche", "departement_id"],
    "projets": ["id", "nom", "budget", "departement_id"],
}

CHALLENGES = [
    {"id": 1, "title": "Afficher des colonnes",
     "text": "Affichez le nom et le prénom de tous les employés.",
     "solution": "SELECT nom, prenom FROM employes", "ordered": False},
    {"id": 2, "title": "Filtrer avec WHERE",
     "text": "Affichez toutes les colonnes des employés du département 1 dont le salaire est supérieur à 1600.",
     "solution": "SELECT * FROM employes WHERE departement_id = 1 AND salaire > 1600", "ordered": False},
    {"id": 3, "title": "Trier et dédoublonner",
     "text": "Affichez la liste des postes, sans doublon, triés par ordre alphabétique.",
     "solution": "SELECT DISTINCT poste FROM employes ORDER BY poste", "ordered": True},
    {"id": 4, "title": "Regrouper et compter",
     "text": "Pour chaque département (departement_id), affichez le nombre d'employés.",
     "solution": "SELECT departement_id, COUNT(*) FROM employes GROUP BY departement_id", "ordered": False},
    {"id": 5, "title": "Jointure",
     "text": "Affichez le nom, le prénom et le nom du département de chaque employé qui a un département.",
     "solution": "SELECT e.nom, e.prenom, d.nom FROM employes e JOIN departements d ON d.id = e.departement_id",
     "ordered": False},
    {"id": 6, "title": "Analyse par département",
     "text": "Affichez le nom des départements dont la masse salariale (somme des salaires) dépasse 3000, avec cette somme.",
     "solution": ("SELECT d.nom, SUM(e.salaire) FROM departements d JOIN employes e ON e.departement_id = d.id "
                  "GROUP BY d.nom HAVING SUM(e.salaire) > 3000"), "ordered": False},
]

MAX_ROWS = 200
MAX_SECONDS = 2.0
# Codes d'action SQLite autorisés : SELECT, READ, FUNCTION, RECURSIVE
_ALLOWED_ACTIONS = {21, 20, 31, 33}


class LabError(Exception):
    pass


def _authorizer(action, *_):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def run_query(sql):
    """Exécute une requête SELECT sur la base d'exemple. Retourne (colonnes, lignes, tronqué)."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise LabError("Écrivez une requête SELECT.")
    if ";" in sql:
        raise LabError("Une seule requête à la fois, sans point-virgule au milieu.")
    if not sql.lower().startswith(("select", "with")):
        raise LabError("Ce terrain est en lecture seule : seules les requêtes SELECT sont acceptées.")
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(SAMPLE_SQL)
        conn.set_authorizer(_authorizer)
        deadline = time.monotonic() + MAX_SECONDS
        conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10000)
        cur = conn.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_ROWS + 1)
        truncated = len(rows) > MAX_ROWS
        return cols, [tuple(r) for r in rows[:MAX_ROWS]], truncated
    except sqlite3.Error as exc:
        msg = str(exc)
        if "interrupted" in msg:
            msg = "Requête trop longue (limite : 2 secondes)."
        elif "not authorized" in msg:
            msg = "Opération non autorisée : ce terrain n'accepte que la lecture (SELECT)."
        raise LabError(msg)
    finally:
        conn.close()


def _norm(rows):
    return [tuple(round(v, 2) if isinstance(v, float) else v for v in r) for r in rows]


def check_challenge(challenge_id, user_rows):
    ch = next((c for c in CHALLENGES if c["id"] == challenge_id), None)
    if ch is None:
        return None
    _, expected, _ = run_query(ch["solution"])
    a, b = _norm(user_rows), _norm(expected)
    if not ch["ordered"]:
        a, b = sorted(a, key=repr), sorted(b, key=repr)
    return a == b
