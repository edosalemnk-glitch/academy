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
    sql = sql.replace("datetime('now',?)", "to_char(CURRENT_TIMESTAMP + (%s || ' days')::interval, 'YYYY-MM-DD HH24:MI:SS')")
    sql = sql.replace("date('now',?)", "to_char(CURRENT_DATE + (%s || ' days')::interval, 'YYYY-MM-DD')")
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
            if line.lstrip().startswith("--"):
                continue
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


def _migrate_filiere_details(conn):
    """Conservée pour compatibilité avec les anciennes versions du schéma."""
    return


def _migrate_bank_settings(conn):
    """Conservée pour compatibilité avec les anciennes versions du schéma."""
    return

def init_db():
    conn = connect()
    conn.executescript(_postgres_schema(SCHEMA))
    _migrate_users_roles(conn)
    _migrate_presence(conn)
    _migrate_filiere_details(conn)
    _migrate_bank_settings(conn)
    conn.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", DEFAULT_SETTINGS.items())
    conn.commit()
    conn.close()
