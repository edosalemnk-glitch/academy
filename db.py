"""Accès à la base SQLite et schéma de la plateforme."""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("INPP_DB", os.path.join(BASE_DIR, "formation.db"))

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
    material_fee REAL NOT NULL DEFAULT 0,      -- frais matériel en USD (40, 50, 80 selon la filière)
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

# Tarifs par défaut (modifiables par le secrétariat, page « Tarifs »)
DEFAULT_SETTINGS = {
    "inscription_fee": "40000",   # FC, obligatoire
    "formation_fee": "50000",     # FC par mois
    "jury_fee": "25000",          # FC, obligatoire avant de passer le jury
    "bank_name": "FN BANK",
    "bank_account": "",           # numéro de compte à renseigner dans la page « Tarifs »
}


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrate_users_roles(conn):
    """Bases créées avant le secrétariat : ajoute le rôle « secretaire » à la contrainte de users."""
    row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
    if row is None or "secretaire" in row[0]:
        return
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")   # sinon DROP TABLE users supprimerait les données liées
    try:
        conn.execute("BEGIN")
        conn.execute("CREATE TABLE users_new " + USERS_COLUMNS)
        conn.execute("INSERT INTO users_new (id, full_name, email, password_hash, role, must_change_password, "
                     "created_by, created_at) SELECT id, full_name, email, password_hash, role, "
                     "must_change_password, created_by, created_at FROM users")
        conn.execute("DROP TABLE users")
        conn.execute("ALTER TABLE users_new RENAME TO users")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.execute("PRAGMA foreign_keys = ON")


def _migrate_presence(conn):
    """Bases créées avant le module présences : ajoute les colonnes de liaison manquantes."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(filieres)")}
    if "service_id" not in cols:
        conn.execute("ALTER TABLE filieres ADD COLUMN service_id INTEGER REFERENCES services(id)")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(registrations)")}
    if "section_id" not in cols:
        conn.execute("ALTER TABLE registrations ADD COLUMN section_id INTEGER REFERENCES sections(id)")
    conn.commit()


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    _migrate_users_roles(conn)
    _migrate_presence(conn)
    conn.executemany("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", DEFAULT_SETTINGS.items())
    conn.commit()
    conn.close()
