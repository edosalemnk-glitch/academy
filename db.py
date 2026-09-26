"""Accès à la base SQLite et schéma de la plateforme."""
import os
import re

import psycopg
class _CompatRow(dict):
    """Ligne PostgreSQL compatible avec sqlite3.Row : accès par nom ou par index."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


def _row_factory(cursor):
    """Fabrique des lignes compatibles avec sqlite3.Row pour psycopg 3."""
    def make_row(values):
        return _CompatRow({desc.name: value for desc, value in zip(cursor.description, values)})
    return make_row


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL est requis. Configurez la connexion PostgreSQL Supabase dans l'environnement."
    )


def _translate_sql(sql):
    """Adapte les quelques conventions SQLite historiques vers PostgreSQL."""
    ignore_insert = bool(re.match(r"^\s*INSERT\s+OR\s+IGNORE\s", sql, re.IGNORECASE))
    if ignore_insert:
        sql = re.sub(r"INSERT\s+OR\s+IGNORE\s+", "INSERT ", sql, count=1, flags=re.IGNORECASE)
        sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"
    sql = sql.replace("datetime('now','-10 days')", "to_char(CURRENT_TIMESTAMP - INTERVAL '10 days', 'YYYY-MM-DD HH24:MI:SS')")
    sql = sql.replace("date('now','-3 days')", "to_char(CURRENT_DATE - INTERVAL '3 days', 'YYYY-MM-DD')")
    sql = sql.replace("datetime('now')", "to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')")
    sql = sql.replace("date('now')", "to_char(CURRENT_DATE, 'YYYY-MM-DD')")
    sql = sql.replace("datetime('now',?)", "to_char(CURRENT_TIMESTAMP + (%s)::interval, 'YYYY-MM-DD HH24:MI:SS')")
    sql = sql.replace("date('now',?)", "to_char(CURRENT_DATE + (%s)::interval, 'YYYY-MM-DD')")
    sql = sql.replace("?", "%s")
    return sql

def _postgres_schema(sql):
    """Convertit le schéma historique SQLite en DDL PostgreSQL."""
    sql = sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
    sql = sql.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
    sql = sql.replace(" REAL ", " DOUBLE PRECISION ")
    sql = sql.replace(" REAL NOT NULL", " DOUBLE PRECISION NOT NULL")
    sql = sql.replace("DEFAULT (datetime('now'))", "DEFAULT to_char(CURRENT_TIMESTAMP, 'YYYY-MM-DD HH24:MI:SS')")
    sql = sql.replace("DEFAULT (date('now'))", "DEFAULT to_char(CURRENT_DATE, 'YYYY-MM-DD')")
    return sql


class _PGCursor:
    def __init__(self, conn, cursor):
        self._conn = conn
        self._cursor = cursor
        self._table = None

    def execute(self, sql, params=None):
        self._table = None
        if re.match(r"^\s*INSERT\s", sql, re.IGNORECASE):
            m = re.search(r"INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.IGNORECASE)
            self._table = m.group(1) if m else None
        translated = _translate_sql(sql)
        self._cursor.execute(translated, params or ())
        return self

    def executemany(self, sql, seq):
        translated = _translate_sql(sql)
        self._cursor.executemany(translated, seq)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def fetchmany(self, size=None):
        return self._cursor.fetchmany(size)

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        if not self._table:
            return None
        row = self._conn._raw.execute(
            "SELECT currval(pg_get_serial_sequence(%s, 'id')) AS id",
            (self._table,),
        ).fetchone()
        return row["id"] if row else None

    @property
    def description(self):
        return self._cursor.description

    def __iter__(self):
        return iter(self._cursor)

    def close(self):
        self._cursor.close()


class _PGConnection:
    def __init__(self, raw):
        self._raw = raw

    def execute(self, sql, params=None):
        return _PGCursor(self, self._raw.cursor()).execute(sql, params)

    def executemany(self, sql, seq):
        return _PGCursor(self, self._raw.cursor()).executemany(sql, seq)

    def executescript(self, script):
        # Retire les commentaires SQL avant de découper le DDL : certains commentaires
        # historiques contiennent des points-virgules, qui ne doivent pas séparer une requête.
        cleaned_lines = []
        for line in script.splitlines():
            # Supprime les commentaires SQL de ligne, y compris ceux placés
            # après une définition de colonne. Certains contiennent des ";"
            # qui ne doivent jamais servir de séparateurs SQL.
            line = re.sub(r"\s*--.*$", "", line)
            if line.strip():
                cleaned_lines.append(line)
        cleaned = "\n".join(cleaned_lines)
        for statement in cleaned.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)
        return self

    def commit(self):
        self._raw.commit()

    def rollback(self):
        self._raw.rollback()

    def close(self):
        self._raw.close()

    def cursor(self):
        return _PGCursor(self, self._raw.cursor())


USERS_COLUMNS = """(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('formateur', 'stagiaire', 'secretaire')),
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
)"""

SCHEMA_TEMPLATE = """
CREATE TABLE IF NOT EXISTS users __USERS__;

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Général',
    level TEXT NOT NULL DEFAULT 'Débutant',
    description TEXT NOT NULL DEFAULT '',
    fee_amount REAL NOT NULL DEFAULT 0,
    currency TEXT NOT NULL DEFAULT 'USD',
    pass_mark INTEGER NOT NULL DEFAULT 70,
    published INTEGER NOT NULL DEFAULT 1,
    start_date TEXT,
    end_date TEXT,
    schedule TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    seats INTEGER NOT NULL DEFAULT 0,
    registration_open INTEGER NOT NULL DEFAULT 1,
    trainer_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    image TEXT
);

CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id INTEGER REFERENCES lessons(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'support'
        CHECK (kind IN ('support','exercice','document','lien')),
    description TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    file_path TEXT,
    file_name TEXT,
    published INTEGER NOT NULL DEFAULT 1,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_resources_course ON resources(course_id, published);
CREATE INDEX IF NOT EXISTS idx_resources_lesson ON resources(lesson_id);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct TEXT NOT NULL CHECK (correct IN ('A', 'B', 'C', 'D')),
    explanation TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected', 'revoked')),
    fee_status TEXT NOT NULL DEFAULT 'unpaid'
        CHECK (fee_status IN ('unpaid', 'paid', 'exempt')),
    requested_at TEXT NOT NULL DEFAULT (datetime('now')),
    decided_at TEXT,
    decided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    UNIQUE (user_id, course_id)
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    score INTEGER NOT NULL,
    passed INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS progress (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    best_score INTEGER NOT NULL DEFAULT 100,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, lesson_id)
);

CREATE TABLE IF NOT EXISTS certificates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    code TEXT NOT NULL UNIQUE,
    issued_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, course_id)
);

-- ---------------------------------------------------------------- secrétariat / réception
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS filieres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    metier TEXT NOT NULL DEFAULT '',           -- métier visé (ex. « Électricien »), selon la fiche INPP
    duration_months INTEGER NOT NULL DEFAULT 0,-- durée de la formation, en mois
    material_fee REAL NOT NULL DEFAULT 0,      -- frais matériel en USD, payables une seule fois (selon la filière)
    active INTEGER NOT NULL DEFAULT 1
);

-- Registre des stagiaires du centre. Les montants fee_* sont figés à l'inscription
-- (une hausse de tarif ne modifie pas ce que doit un stagiaire déjà inscrit).
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    sex TEXT NOT NULL CHECK (sex IN ('M', 'F')),
    phone TEXT NOT NULL DEFAULT '',
    filiere_id INTEGER NOT NULL REFERENCES filieres(id),
    trainee_type TEXT NOT NULL DEFAULT 'non_recommande'
        CHECK (trainee_type IN ('non_recommande', 'recommande_total', 'recommande_partiel')),
    institution TEXT NOT NULL DEFAULT '',
    letter_ref TEXT NOT NULL DEFAULT '',
    letter_status TEXT NOT NULL DEFAULT 'none'
        CHECK (letter_status IN ('none', 'pending', 'approved', 'rejected')),
    letter_decided_by TEXT NOT NULL DEFAULT '',
    letter_decided_at TEXT,
    letter_note TEXT NOT NULL DEFAULT '',
    fee_inscription REAL NOT NULL DEFAULT 0,   -- FC
    fee_material REAL NOT NULL DEFAULT 0,      -- USD
    fee_formation REAL NOT NULL DEFAULT 0,     -- FC par mois
    fee_jury REAL NOT NULL DEFAULT 0,          -- FC
    card_code TEXT UNIQUE,
    card_issued_at TEXT,
    registered_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('inscription', 'materiel', 'formation', 'jury')),
    amount REAL NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL CHECK (currency IN ('FC', 'USD')),
    period TEXT,                               -- mois couvert (AAAA-MM) pour les frais de formation
    bank_ref TEXT NOT NULL DEFAULT '',         -- référence de la preuve de paiement FN BANK
    paid_at TEXT NOT NULL DEFAULT (date('now')),
    recorded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    voided INTEGER NOT NULL DEFAULT 0,
    voided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    voided_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_payments_reg ON payments(registration_id);

-- ---------------------------------------------------------------- filières / services / présences
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    chef_id INTEGER REFERENCES users(id) ON DELETE SET NULL,   -- le chef de service est aussi formateur
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS service_formateurs (
    service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (service_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_service_formateurs_user ON service_formateurs(user_id);

-- Une section est un groupe de stagiaires suivant une filière avec un formateur et un horaire propres
-- (ex. « SQL Niveau 1 - groupe A », 8h30 + 15 min de tolérance, fin 12h30).
CREATE TABLE IF NOT EXISTS sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filiere_id INTEGER NOT NULL REFERENCES filieres(id),
    trainer_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    start_time TEXT NOT NULL DEFAULT '08:30',      -- HH:MM
    grace_minutes INTEGER NOT NULL DEFAULT 15,     -- tolérance avant de compter un retard
    end_time TEXT NOT NULL DEFAULT '12:30',        -- HH:MM
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Présence d'un stagiaire à une section, un jour donné. Un scan de carte (QR) crée/actualise la ligne
-- automatiquement ; malade/permission/absent sont posés à la main par le formateur.
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    day TEXT NOT NULL,                             -- AAAA-MM-JJ
    status TEXT NOT NULL CHECK (status IN ('present', 'retard', 'absent', 'malade', 'permission')),
    checkin_at TEXT,                               -- heure du pointage (scan), NULL si statut posé à la main
    source TEXT NOT NULL DEFAULT 'formateur' CHECK (source IN ('qr', 'formateur')),
    note TEXT NOT NULL DEFAULT '',
    marked_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (section_id, registration_id, day)
);
CREATE INDEX IF NOT EXISTS idx_attendance_day ON attendance(section_id, day);

-- Message d'un stagiaire (depuis sa carte) prévenant son formateur d'une absence ou d'un retard.
CREATE TABLE IF NOT EXISTS absence_notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_id INTEGER NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    for_day TEXT NOT NULL,                         -- AAAA-MM-JJ concerné
    kind TEXT NOT NULL CHECK (kind IN ('absence', 'retard')),
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'attente' CHECK (status IN ('attente', 'traite')),
    decided_status TEXT,                           -- statut de présence posé par le formateur, une fois traité
    decided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    decided_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_notices_section ON absence_notices(section_id, status);

-- ---------------------------------------------------------------- examen final (distinct des quiz de leçon)
-- Un cours a au plus un examen final : surveillé en pratique (le formateur ouvre la fenêtre depuis la
-- salle), corrigé automatiquement comme les quiz, mais séparé du parcours de leçons.
CREATE TABLE IF NOT EXISTS exams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL UNIQUE REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Examen final',
    duration_minutes INTEGER NOT NULL DEFAULT 30,
    pass_mark INTEGER NOT NULL DEFAULT 70,
    max_attempts INTEGER NOT NULL DEFAULT 1,
    opens_at TEXT,                             -- datetime ISO ; NULL = pas de borne basse
    closes_at TEXT,                             -- datetime ISO ; NULL = pas de borne haute
    published INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS exam_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    option_a TEXT NOT NULL,
    option_b TEXT NOT NULL,
    option_c TEXT NOT NULL,
    option_d TEXT NOT NULL,
    correct TEXT NOT NULL CHECK (correct IN ('A', 'B', 'C', 'D')),
    explanation TEXT NOT NULL DEFAULT ''
);

-- Une tentative par ligne. started_at fixe le chrono ; submitted_at NULL = tentative en cours.
CREATE TABLE IF NOT EXISTS exam_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_id INTEGER NOT NULL REFERENCES exams(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    score INTEGER,
    passed INTEGER,
    late INTEGER NOT NULL DEFAULT 0,           -- soumis après le temps imparti
    started_at TEXT NOT NULL DEFAULT (datetime('now')),
    submitted_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_exam_attempts ON exam_attempts(exam_id, user_id);
"""


SCHEMA = SCHEMA_TEMPLATE.replace("__USERS__", USERS_COLUMNS)

# Tarifs par défaut (modifiables par le secrétariat, page « Tarifs »).
# Source : fiche de renseignements INPP, Direction Provinciale de Kinshasa.
DEFAULT_SETTINGS = {
    "inscription_fee": "58000",     # FC, obligatoire (Carte, Certificat, Fiche et Test)
    "formation_fee": "60000",       # FC par mois (minerval, toutes filières confondues)
    "jury_fee": "25000",            # FC, obligatoire avant de passer le jury
    "lettre_stage_fee": "5000",     # FC, lettre de stage, payable après la formation
    "bank_name": "BCDC - Equity",
    "bank_account_usd": "00101-00001340052-37",   # n° de compte en dollars
    "bank_account_fc": "00101-00001340051-40",    # n° de compte en francs congolais
}


def connect():
    # Supabase fournit DATABASE_URL depuis Dashboard > Connect > Session pooler.
    # sslmode=require garantit le chiffrement de la connexion.
    url = DATABASE_URL
    if "sslmode=" not in url:
        url += ("&" if "?" in url else "?") + "sslmode=require"
    raw = psycopg.connect(url, row_factory=_row_factory, prepare_threshold=None, connect_timeout=10)
    return _PGConnection(raw)


def _migrate_users_roles(conn):
    """Conservée pour compatibilité : le schéma PostgreSQL inclut directement le rôle secretaire."""
    return


def _migrate_presence(conn):
    """Conservée pour compatibilité avec les anciennes versions du schéma."""
    return



def _migrate_resource_modules_exam(conn):
    """Ajoute les modules Word/Excel et la sélection d'exercices pour l'examen final."""
    conn.execute("ALTER TABLE resources ADD COLUMN IF NOT EXISTS module TEXT NOT NULL DEFAULT 'general'")
    conn.execute("ALTER TABLE resources ADD COLUMN IF NOT EXISTS exam_selected INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE resources ADD COLUMN IF NOT EXISTS exam_points INTEGER NOT NULL DEFAULT 10")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_resources_module_exam ON resources(course_id, module, exam_selected)")


def _migrate_registration_section(conn):
    """Ajoute le rattachement des inscriptions aux sections introduit après le schéma initial."""
    conn.execute(
        "ALTER TABLE registrations ADD COLUMN IF NOT EXISTS section_id INTEGER REFERENCES sections(id)"
    )

def _migrate_services_formateurs(conn):
    """Lie plusieurs formateurs à chaque service et rattache les cours à un service."""
    conn.execute(
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS service_id INTEGER REFERENCES services(id)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS service_formateurs ("
        "service_id INTEGER NOT NULL REFERENCES services(id) ON DELETE CASCADE,"
        "user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
        "created_at TEXT NOT NULL DEFAULT (datetime('now')),"
        "PRIMARY KEY (service_id, user_id))"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_service_formateurs_user ON service_formateurs(user_id)")
    # Le chef historique reste automatiquement membre de son service.
    conn.execute(
        "INSERT INTO service_formateurs (service_id, user_id) "
        "SELECT id, chef_id FROM services WHERE chef_id IS NOT NULL "
        "ON CONFLICT DO NOTHING"
    )
    # Les cours historiques sans service sont rattachés au service du formateur lorsqu'il n'y en a qu'un.
    conn.execute(
        "UPDATE courses c SET service_id=("
        "SELECT sf.service_id FROM service_formateurs sf "
        "WHERE sf.user_id=c.trainer_id ORDER BY sf.service_id LIMIT 1"
        ") WHERE c.service_id IS NULL AND EXISTS ("
        "SELECT 1 FROM service_formateurs sf2 WHERE sf2.user_id=c.trainer_id)"
    )


def _migrate_filiere_details(conn):
    """Ajoute les colonnes des filières introduites après le schéma initial."""
    conn.execute(
        "ALTER TABLE filieres ADD COLUMN IF NOT EXISTS service_id INTEGER REFERENCES services(id)"
    )


def _migrate_course_case_study(conn):
    """Ajoute les cas pratiques au catalogue sans modifier les autres données du cours."""
    conn.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS case_study TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "UPDATE courses SET case_study=? WHERE COALESCE(TRIM(case_study),'')='' "
        "AND category='Bases de données' AND lower(title) LIKE ?",
        ("%niveau 1%", "Vous êtes agent informatique dans un centre de formation. La direction vous demande de retrouver "
         "rapidement les stagiaires, leurs résultats et les informations utiles dans une base de données. "
         "Votre mission : interroger les tables, filtrer les données et produire les bons résultats sans modifier "
         "les informations d'origine.",)
    )
    conn.execute(
        "UPDATE courses SET case_study=? WHERE COALESCE(TRIM(case_study),'')='' "
        "AND category='Bases de données' AND lower(title) LIKE ?",
        ("%niveau 2%", "Le responsable administratif doit consolider plusieurs informations pour préparer un rapport mensuel. "
         "Votre mission : construire des requêtes SQL plus avancées, relier les tables et extraire des indicateurs "
         "fiables à partir des données de l'organisation.",)
    )
    conn.execute(
        "UPDATE courses SET case_study=? WHERE COALESCE(TRIM(case_study),'')='' AND category='Bureautique'",
        ("Le secrétariat reçoit chaque semaine des documents et fichiers provenant de plusieurs services. "
         "Votre mission : organiser une arborescence claire, retrouver rapidement un document et éviter les "
         "erreurs de classement ou de déplacement.",)
    )


def _migrate_reference_resources(conn):
    """Publie des ressources pédagogiques réelles de révision."""
    matches = conn.execute(
        "SELECT id, title FROM courses WHERE (lower(title) LIKE ? OR lower(title) LIKE ? OR lower(title) = ?)",
        ("%sql%niveau 1%", "%sql%niveau 2%", "bureautique – gérer ses fichiers et dossiers")
    ).fetchall()
    if not matches:
        return

    resources = {
        "sql1": [
            ("Cours — SQL Niveau 1 : SELECT, WHERE et ORDER BY", "support",
             "Fiche de révision sur les requêtes SQL de base.",
             """# Objectifs
À la fin de cette révision, vous devez pouvoir sélectionner des colonnes, filtrer des lignes, combiner des conditions et trier un résultat.

# SELECT
SELECT nom, prenom
FROM stagiaires;

SELECT * FROM stagiaires;

# WHERE
SELECT nom, prenom
FROM stagiaires
WHERE statut = 'actif';

Conditions utiles : age >= 18, filiere = 'Informatique', nom LIKE 'M%'.

# AND / OR
SELECT nom, prenom
FROM stagiaires
WHERE statut = 'actif' AND filiere = 'Informatique';

# ORDER BY
SELECT nom, prenom
FROM stagiaires
ORDER BY nom ASC;

ASC = croissant ; DESC = décroissant.

# LIMIT
SELECT nom, prenom
FROM stagiaires
ORDER BY nom
LIMIT 10;

# Méthode
Lire la consigne → choisir les colonnes → choisir la table → filtrer → trier → vérifier le résultat."""),
            ("Travaux pratiques — SQL Niveau 1", "exercice",
             "Exercices progressifs avec corrigé.",
             """# Jeu de données
Table stagiaires : id, nom, prenom, filiere, statut, age.

# Exercices
1. Afficher nom, prénom et filière de tous les stagiaires.
2. Afficher uniquement les stagiaires actifs.
3. Afficher les stagiaires d'Informatique.
4. Afficher les stagiaires actifs de plus de 18 ans.
5. Afficher les stagiaires actifs triés par nom.
6. Afficher les 5 premiers stagiaires actifs triés par nom.

# Corrigé
1) SELECT nom, prenom, filiere FROM stagiaires;
2) SELECT nom, prenom FROM stagiaires WHERE statut = 'actif';
3) SELECT nom, prenom FROM stagiaires WHERE filiere = 'Informatique';
4) SELECT nom, prenom FROM stagiaires WHERE statut = 'actif' AND age > 18;
5) SELECT nom, prenom FROM stagiaires WHERE statut = 'actif' ORDER BY nom ASC;
6) SELECT nom, prenom FROM stagiaires WHERE statut = 'actif' ORDER BY nom ASC LIMIT 5;"""),
            ("Travail personnel — 10 requêtes SQL", "exercice",
             "Série d'entraînement à réaliser avant la prochaine séance.",
             """Produisez une requête pour :
1. afficher tous les stagiaires ;
2. afficher nom et prénom ;
3. afficher les stagiaires d'Électricité ;
4. afficher les stagiaires non actifs ;
5. afficher les stagiaires âgés d'au moins 18 ans ;
6. afficher les stagiaires d'Informatique âgés d'au moins 18 ans ;
7. trier par prénom ;
8. trier par âge décroissant ;
9. afficher les 10 premiers ;
10. afficher les 10 premiers actifs triés par nom.

Écrivez, exécutez et vérifiez chaque requête.""")
        ],
        "sql2": [
            ("Cours — SQL Niveau 2 : JOIN, GROUP BY et agrégations", "support",
             "Fiche de révision sur les jointures et l'analyse.",
             """# JOIN
SELECT s.nom, s.prenom, f.nom AS filiere
FROM stagiaires s
JOIN filieres f ON f.id = s.filiere_id;

# LEFT JOIN
SELECT s.nom, f.nom AS filiere
FROM stagiaires s
LEFT JOIN filieres f ON f.id = s.filiere_id;

# COUNT
SELECT COUNT(*) AS total FROM stagiaires;

# GROUP BY
SELECT f.nom, COUNT(*) AS total
FROM stagiaires s
JOIN filieres f ON f.id = s.filiere_id
GROUP BY f.nom
ORDER BY total DESC;

# HAVING
SELECT f.nom, COUNT(*) AS total
FROM stagiaires s
JOIN filieres f ON f.id = s.filiere_id
GROUP BY f.nom
HAVING COUNT(*) >= 5;

WHERE filtre les lignes avant l'agrégation ; HAVING filtre les groupes après l'agrégation."""),
            ("Travaux pratiques — SQL Niveau 2", "exercice",
             "Exercices de jointures et d'analyse avec corrigé indicatif.",
             """# Exercices
1. Afficher chaque stagiaire avec le nom de sa filière.
2. Compter les stagiaires par filière.
3. Afficher les filières ayant au moins 5 stagiaires.
4. Afficher les stagiaires actifs avec leur filière.
5. Classer les filières par nombre de stagiaires décroissant.

# Corrigé
1) SELECT s.nom, s.prenom, f.nom AS filiere FROM stagiaires s JOIN filieres f ON f.id=s.filiere_id;
2) SELECT f.nom, COUNT(*) AS total FROM stagiaires s JOIN filieres f ON f.id=s.filiere_id GROUP BY f.nom;
3) SELECT f.nom, COUNT(*) AS total FROM stagiaires s JOIN filieres f ON f.id=s.filiere_id GROUP BY f.nom HAVING COUNT(*) >= 5;
4) SELECT s.nom, s.prenom, f.nom AS filiere FROM stagiaires s JOIN filieres f ON f.id=s.filiere_id WHERE s.statut='actif';
5) SELECT f.nom, COUNT(*) AS total FROM stagiaires s JOIN filieres f ON f.id=s.filiere_id GROUP BY f.nom ORDER BY total DESC;""")
        ],
        "bureautique": [
            ("Cours — Bureautique : organiser ses fichiers et dossiers", "support",
             "Fiche pratique d'organisation documentaire.",
             """# Organisation
INPP/
  2026/
    Inscriptions/
    Formations/
    Rapports/
    Archives/

# Nommage
Préférer : Rapport_Formation_SQL_2026-10-05.docx
Éviter : Document final nouveau 2.docx

# Bonnes pratiques
1. Un dossier = un objectif clair.
2. Un fichier = un nom explicite.
3. Utiliser AAAA-MM-JJ pour les dates.
4. Archiver les anciennes versions.
5. Éviter final, final2, final_OK.

# Travail
Créez une arborescence pour un service qui gère trois formations et des rapports mensuels."""),
            ("Travaux pratiques — Word : document professionnel", "exercice",
             "Production d'un compte rendu de formation.",
             """Créer un document Compte rendu de formation avec : titre, formation, date, formateur, introduction, trois points traités, conclusion et tableau récapitulatif.

Mise en forme : titres cohérents, texte lisible, tableau avec en-têtes, pied de page avec la date.

Nom du fichier : Compte_rendu_formation_AAAA-MM-JJ.docx.

Contrôle final : orthographe, marges, titres et nom du fichier."""),
            ("Travaux pratiques — Excel : tableau et calculs", "exercice",
             "Exercice de saisie, calcul et tri d'un tableau de stagiaires.",
             """Créer un tableau avec Nom, Prénom, Filière, Note 1, Note 2, Moyenne, Statut.

Travail :
1. saisir au moins 10 lignes ;
2. calculer la moyenne de chaque stagiaire ;
3. identifier les moyennes >= 50 ;
4. trier par moyenne décroissante ;
5. calculer la moyenne générale.

Formule exemple : =MOYENNE(D2:E2).

Vérifiez que les formules couvrent toutes les lignes et que le tri conserve les informations de chaque stagiaire.""")
        ]
    }

    for course in matches:
        title = str(course["title"])
        key = "sql1" if "niveau 1" in title.lower() else "sql2" if "niveau 2" in title.lower() else "bureautique"
        for rtitle, kind, description, content in resources[key]:
            exists = conn.execute(
                "SELECT id FROM resources WHERE course_id=? AND title=?", (course["id"], rtitle)
            ).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO resources (course_id,title,kind,description,content,published) VALUES (?,?,?,?,?,1)",
                    (course["id"], rtitle, kind, description, content)
                )

    # Retire les quatre anciennes ressources génériques de la première version.
    # Les ressources créées par un formateur (created_by non NULL) ne sont jamais touchées.
    conn.execute(
        "DELETE FROM resources WHERE created_by IS NULL AND title IN (?,?,?,?)",
        (
            "Fiche de révision SQL — requêtes de base",
            "Exercices pratiques SQL — SELECT / WHERE / ORDER BY",
            "Fiche de révision SQL — jointures et analyses",
            "Fiche de révision — organiser ses fichiers et dossiers",
        ),
    )
def _migrate_course_schedule(conn):
    """Ajoute les informations de programmation des formations visibles par le public."""
    conn.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS start_date TEXT")
    conn.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS end_date TEXT")
    conn.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS schedule TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT ''")
    conn.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS seats INTEGER NOT NULL DEFAULT 0")
    conn.execute("ALTER TABLE courses ADD COLUMN IF NOT EXISTS registration_open INTEGER NOT NULL DEFAULT 1")

    # Données de démonstration visibles immédiatement après migration.
    # On ne remplit que les cours encore non programmés : une date saisie par le formateur
    # reste la source de vérité.
    demo_schedule = [
        ("SQL – Niveau 1 : Fondamentaux", "2026-10-05", "2026-12-04",
         "Lundi–Vendredi · 08h30–12h30", "INPP Matadi", 25),
        ("SQL – Niveau 2 : Jointures et analyses", "2026-11-02", "2026-12-18",
         "Lundi–Vendredi · 13h30–17h30", "INPP Matadi", 20),
        ("Bureautique – Gérer ses fichiers et dossiers", "2026-10-12", "2026-11-06",
         "Lundi–Vendredi · 08h30–12h30", "INPP Matadi", 30),
    ]
    for title, start, end, schedule, location, seats in demo_schedule:
        conn.execute(
            "UPDATE courses SET start_date=?, end_date=?, schedule=?, location=?, seats=?, registration_open=1 "
            "WHERE title=? AND start_date IS NULL",
            (start, end, schedule, location, seats, title),
        )


def _migrate_bank_settings(conn):
    """Conservée pour compatibilité avec les anciennes versions du schéma."""
    return

def _migrate_reference_catalogue(conn):
    """Aligne une seule fois les écarts visibles sur la fiche papier fournie par l'INPP.
    
    Après cette initialisation, les valeurs en base sont la source de vérité :
    une modification faite par le secrétariat n'est plus écrasée au démarrage.
    """
    done = conn.execute("SELECT 1 FROM settings WHERE key='fiche_reference_v1'").fetchone()
    if done:
        return

    corrections = [
        ("Inspecteur de Protection Industrielle", None, 1, 60),
        ("Froid ménager", None, 6, 90),
        ("Powerpoint", None, 3, 70),
        ("Peinture Design", None, 4, 90),
        ("Académie Cisco : IT Essentials", None, 2, 90),
        ("Robbot", "Robbobat", 3, 70),
        ("Technique de maintenance des équipements hydropneumatiques",
         "Technique de maintenance des installations hydropneumatique", 3, 200),
    ]
    for current_name, new_name, duration, material in corrections:
        if new_name:
            conn.execute(
                "UPDATE filieres SET name=?, duration_months=?, material_fee=? WHERE name=?",
                (new_name, duration, material, current_name),
            )
        else:
            conn.execute(
                "UPDATE filieres SET duration_months=?, material_fee=? WHERE name=?",
                (duration, material, current_name),
            )

    # Trois lignes ajoutées par les données de démonstration ne figurent pas sur la fiche
    # photographiée : elles restent conservées pour l'historique, mais ne sont plus publiées.
    for name in ("Informatique de gestion", "Électricité du bâtiment", "Coupe et couture"):
        conn.execute("UPDATE filieres SET active=0 WHERE name=?", (name,))

    conn.execute(
        "INSERT INTO settings (key,value) VALUES (?,?)",
        ("fiche_reference_v1", "1"),
    )


def init_db():
    conn = connect()
    conn.executescript(_postgres_schema(SCHEMA))
    _migrate_users_roles(conn)
    _migrate_presence(conn)
    _migrate_filiere_details(conn)
    _migrate_services_formateurs(conn)
    _migrate_registration_section(conn)
    _migrate_resource_modules_exam(conn)
    _migrate_course_case_study(conn)
    _migrate_course_schedule(conn)
    _migrate_reference_resources(conn)
    _migrate_bank_settings(conn)
    conn.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", DEFAULT_SETTINGS.items())
    _migrate_reference_catalogue(conn)
    conn.commit()
    conn.close()
