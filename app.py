"""INPP Académie : plateforme de formation avec abonnement, validation par le formateur et quiz."""
import csv
import io
import mimetypes
import os
import random
import re
import secrets
import string
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import json
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import qrcode
import qrcode.image.svg

import db as database
import fees
import presence
import sqllab
from utils import render_content

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
ALLOWED_EXT = {"gif", "png", "jpg", "jpeg", "webp"}
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "inpp-uploads")
SUPABASE_STORAGE_SIGNED_TTL = int(os.environ.get("SUPABASE_STORAGE_SIGNED_TTL", "3600"))
# Contrôle des frais : mettre INPP_ENFORCE_FEES=1 pour bloquer l'accès tant que le formateur
# n'a pas marqué l'inscription comme « payée » ou « exonérée ».
ENFORCE_FEES = os.environ.get("INPP_ENFORCE_FEES", "0") == "1"
LEVELS = ["Débutant", "Intermédiaire", "Avancé"]
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")

STATUS = {
    "pending": ("En attente de validation", "warn"),
    "approved": ("Inscrit", "ok"),
    "rejected": ("Refusé", "bad"),
    "revoked": ("Accès retiré", "bad"),
}
FEE = {"unpaid": "Non payé", "paid": "Payé", "exempt": "Exonéré"}


def load_secret():
    env = os.environ.get("SECRET_KEY")
    if env:
        return env
    if os.environ.get("RENDER"):
        raise RuntimeError("SECRET_KEY est obligatoire sur Render.")
    path = os.path.join(BASE_DIR, "secret.key")
    if not os.path.exists(path):
        with open(path, "w") as fh:
            fh.write(secrets.token_hex(32))
    with open(path) as fh:
        return fh.read().strip()


app = Flask(__name__)


def seo_base_url():
    return os.environ.get("SEO_BASE_URL", request.url_root).rstrip("/")


@app.context_processor
def inject_seo():
    return {"seo_base_url": seo_base_url}
app.secret_key = load_secret()
app.config.update(
    MAX_CONTENT_LENGTH=8 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "1" if os.environ.get("RENDER") else "0") == "1",
)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.jinja_env.filters["render"] = render_content
app.jinja_env.filters["todict"] = lambda row: dict(row) if row is not None else {}


# ------------------------------------------------------------------ base de données
def get_db():
    if "db" not in g:
        g.db = database.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def ensure_ready():
    database.init_db()
    conn = database.connect()
    empty = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
    if empty and os.environ.get("INPP_SEED_DEMO", "0") == "1":
        import seed
        seed.seed(conn)
    elif os.environ.get("INPP_RESTORE_DEMO", "1") == "1":
        restored = conn.execute("SELECT 1 FROM settings WHERE key='demo_restore_done'").fetchone()
        if not restored:
            import seed
            seed.restore_demo(conn)
            conn.execute("INSERT INTO settings (key,value) VALUES (?,?)", ("demo_restore_done", "1"))
            conn.commit()
    conn.close()


# ------------------------------------------------------------------ sécurité de base
def csrf_field():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    from markupsafe import Markup
    return Markup(f'<input type="hidden" name="_csrf" value="{session["_csrf"]}">')


app.jinja_env.globals["csrf_field"] = csrf_field
app.jinja_env.globals.update(STATUS=STATUS, FEE=FEE, ENFORCE_FEES=ENFORCE_FEES, KINDS=fees.KINDS,
                            TYPES=fees.TYPES, REG_STATUS=fees.STATUS, LETTER=fees.LETTER,
                            PSTATUS=presence.STATUS, NOTICE_KIND=presence.NOTICE_KIND)
app.jinja_env.filters["money"] = fees.format_money
app.jinja_env.globals["today"] = lambda: time.strftime("%Y-%m-%d")


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    if request.is_secure:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "Formulaire expiré. Rechargez la page et recommencez.")


@app.before_request
def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        g.user = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if g.user is None:
            session.clear()
    if (g.user and g.user["must_change_password"]
            and request.endpoint not in ("change_password", "logout", "static")):
        return redirect(url_for("change_password"))


@app.context_processor
def inject_nav():
    pending = 0
    if g.get("user") and g.user["role"] == "formateur":
        pending = get_db().execute(
            "SELECT COUNT(*) FROM enrollments e JOIN courses c ON c.id=e.course_id "
            "WHERE c.trainer_id=? AND e.status='pending'", (g.user["id"],)).fetchone()[0]
    return {"pending_total": pending}


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if not g.user:
            flash("Connectez-vous pour continuer.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*a, **kw)
    return wrapped


def trainer_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if g.user["role"] != "formateur":
            abort(403)
        return view(*a, **kw)
    return wrapped


def secretary_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if g.user["role"] != "secretaire":
            abort(403)
        return view(*a, **kw)
    return wrapped


def safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else None


_login_failures = {}


def too_many_failures(key):
    hits = [t for t in _login_failures.get(key, []) if time.time() - t < 300]
    _login_failures[key] = hits
    return len(hits) >= 5


# ------------------------------------------------------------------ accès aux données
def get_course(course_id):
    row = get_db().execute(
        "SELECT c.*, u.full_name AS trainer_name FROM courses c JOIN users u ON u.id=c.trainer_id "
        "WHERE c.id=?", (course_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def own_course(course_id):
    course = get_course(course_id)
    if course["trainer_id"] != g.user["id"]:
        abort(403)
    return course


def get_lesson(lesson_id):
    row = get_db().execute("SELECT * FROM lessons WHERE id=?", (lesson_id,)).fetchone()
    if row is None:
        abort(404)
    return row


def own_lesson(lesson_id):
    lesson = get_lesson(lesson_id)
    return lesson, own_course(lesson["course_id"])


def get_enrollment(user_id, course_id):
    return get_db().execute("SELECT * FROM enrollments WHERE user_id=? AND course_id=?",
                            (user_id, course_id)).fetchone()


def lessons_of(course_id):
    return get_db().execute("SELECT * FROM lessons WHERE course_id=? ORDER BY position, id",
                            (course_id,)).fetchall()


def progress_of(user_id, course_id):
    lessons = lessons_of(course_id)
    done = {r["lesson_id"] for r in get_db().execute(
        "SELECT p.lesson_id FROM progress p JOIN lessons l ON l.id=p.lesson_id "
        "WHERE p.user_id=? AND l.course_id=?", (user_id, course_id))}
    total = len(lessons)
    return {"lessons": lessons, "done": done, "total": total, "count": len(done),
            "pct": int(100 * len(done) / total) if total else 0,
            "next": next((l for l in lessons if l["id"] not in done), None)}


def lesson_unlocked(lessons, done, lesson_id):
    for l in lessons:
        if l["id"] == lesson_id:
            return True
        if l["id"] not in done:
            return False
    return False


def course_access(course):
    """'preview' pour le formateur propriétaire, 'learner' pour un stagiaire validé, sinon redirection."""
    if g.user["role"] == "formateur":
        if g.user["id"] != course["trainer_id"]:
            abort(403)
        return "preview"
    enr = get_enrollment(g.user["id"], course["id"])
    if not enr or enr["status"] != "approved":
        flash("Vous devez d'abord être validé par le formateur pour suivre ce cours.", "warn")
        abort(redirect(url_for("course_public", course_id=course["id"])))
    if ENFORCE_FEES and course["fee_amount"] > 0 and enr["fee_status"] == "unpaid":
        flash("Les frais de ce cours ne sont pas encore réglés. Contactez le formateur.", "warn")
        abort(redirect(url_for("course_public", course_id=course["id"])))
    return "learner"


def get_exam(course_id):
    """L'examen final du cours (au plus un), ou None si non configuré."""
    return get_db().execute("SELECT * FROM exams WHERE course_id=?", (course_id,)).fetchone()


def exam_window_state(exam):
    """'a_venir' / 'ouvert' / 'ferme' selon opens_at / closes_at (comparés à l'heure du serveur)."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if exam["opens_at"] and now < exam["opens_at"]:
        return "a_venir"
    if exam["closes_at"] and now > exam["closes_at"]:
        return "ferme"
    return "ouvert"


def exam_attempts_of(exam_id, user_id):
    return get_db().execute(
        "SELECT * FROM exam_attempts WHERE exam_id=? AND user_id=? ORDER BY id", (exam_id, user_id)).fetchall()


def maybe_issue_certificate(user_id, course_id):
    """Émet le certificat une fois toutes les leçons validées, et l'examen final réussi s'il existe."""
    conn = get_db()
    prog = progress_of(user_id, course_id)
    if not prog["total"] or prog["count"] != prog["total"]:
        return False
    exam = get_exam(course_id)
    if exam and exam["published"]:
        ok = conn.execute("SELECT 1 FROM exam_attempts WHERE exam_id=? AND user_id=? AND passed=1 LIMIT 1",
                          (exam["id"], user_id)).fetchone()
        if not ok:
            return False
    code = f"INPP-{time.strftime('%Y')}-{secrets.token_hex(3).upper()}"
    conn.execute("INSERT OR IGNORE INTO certificates (user_id, course_id, code) VALUES (?,?,?)",
                 (user_id, course_id, code))
    return True


def temp_password():
    alphabet = string.ascii_letters.replace("l", "").replace("I", "").replace("O", "") + "23456789"
    return "".join(secrets.choice(alphabet) for _ in range(9))


def valid_email(email):
    return bool(EMAIL_RE.fullmatch(email))


# ------------------------------------------------------------------ authentification
@app.route("/inscription", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("index"))
    requested_course_id = request.args.get("course_id", type=int)
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        pwd = request.form.get("password", "")
        if len(name) < 3:
            flash("Indiquez votre nom complet.", "bad")
        elif not valid_email(email):
            flash("Adresse e-mail invalide.", "bad")
        elif len(pwd) < 8:
            flash("Le mot de passe doit contenir au moins 8 caractères.", "bad")
        elif pwd != request.form.get("confirm", ""):
            flash("Les deux mots de passe ne sont pas identiques.", "bad")
        elif get_db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
            flash("Un compte existe déjà avec cette adresse. Connectez-vous.", "bad")
        else:
            cur = get_db().execute(
                "INSERT INTO users (full_name,email,password_hash,role) VALUES (?,?,?,'stagiaire')",
                (name, email, generate_password_hash(pwd)))
            conn = get_db()
            course = None
            if requested_course_id:
                course = conn.execute(
                    "SELECT * FROM courses WHERE id=? AND published=1", (requested_course_id,)
                ).fetchone()
            joined_course = bool(course and course_registration_capacity(course))
            if joined_course:
                conn.execute(
                    "INSERT INTO enrollments (user_id, course_id) VALUES (?,?)",
                    (cur.lastrowid, requested_course_id),
                )
            conn.commit()
            session.clear()
            session["uid"] = cur.lastrowid
            if course:
                if joined_course:
                    flash("Compte créé. Votre demande d'inscription à cette formation a été envoyée au formateur.", "ok")
                else:
                    flash("Compte créé. Cette session n'accepte pas actuellement de nouvelles inscriptions.", "warn")
                return redirect(url_for("course_public", course_id=course["id"]))
            flash("Compte créé. Choisissez une formation et demandez votre inscription.", "ok")
            return redirect(url_for("catalogue"))
    return render_template("register.html")


@app.route("/connexion", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        key = f"{request.remote_addr}|{email}"
        if too_many_failures(key):
            flash("Trop d'essais. Réessayez dans 5 minutes.", "bad")
        else:
            user = get_db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
                _login_failures.pop(key, None)
                session.clear()
                session["uid"] = user["id"]
                return redirect(safe_next(request.args.get("next")) or url_for("index"))
            _login_failures.setdefault(key, []).append(time.time())
            flash("E-mail ou mot de passe incorrect.", "bad")
    return render_template("login.html")


@app.route("/deconnexion", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("catalogue"))


@app.route("/profil/mot-de-passe", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "POST":
        old, new = request.form.get("old", ""), request.form.get("new", "")
        if not check_password_hash(g.user["password_hash"], old):
            flash("Mot de passe actuel incorrect.", "bad")
        elif len(new) < 8:
            flash("Le nouveau mot de passe doit contenir au moins 8 caractères.", "bad")
        elif new != request.form.get("confirm", ""):
            flash("Les deux nouveaux mots de passe ne sont pas identiques.", "bad")
        else:
            get_db().execute("UPDATE users SET password_hash=?, must_change_password=0 WHERE id=?",
                             (generate_password_hash(new), g.user["id"]))
            get_db().commit()
            flash("Mot de passe modifié.", "ok")
            return redirect(url_for("index"))
    return render_template("change_password.html")


# ------------------------------------------------------------------ vitrine publique
@app.route("/")
def index():
    if g.user and g.user["role"] == "formateur":
        return redirect(url_for("trainer_dashboard"))
    if g.user and g.user["role"] == "secretaire":
        return redirect(url_for("sec_dashboard"))
    if g.user:
        return redirect(url_for("my_courses"))
    conn = get_db()
    stats = {
        "filieres": conn.execute("SELECT COUNT(*) FROM filieres WHERE active=1").fetchone()[0],
        "cours": conn.execute("SELECT COUNT(*) FROM courses WHERE published=1").fetchone()[0],
        "stagiaires": conn.execute(
            "SELECT COUNT(*) FROM registrations WHERE card_code IS NOT NULL").fetchone()[0],
        "certificats": conn.execute("SELECT COUNT(*) FROM certificates").fetchone()[0],
    }
    upcoming = conn.execute(
        "SELECT c.*, u.full_name AS trainer_name, "
        "(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id AND e.status IN ('pending','approved')) AS nb_reserved "
        "FROM courses c JOIN users u ON u.id=c.trainer_id "
        "WHERE c.published=1 AND c.start_date IS NOT NULL "
        "AND c.start_date >= to_char(CURRENT_DATE, 'YYYY-MM-DD') "
        "ORDER BY c.start_date, c.id LIMIT 3"
    ).fetchall()
    return render_template("home.html", stats=stats, upcoming=upcoming)


@app.route("/a-propos")
def apropos():
    return render_template("apropos.html")


def public_catalogue():
    """Retourne les lignes de la fiche de renseignements, dans l'ordre du catalogue."""
    rows = get_db().execute(
        "SELECT f.*, s.name AS service_name, "
        "(SELECT COUNT(*) FROM registrations r WHERE r.filiere_id=f.id) AS nb_stagiaires "
        "FROM filieres f LEFT JOIN services s ON s.id=f.service_id "
        "WHERE f.active=1 ORDER BY f.id"
    ).fetchall()
    groups = []
    by_service = {}
    for row in rows:
        service_name = row["service_name"] or "Service non précisé"
        if service_name not in by_service:
            group = {"name": service_name, "rows": []}
            by_service[service_name] = group
            groups.append(group)
        by_service[service_name]["rows"].append(row)
    return rows, groups


def course_schedule_state(course):
    """État public d'une formation programmée."""
    today = datetime.now().date()
    start = None
    end = None
    if course["start_date"]:
        try:
            start = datetime.strptime(str(course["start_date"])[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    if course["end_date"]:
        try:
            end = datetime.strptime(str(course["end_date"])[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    if start and today < start:
        return "a_venir"
    if start and (not end or today <= end):
        return "en_cours"
    if end and today > end:
        return "terminee"
    return "non_programmee"


def course_schedule_label(course):
    labels = {
        "a_venir": "Prochainement",
        "en_cours": "En cours",
        "terminee": "Terminée",
        "non_programmee": "Date à confirmer",
    }
    return labels[course_schedule_state(course)]


def course_registration_capacity(course):
    if not course["registration_open"]:
        return False
    if course_schedule_state(course) not in ("a_venir", "en_cours"):
        return False
    if course["seats"] and get_db().execute(
        "SELECT COUNT(*) FROM enrollments WHERE course_id=? AND status IN ('pending','approved')",
        (course["id"],)
    ).fetchone()[0] >= course["seats"]:
        return False
    return True


@app.route("/filieres")
def filieres_public():
    rows, groups = public_catalogue()
    return render_template("filieres_public.html", filieres=rows, groups=groups)


@app.route("/services")
def services_public():
    conn = get_db()
    services = conn.execute(
        "SELECT s.*, u.full_name AS chef_name, "
        "(SELECT COUNT(*) FROM filieres f WHERE f.service_id=s.id AND f.active=1) AS nb_filieres, "
        "(SELECT COUNT(*) FROM service_formateurs sf WHERE sf.service_id=s.id) AS nb_formateurs, "
        "(SELECT COUNT(*) FROM courses c WHERE c.service_id=s.id AND c.published=1) AS nb_cours "
        "FROM services s LEFT JOIN users u ON u.id=s.chef_id "
        "WHERE s.active=1 ORDER BY s.name"
    ).fetchall()
    return render_template("services_public.html", services=services)


@app.route("/services/<int:service_id>")
def service_public(service_id):
    conn = get_db()
    service = conn.execute(
        "SELECT s.*, u.full_name AS chef_name FROM services s "
        "LEFT JOIN users u ON u.id=s.chef_id WHERE s.id=? AND s.active=1", (service_id,)
    ).fetchone()
    if not service:
        abort(404)
    filieres = conn.execute(
        "SELECT * FROM filieres WHERE service_id=? AND active=1 ORDER BY name", (service_id,)
    ).fetchall()
    formateurs = conn.execute(
        "SELECT u.id, u.full_name FROM service_formateurs sf JOIN users u ON u.id=sf.user_id "
        "WHERE sf.service_id=? AND u.role='formateur' ORDER BY u.full_name", (service_id,)
    ).fetchall()
    courses = conn.execute(
        "SELECT c.*, u.full_name AS trainer_name, "
        "(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id AND e.status IN ('pending','approved')) AS nb_reserved "
        "FROM courses c JOIN users u ON u.id=c.trainer_id "
        "WHERE c.service_id=? AND c.published=1 ORDER BY c.start_date NULLS LAST, c.title", (service_id,)
    ).fetchall()
    for course in courses:
        course["schedule_state"] = course_schedule_state(course)
        course["schedule_label"] = course_schedule_label(course)
        course["registration_available"] = course_registration_capacity(course)
    return render_template("service_public.html", service=service, filieres=filieres,
                           formateurs=formateurs, courses=courses)


@app.route("/faq")
def faq():
    return render_template("faq.html")


@app.route("/contact")
def contact():
    return render_template("contact.html", cfg=get_settings())


@app.route("/robots.txt")
def robots_txt():
    lines = ["User-agent: *", "Allow: /", "Disallow: /formateur", "Disallow: /secretariat",
             "Disallow: /mes-cours", "Disallow: /profil", f"Sitemap: {seo_base_url()}/sitemap.xml"]
    return Response("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    conn = get_db()
    urls = [url_for("index"), url_for("catalogue"), url_for("apropos"), url_for("filieres_public"),
url_for("procedure"), url_for("faq"), url_for("contact"), url_for("login"), url_for("register")]
    for c in conn.execute("SELECT id FROM courses WHERE published=1"):
        urls.append(url_for("course_public", course_id=c["id"]))
    body = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for u in urls:
        body.append(f"<url><loc>{seo_base_url()}{u}</loc></url>")
    body.append("</urlset>")
    return Response("\n".join(body), mimetype="application/xml")


@app.route("/catalogue")
def catalogue():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    level = request.args.get("level", "").strip()
    status = request.args.get("status", "a_venir").strip()
    month = request.args.get("month", "").strip()
    sql = ("SELECT c.*, u.full_name AS trainer_name, "
           "(SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) AS nb_lessons, "
           "(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id "
           "AND e.status IN ('pending','approved')) AS nb_reserved "
           "FROM courses c JOIN users u ON u.id=c.trainer_id WHERE c.published=1")
    params = []
    if q:
        sql += " AND (c.title ILIKE ? OR c.category ILIKE ? OR c.description ILIKE ? OR c.location ILIKE ?)"
        params = [f"%{q}%"] * 4
    if category:
        sql += " AND c.category=?"
        params.append(category)
    if level:
        sql += " AND c.level=?"
        params.append(level)
    courses = list(get_db().execute(sql + " ORDER BY c.start_date NULLS LAST, c.category, c.id", params).fetchall())
    for course in courses:
        course["schedule_state"] = course_schedule_state(course)
        course["schedule_label"] = course_schedule_label(course)
        course["registration_available"] = course_registration_capacity(course)
    if status != "toutes":
        courses = [c for c in courses if c["schedule_state"] == status]
    if month:
        courses = [c for c in courses if c["start_date"] and str(c["start_date"]).startswith(month)]
    categories = [r[0] for r in get_db().execute(
        "SELECT DISTINCT category FROM courses WHERE published=1 ORDER BY category"
    ).fetchall()]
    levels = [r[0] for r in get_db().execute(
        "SELECT DISTINCT level FROM courses WHERE published=1 ORDER BY level"
    ).fetchall()]
    months = sorted({
        str(c["start_date"])[:7] for c in get_db().execute(
            "SELECT start_date FROM courses WHERE published=1 AND start_date IS NOT NULL ORDER BY start_date"
        ).fetchall()
    })
    enrollments = {}
    if g.user:
        enrollments = {r["course_id"]: r for r in get_db().execute(
            "SELECT * FROM enrollments WHERE user_id=?", (g.user["id"],))}
    return render_template(
        "catalogue.html", courses=courses, enrollments=enrollments, q=q,
        category=category, level=level, status=status, month=month,
        categories=categories, levels=levels, months=months,
    )


@app.route("/catalogue.pdf")
def catalogue_pdf():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    level = request.args.get("level", "").strip()
    status = request.args.get("status", "a_venir").strip()
    month = request.args.get("month", "").strip()
    sql = ("SELECT c.*, u.full_name AS trainer_name, "
           "(SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) AS nb_lessons, "
           "(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id "
           "AND e.status IN ('pending','approved')) AS nb_reserved "
           "FROM courses c JOIN users u ON u.id=c.trainer_id WHERE c.published=1")
    params = []
    if q:
        sql += " AND (c.title ILIKE ? OR c.category ILIKE ? OR c.description ILIKE ? OR c.location ILIKE ?)"
        params = [f"%{q}%"] * 4
    if category:
        sql += " AND c.category=?"
        params.append(category)
    if level:
        sql += " AND c.level=?"
        params.append(level)
    courses = list(get_db().execute(sql + " ORDER BY c.start_date NULLS LAST, c.category, c.id", params).fetchall())
    for course in courses:
        course["schedule_state"] = course_schedule_state(course)
        course["schedule_label"] = course_schedule_label(course)
    if status != "toutes":
        courses = [c for c in courses if c["schedule_state"] == status]
    if month:
        courses = [c for c in courses if c["start_date"] and str(c["start_date"]).startswith(month)]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=10*mm, leftMargin=10*mm, topMargin=35*mm, bottomMargin=12*mm,
        title="Programmation des formations INPP Académie", author="INPP Académie",
    )
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("ScheduleCell", parent=styles["BodyText"], fontName="Helvetica",
                          fontSize=7.2, leading=8.5)
    head = ParagraphStyle("ScheduleHead", parent=cell, fontName="Helvetica-Bold",
                          fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.white)
    title = ParagraphStyle("ScheduleTitle", parent=styles["Title"], fontName="Helvetica-Bold",
                           fontSize=16, leading=19, alignment=TA_CENTER,
                           textColor=colors.HexColor("#2e6da4"), spaceAfter=3*mm)
    story = [
        Paragraph("PROGRAMMATION DES FORMATIONS", title),
        Paragraph("Formations publiées · dates, lieux, horaires et inscriptions",
                  ParagraphStyle("ScheduleSub", parent=cell, alignment=TA_CENTER, fontSize=8.5)),
        Spacer(1, 3*mm),
    ]
    rows = [[Paragraph(x, head) for x in
             ["Formation", "Catégorie", "Niveau", "Dates", "Lieu", "Horaire", "Places", "Frais"]]]
    for c in courses:
        dates = "Date à confirmer"
        if c["start_date"]:
            dates = str(c["start_date"])[:10]
            if c["end_date"]:
                dates += " → " + str(c["end_date"])[:10]
        seats = "—"
        if c["seats"]:
            seats = f"{c['nb_reserved']}/{c['seats']}"
        fee = f"{c['fee_amount']:g} {c['currency']}" if c["fee_amount"] else "Gratuit"
        rows.append([
            Paragraph(c["title"], cell), Paragraph(c["category"], cell), Paragraph(c["level"], cell),
            Paragraph(dates, cell), Paragraph(c["location"] or "—", cell),
            Paragraph(c["schedule"] or "—", cell), Paragraph(seats, cell), Paragraph(fee, cell)
        ])
    if len(rows) == 1:
        rows.append([Paragraph("Aucune formation ne correspond aux filtres.", cell)] + [""] * 7)
    table = Table(rows, repeatRows=1, colWidths=[47*mm, 30*mm, 25*mm, 34*mm, 42*mm, 34*mm, 18*mm, 22*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#2e6da4")),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#cfd7df")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f4f7fa")]),
        ("LEFTPADDING", (0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
    ]))
    story.append(table)
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph(
        "Pour vous inscrire : ouvrez la fiche de la formation, créez votre compte si nécessaire, "
        "puis envoyez votre demande d'inscription. La validation est effectuée par le formateur.",
        ParagraphStyle("ScheduleNote", parent=cell, fontSize=8, leading=10)
    ))
    doc.build(story, onFirstPage=_pdf_logo, onLaterPages=_pdf_logo)
    buffer.seek(0)
    return Response(buffer.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": "inline; filename=programmation-formations-INPP.pdf"})


@app.route("/cours/<int:course_id>")
def course_public(course_id):
    course = get_course(course_id)
    if not course["published"] and not (g.user and g.user["id"] == course["trainer_id"]):
        abort(404)
    enrollment = get_enrollment(g.user["id"], course_id) if g.user else None
    return render_template(
        "course_public.html", course=course, lessons=lessons_of(course_id),
        enrollment=enrollment, schedule_state=course_schedule_state(course),
        schedule_label=course_schedule_label(course),
        registration_available=course_registration_capacity(course),
    )


@app.route("/cours/<int:course_id>/abonner", methods=["POST"])
@login_required
def subscribe(course_id):
    course = get_course(course_id)
    if g.user["role"] != "stagiaire":
        abort(403)
    conn = get_db()
    if not course_registration_capacity(course):
        flash("Les inscriptions à cette session ne sont pas ouvertes ou la capacité est atteinte.", "warn")
        return redirect(url_for("course_public", course_id=course_id))
    enr = get_enrollment(g.user["id"], course_id)
    if enr is None:
        conn.execute("INSERT INTO enrollments (user_id, course_id) VALUES (?,?)", (g.user["id"], course_id))
        flash("Demande envoyée. Le formateur doit valider votre inscription avant l'accès au cours.", "ok")
    elif enr["status"] in ("rejected", "revoked"):
        conn.execute("UPDATE enrollments SET status='pending', requested_at=datetime('now'), "
                     "decided_at=NULL, decided_by=NULL WHERE id=?", (enr["id"],))
        flash("Nouvelle demande envoyée au formateur.", "ok")
    else:
        flash("Vous avez déjà une inscription pour ce cours.", "info")
    conn.commit()
    return redirect(url_for("course_public", course_id=course["id"]))


# ------------------------------------------------------------------ espace stagiaire
@app.route("/mes-cours")
@login_required
def my_courses():
    if g.user["role"] == "formateur":
        return redirect(url_for("trainer_dashboard"))
    if g.user["role"] == "secretaire":
        return redirect(url_for("sec_dashboard"))
    rows = get_db().execute(
        "SELECT e.*, c.title, c.category, c.level, c.fee_amount, c.currency FROM enrollments e "
        "JOIN courses c ON c.id=e.course_id WHERE e.user_id=? ORDER BY e.requested_at DESC",
        (g.user["id"],)).fetchall()
    items = []
    for e in rows:
        prog = progress_of(g.user["id"], e["course_id"]) if e["status"] == "approved" else None
        cert = get_db().execute("SELECT code FROM certificates WHERE user_id=? AND course_id=?",
                                (g.user["id"], e["course_id"])).fetchone()
        items.append({"e": e, "prog": prog, "cert": cert})
    return render_template("my_courses.html", items=items)


@app.route("/apprendre/<int:course_id>")
@login_required
def learn(course_id):
    course = get_course(course_id)
    mode = course_access(course)
    prog = progress_of(g.user["id"], course_id)
    cert = get_db().execute("SELECT code FROM certificates WHERE user_id=? AND course_id=?",
                            (g.user["id"], course_id)).fetchone()
    counts = {r["lesson_id"]: r["n"] for r in get_db().execute(
        "SELECT lesson_id, COUNT(*) n FROM questions WHERE lesson_id IN "
        "(SELECT id FROM lessons WHERE course_id=?) GROUP BY lesson_id", (course_id,))}
    exam = get_exam(course_id)
    exam_attempt = None
    if exam and mode == "learner":
        attempts = exam_attempts_of(exam["id"], g.user["id"])
        exam_attempt = attempts[-1] if attempts else None
    return render_template("learn.html", course=course, prog=prog, mode=mode, cert=cert, counts=counts,
                           exam=exam, exam_attempt=exam_attempt)


@app.route("/lecon/<int:lesson_id>")
@login_required
def lesson(lesson_id):
    les = get_lesson(lesson_id)
    course = get_course(les["course_id"])
    mode = course_access(course)
    prog = progress_of(g.user["id"], course["id"])
    if mode == "learner" and not lesson_unlocked(prog["lessons"], prog["done"], lesson_id):
        flash("Terminez d'abord la leçon précédente (quiz réussi) pour débloquer celle-ci.", "warn")
        return redirect(url_for("learn", course_id=course["id"]))
    nb_questions = get_db().execute("SELECT COUNT(*) FROM questions WHERE lesson_id=?",
                                    (lesson_id,)).fetchone()[0]
    ids = [l["id"] for l in prog["lessons"]]
    idx = ids.index(lesson_id)
    return render_template("lesson.html", lesson=les, course=course, prog=prog, mode=mode,
                           nb_questions=nb_questions, index=idx + 1,
                           prev_id=ids[idx - 1] if idx > 0 else None,
                           next_id=ids[idx + 1] if idx + 1 < len(ids) else None,
                           completed=lesson_id in prog["done"])


@app.route("/lecon/<int:lesson_id>/terminer", methods=["POST"])
@login_required
def complete_lesson(lesson_id):
    les = get_lesson(lesson_id)
    course = get_course(les["course_id"])
    if course_access(course) != "learner":
        return redirect(url_for("lesson", lesson_id=lesson_id))
    conn = get_db()
    if conn.execute("SELECT COUNT(*) FROM questions WHERE lesson_id=?", (lesson_id,)).fetchone()[0]:
        abort(400, "Cette leçon a un quiz : il faut le réussir pour la valider.")
    prog = progress_of(g.user["id"], course["id"])
    if not lesson_unlocked(prog["lessons"], prog["done"], lesson_id):
        abort(403)
    conn.execute("INSERT OR IGNORE INTO progress (user_id, lesson_id, best_score) VALUES (?,?,100)",
                 (g.user["id"], lesson_id))
    if maybe_issue_certificate(g.user["id"], course["id"]):
        flash("Formation terminée : votre certificat est disponible.", "ok")
    conn.commit()
    return redirect(url_for("learn", course_id=course["id"]))


@app.route("/lecon/<int:lesson_id>/quiz", methods=["GET", "POST"])
@login_required
def quiz(lesson_id):
    les = get_lesson(lesson_id)
    course = get_course(les["course_id"])
    mode = course_access(course)
    conn = get_db()
    prog = progress_of(g.user["id"], course["id"])
    if mode == "learner" and not lesson_unlocked(prog["lessons"], prog["done"], lesson_id):
        return redirect(url_for("learn", course_id=course["id"]))
    questions = conn.execute("SELECT * FROM questions WHERE lesson_id=? ORDER BY id", (lesson_id,)).fetchall()
    if not questions:
        flash("Cette leçon n'a pas encore de quiz.", "info")
        return redirect(url_for("lesson", lesson_id=lesson_id))

    if request.method == "GET":
        shuffled = []
        for q in random.sample(list(questions), len(questions)):
            opts = [(k, q["option_" + k.lower()]) for k in "ABCD"]
            random.shuffle(opts)
            shuffled.append({"q": q, "opts": opts})
        return render_template("quiz.html", lesson=les, course=course, items=shuffled, mode=mode)

    results, good = [], 0
    for q in questions:
        chosen = request.form.get(f"q_{q['id']}")
        ok = chosen == q["correct"]
        good += ok
        results.append({"q": q, "chosen": chosen, "ok": ok})
    score = round(100 * good / len(questions))
    passed = score >= course["pass_mark"]
    certificate = False
    if mode == "learner":
        conn.execute("INSERT INTO attempts (user_id, lesson_id, score, passed) VALUES (?,?,?,?)",
                     (g.user["id"], lesson_id, score, int(passed)))
        if passed:
            conn.execute(
                "INSERT INTO progress (user_id, lesson_id, best_score) VALUES (?,?,?) "
                "ON CONFLICT(user_id, lesson_id) DO UPDATE SET best_score=MAX(best_score, excluded.best_score)",
                (g.user["id"], lesson_id, score))
            certificate = maybe_issue_certificate(g.user["id"], course["id"])
        conn.commit()
    ids = [l["id"] for l in prog["lessons"]]
    idx = ids.index(lesson_id)
    return render_template("quiz_result.html", lesson=les, course=course, results=results, score=score,
                           good=good, total=len(questions), passed=passed, mode=mode, certificate=certificate,
                           next_id=ids[idx + 1] if idx + 1 < len(ids) else None)


@app.route("/certificat/<code>")
def certificate(code):
    row = get_db().execute(
        "SELECT ct.*, u.full_name, c.title, c.level, t.full_name AS trainer_name "
        "FROM certificates ct JOIN users u ON u.id=ct.user_id JOIN courses c ON c.id=ct.course_id "
        "JOIN users t ON t.id=c.trainer_id WHERE ct.code=?", (code,)).fetchone()
    if row is None:
        abort(404)
    return render_template("certificate.html", cert=row)


@app.route("/cours/<int:course_id>/examen")
@login_required
def exam_intro(course_id):
    course = get_course(course_id)
    exam = get_exam(course_id)
    if exam is None or not exam["published"]:
        abort(404)
    if course_access(course) != "learner":
        return redirect(url_for("learn", course_id=course_id))
    prog = progress_of(g.user["id"], course_id)
    lessons_done = bool(prog["total"]) and prog["count"] == prog["total"]
    attempts = exam_attempts_of(exam["id"], g.user["id"])
    ongoing = next((a for a in attempts if a["submitted_at"] is None), None)
    return render_template("exam_intro.html", course=course, exam=exam, lessons_done=lessons_done,
                           attempts=attempts, state=exam_window_state(exam), ongoing=ongoing)


@app.route("/cours/<int:course_id>/examen/commencer", methods=["POST"])
@login_required
def exam_start(course_id):
    course = get_course(course_id)
    exam = get_exam(course_id)
    if exam is None or not exam["published"]:
        abort(404)
    if course_access(course) != "learner":
        abort(403)
    prog = progress_of(g.user["id"], course_id)
    if not prog["total"] or prog["count"] != prog["total"]:
        flash("Terminez d'abord toutes les leçons du cours.", "warn")
        return redirect(url_for("exam_intro", course_id=course_id))
    if exam_window_state(exam) != "ouvert":
        flash("L'examen n'est pas ouvert pour le moment. Revenez pendant le créneau annoncé par votre formateur.",
              "warn")
        return redirect(url_for("exam_intro", course_id=course_id))
    conn = get_db()
    attempts = exam_attempts_of(exam["id"], g.user["id"])
    ongoing = next((a for a in attempts if a["submitted_at"] is None), None)
    if ongoing:
        return redirect(url_for("exam_take", attempt_id=ongoing["id"]))
    if len(attempts) >= exam["max_attempts"]:
        flash("Vous avez déjà utilisé toutes vos tentatives pour cet examen.", "warn")
        return redirect(url_for("exam_intro", course_id=course_id))
    nb_q = conn.execute("SELECT COUNT(*) FROM exam_questions WHERE exam_id=?", (exam["id"],)).fetchone()[0]
    if not nb_q:
        flash("L'examen n'a pas encore de questions ; revenez plus tard.", "info")
        return redirect(url_for("exam_intro", course_id=course_id))
    attempt_id = conn.execute("INSERT INTO exam_attempts (exam_id, user_id) VALUES (?,?)",
                              (exam["id"], g.user["id"])).lastrowid
    conn.commit()
    return redirect(url_for("exam_take", attempt_id=attempt_id))


def get_exam_attempt(attempt_id):
    row = get_db().execute(
        "SELECT ea.id AS attempt_id, ea.exam_id, ea.user_id, ea.score, ea.passed, ea.late, "
        "ea.started_at, ea.submitted_at, e.course_id, e.title, e.duration_minutes, e.pass_mark, "
        "e.max_attempts, e.opens_at, e.closes_at, e.published "
        "FROM exam_attempts ea JOIN exams e ON e.id=ea.exam_id WHERE ea.id=?", (attempt_id,)).fetchone()
    if row is None:
        abort(404)
    if row["user_id"] != g.user["id"]:
        abort(403)
    return row


@app.route("/examen/<int:attempt_id>", methods=["GET", "POST"])
@login_required
def exam_take(attempt_id):
    attempt = get_exam_attempt(attempt_id)
    course = get_course(attempt["course_id"])
    if attempt["submitted_at"] is not None:
        return redirect(url_for("exam_result", attempt_id=attempt_id))
    conn = get_db()
    questions = conn.execute("SELECT * FROM exam_questions WHERE exam_id=? ORDER BY id",
                             (attempt["exam_id"],)).fetchall()
    deadline = (datetime.strptime(attempt["started_at"], "%Y-%m-%d %H:%M:%S")
               + timedelta(minutes=attempt["duration_minutes"]))
    now = datetime.now()
    seconds_left = max(0, int((deadline - now).total_seconds()))

    # Le temps écoulé (fermeture du navigateur, etc.) déclenche une correction automatique dès
    # qu'un formulaire est soumis ou que la page est rouverte après l'échéance : aucune réponse
    # cochée compte comme fausse, ce qui protège contre une tentative laissée ouverte indéfiniment.
    if request.method == "POST" or seconds_left <= 0:
        results, good = [], 0
        for q in questions:
            chosen = request.form.get(f"q_{q['id']}")
            ok = chosen == q["correct"]
            good += ok
            results.append({"q": q, "chosen": chosen, "ok": ok})
        score = round(100 * good / len(questions)) if questions else 0
        late = now > deadline
        passed = score >= attempt["pass_mark"] and not late
        conn.execute("UPDATE exam_attempts SET score=?, passed=?, late=?, submitted_at=datetime('now') "
                     "WHERE id=?", (score, int(passed), int(late), attempt_id))
        if passed:
            maybe_issue_certificate(g.user["id"], course["id"])
        conn.commit()
        return redirect(url_for("exam_result", attempt_id=attempt_id))

    shuffled = []
    for q in random.sample(list(questions), len(questions)):
        opts = [(k, q["option_" + k.lower()]) for k in "ABCD"]
        random.shuffle(opts)
        shuffled.append({"q": q, "opts": opts})
    return render_template("exam_take.html", course=course, exam=attempt, items=shuffled,
                           seconds_left=seconds_left)


@app.route("/examen/<int:attempt_id>/resultat")
@login_required
def exam_result(attempt_id):
    attempt = get_exam_attempt(attempt_id)
    if attempt["submitted_at"] is None:
        return redirect(url_for("exam_take", attempt_id=attempt_id))
    course = get_course(attempt["course_id"])
    cert = get_db().execute("SELECT code FROM certificates WHERE user_id=? AND course_id=?",
                            (g.user["id"], course["id"])).fetchone()
    return render_template("exam_result.html", course=course, exam=attempt, cert=cert)


@app.route("/terrain-sql", methods=["GET", "POST"])
@login_required
def sql_lab():
    challenge_id = request.form.get("challenge", type=int) or request.args.get("defi", type=int)
    default_sql = "SELECT " if request.args.get("defi") else "SELECT * FROM employes;"
    sql = request.form.get("sql", default_sql)
    result, error, verdict = None, None, None
    if request.method == "POST":
        try:
            cols, rows, truncated = sqllab.run_query(sql)
            result = {"cols": cols, "rows": rows, "truncated": truncated}
            if challenge_id:
                verdict = sqllab.check_challenge(challenge_id, rows)
        except sqllab.LabError as exc:
            error = str(exc)
    return render_template("sql_lab.html", sql=sql, result=result, error=error, verdict=verdict,
                           challenge_id=challenge_id, tables=sqllab.TABLES, challenges=sqllab.CHALLENGES,
                           max_rows=sqllab.MAX_ROWS)


# ------------------------------------------------------------------ espace formateur
@app.route("/formateur")
@trainer_required
def trainer_dashboard():
    conn = get_db()
    courses = conn.execute(
        "SELECT c.*, "
        "(SELECT COUNT(*) FROM lessons l WHERE l.course_id=c.id) AS nb_lessons, "
        "(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id AND e.status='approved') AS nb_learners, "
        "(SELECT COUNT(*) FROM enrollments e WHERE e.course_id=c.id AND e.status='pending') AS nb_pending "
        "FROM courses c WHERE c.trainer_id=? ORDER BY c.title", (g.user["id"],)).fetchall()
    blocked = conn.execute(
        "SELECT u.full_name, c.id AS course_id, c.title AS course, l.title AS lesson, COUNT(*) AS fails "
        "FROM attempts a JOIN users u ON u.id=a.user_id JOIN lessons l ON l.id=a.lesson_id "
        "JOIN courses c ON c.id=l.course_id WHERE c.trainer_id=? AND a.passed=0 AND NOT EXISTS "
        "(SELECT 1 FROM progress p WHERE p.user_id=a.user_id AND p.lesson_id=a.lesson_id) "
        "GROUP BY a.user_id, a.lesson_id, u.full_name, c.id, c.title, l.title HAVING COUNT(*)>=3 ORDER BY fails DESC LIMIT 10",
        (g.user["id"],)).fetchall()
    recent = conn.execute(
        "SELECT u.full_name, c.title AS course, l.title AS lesson, a.score, a.passed, a.created_at "
        "FROM attempts a JOIN users u ON u.id=a.user_id JOIN lessons l ON l.id=a.lesson_id "
        "JOIN courses c ON c.id=l.course_id WHERE c.trainer_id=? ORDER BY a.created_at DESC, a.id DESC LIMIT 8",
        (g.user["id"],)).fetchall()
    nb_stagiaires = conn.execute("SELECT COUNT(*) FROM users WHERE role='stagiaire'").fetchone()[0]
    return render_template("formateur/dashboard.html", courses=courses, blocked=blocked, recent=recent,
                           nb_stagiaires=nb_stagiaires)


def read_course_form():
    f = request.form
    title = f.get("title", "").strip()
    try:
        fee = max(0.0, float(f.get("fee_amount", "0").replace(",", ".") or 0))
        mark = min(100, max(1, int(f.get("pass_mark", "70") or 70)))
        seats = max(0, int(f.get("seats", "0") or 0))
        start_date = f.get("start_date", "").strip() or None
        end_date = f.get("end_date", "").strip() or None
        if start_date:
            datetime.strptime(start_date, "%Y-%m-%d")
        if end_date:
            datetime.strptime(end_date, "%Y-%m-%d")
        if start_date and end_date and end_date < start_date:
            return None, "La date de fin doit être postérieure ou égale à la date de début."
    except ValueError:
        return None, "Les frais, les places ou les dates sont invalides."
    if len(title) < 3:
        return None, "Donnez un titre au cours."
    level = f.get("level") if f.get("level") in LEVELS else LEVELS[0]
    return {"title": title, "category": f.get("category", "").strip() or "Général", "level": level,
            "description": f.get("description", "").strip(),
            "case_study": f.get("case_study", "").strip(),
            "fee_amount": fee, "pass_mark": mark,
            "start_date": start_date, "end_date": end_date,
            "schedule": f.get("schedule", "").strip(),
            "location": f.get("location", "").strip(),
            "seats": seats,
            "registration_open": 1 if f.get("registration_open") else 0,
            "published": 1 if f.get("published") else 0}, None


@app.route("/formateur/cours/nouveau", methods=["GET", "POST"])
@trainer_required
def course_new():
    if request.method == "POST":
        data, err = read_course_form()
        if err:
            flash(err, "bad")
        else:
            cur = get_db().execute(
                "INSERT INTO courses (title, category, level, description, case_study, fee_amount, pass_mark, "
                "published, start_date, end_date, schedule, location, seats, registration_open, trainer_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (data["title"], data["category"], data["level"], data["description"], data["case_study"],
                 data["fee_amount"], data["pass_mark"], data["published"], data["start_date"], data["end_date"],
                 data["schedule"], data["location"], data["seats"], data["registration_open"], g.user["id"]))
            get_db().commit()
            flash("Cours créé. Ajoutez maintenant des leçons.", "ok")
            return redirect(url_for("course_manage", course_id=cur.lastrowid))
    services = get_db().execute("SELECT id, name FROM services WHERE active=1 ORDER BY name").fetchall()
    return render_template("formateur/course_form.html", course=None, levels=LEVELS, services=services)


@app.route("/formateur/cours/<int:course_id>/modifier", methods=["GET", "POST"])
@trainer_required
def course_edit(course_id):
    course = own_course(course_id)
    if request.method == "POST":
        data, err = read_course_form()
        if err:
            flash(err, "bad")
        else:
            get_db().execute(
                "UPDATE courses SET title=?, category=?, level=?, description=?, case_study=?, "
                "fee_amount=?, pass_mark=?, published=?, start_date=?, end_date=?, schedule=?, "
                "location=?, seats=?, registration_open=?, service_id=? WHERE id=?",
                (data["title"], data["category"], data["level"], data["description"], data["case_study"],
                 data["fee_amount"], data["pass_mark"], data["published"], data["start_date"], data["end_date"],
                 data["schedule"], data["location"], data["seats"], data["registration_open"], data["service_id"], course_id))
            get_db().commit()
            flash("Cours mis à jour.", "ok")
            return redirect(url_for("course_manage", course_id=course_id))
    services = get_db().execute("SELECT id, name FROM services WHERE active=1 ORDER BY name").fetchall()
    return render_template("formateur/course_form.html", course=course, levels=LEVELS, services=services)


@app.route("/formateur/cours/<int:course_id>/supprimer", methods=["POST"])
@trainer_required
def course_delete(course_id):
    own_course(course_id)
    get_db().execute("DELETE FROM courses WHERE id=?", (course_id,))
    get_db().commit()
    flash("Cours supprimé avec ses leçons, quiz et inscriptions.", "ok")
    return redirect(url_for("trainer_dashboard"))


@app.route("/formateur/cours/<int:course_id>")
@trainer_required
def course_manage(course_id):
    course = own_course(course_id)
    lessons = get_db().execute(
        "SELECT l.*, (SELECT COUNT(*) FROM questions q WHERE q.lesson_id=l.id) AS nb_questions "
        "FROM lessons l WHERE l.course_id=? ORDER BY position, id", (course_id,)).fetchall()
    pending = get_db().execute("SELECT COUNT(*) FROM enrollments WHERE course_id=? AND status='pending'",
                               (course_id,)).fetchone()[0]
    exam = get_exam(course_id)
    exam_nb_questions = 0
    exam_nb_attempts = 0
    if exam:
        exam_nb_questions = get_db().execute("SELECT COUNT(*) FROM exam_questions WHERE exam_id=?",
                                             (exam["id"],)).fetchone()[0]
        exam_nb_attempts = get_db().execute("SELECT COUNT(*) FROM exam_attempts WHERE exam_id=?",
                                            (exam["id"],)).fetchone()[0]
    return render_template("formateur/course_manage.html", course=course, lessons=lessons, pending=pending,
                           exam=exam, exam_nb_questions=exam_nb_questions, exam_nb_attempts=exam_nb_attempts)


# --- examen final (distinct des quiz de leçon : fenêtre programmée, tentatives limitées, chrono)
@app.route("/formateur/cours/<int:course_id>/examen", methods=["GET", "POST"])
@trainer_required
def exam_config(course_id):
    course = own_course(course_id)
    conn = get_db()
    exam = get_exam(course_id)
    if request.method == "POST":
        f = request.form

        def clean_dt(name):
            val = f.get(name, "").strip().replace("T", " ")
            if not val:
                return None
            return val + (":00" if len(val) == 16 else "")

        title = f.get("title", "").strip() or "Examen final"
        duration = f.get("duration_minutes", type=int) or 30
        pass_mark = min(100, max(1, f.get("pass_mark", type=int) or 70))
        max_attempts = max(1, f.get("max_attempts", type=int) or 1)
        opens_at, closes_at = clean_dt("opens_at"), clean_dt("closes_at")
        published = 1 if f.get("published") else 0
        if exam:
            conn.execute(
                "UPDATE exams SET title=?, duration_minutes=?, pass_mark=?, max_attempts=?, "
                "opens_at=?, closes_at=?, published=? WHERE course_id=?",
                (title, duration, pass_mark, max_attempts, opens_at, closes_at, published, course_id))
        else:
            conn.execute(
                "INSERT INTO exams (course_id, title, duration_minutes, pass_mark, max_attempts, "
                "opens_at, closes_at, published) VALUES (?,?,?,?,?,?,?,?)",
                (course_id, title, duration, pass_mark, max_attempts, opens_at, closes_at, published))
        conn.commit()
        flash("Examen enregistré.", "ok")
        return redirect(url_for("exam_config", course_id=course_id))
    exam = get_exam(course_id)
    nb_questions = 0
    if exam:
        nb_questions = conn.execute("SELECT COUNT(*) FROM exam_questions WHERE exam_id=?",
                                    (exam["id"],)).fetchone()[0]
    return render_template("formateur/exam_form.html", course=course, exam=exam, nb_questions=nb_questions)


@app.route("/formateur/cours/<int:course_id>/examen/questions", methods=["GET", "POST"])
@trainer_required
def exam_questions(course_id):
    course = own_course(course_id)
    exam = get_exam(course_id)
    if exam is None:
        flash("Configurez d'abord l'examen avant d'ajouter des questions.", "info")
        return redirect(url_for("exam_config", course_id=course_id))
    conn = get_db()
    edit = None
    if request.args.get("edit", type=int):
        edit = conn.execute("SELECT * FROM exam_questions WHERE id=? AND exam_id=?",
                            (request.args.get("edit", type=int), exam["id"])).fetchone()
    if request.method == "POST":
        f = request.form
        vals = [f.get(k, "").strip() for k in ("text", "option_a", "option_b", "option_c", "option_d")]
        correct = f.get("correct", "")
        if not all(vals) or correct not in ("A", "B", "C", "D"):
            flash("Remplissez la question, les 4 réponses et indiquez la bonne réponse.", "bad")
        else:
            qid = f.get("qid", type=int)
            if qid:
                conn.execute("UPDATE exam_questions SET text=?, option_a=?, option_b=?, option_c=?, "
                             "option_d=?, correct=?, explanation=? WHERE id=? AND exam_id=?",
                             (*vals, correct, f.get("explanation", "").strip(), qid, exam["id"]))
                flash("Question modifiée.", "ok")
            else:
                conn.execute("INSERT INTO exam_questions (exam_id, text, option_a, option_b, option_c, "
                             "option_d, correct, explanation) VALUES (?,?,?,?,?,?,?,?)",
                             (exam["id"], *vals, correct, f.get("explanation", "").strip()))
                flash("Question ajoutée.", "ok")
            conn.commit()
            return redirect(url_for("exam_questions", course_id=course_id))
    qs = conn.execute("SELECT * FROM exam_questions WHERE exam_id=? ORDER BY id", (exam["id"],)).fetchall()
    return render_template("formateur/exam_questions.html", course=course, exam=exam, questions=qs, edit=edit)


@app.route("/formateur/examen/questions/<int:qid>/supprimer", methods=["POST"])
@trainer_required
def exam_question_delete(qid):
    conn = get_db()
    q = conn.execute("SELECT eq.*, e.course_id FROM exam_questions eq JOIN exams e ON e.id=eq.exam_id "
                     "WHERE eq.id=?", (qid,)).fetchone()
    if q is None:
        abort(404)
    own_course(q["course_id"])
    conn.execute("DELETE FROM exam_questions WHERE id=?", (qid,))
    conn.commit()
    flash("Question supprimée.", "ok")
    return redirect(url_for("exam_questions", course_id=q["course_id"]))


@app.route("/formateur/cours/<int:course_id>/examen/resultats")
@trainer_required
def exam_results(course_id):
    course = own_course(course_id)
    exam = get_exam(course_id)
    if exam is None:
        abort(404)
    rows = get_db().execute(
        "SELECT ea.*, u.full_name FROM exam_attempts ea JOIN users u ON u.id=ea.user_id "
        "WHERE ea.exam_id=? ORDER BY ea.started_at DESC", (exam["id"],)).fetchall()
    return render_template("formateur/exam_results.html", course=course, exam=exam, attempts=rows)


def _storage_enabled():
    return bool(
        SUPABASE_URL
        and SUPABASE_SERVICE_ROLE_KEY
        and SUPABASE_URL.startswith(("http://", "https://"))
    )


def _storage_request(method, path, body=None, content_type=None):
    """Appelle l'API Storage Supabase avec la clé service-role côté serveur uniquement."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise RuntimeError("Supabase Storage n'est pas configuré.")
    if not SUPABASE_URL.startswith(("http://", "https://")):
        raise RuntimeError(
            "SUPABASE_URL doit être l'URL du projet Supabase, par exemple "
            "'https://<project-ref>.supabase.co', et non l'hôte PostgreSQL."
        )
    url = f"{SUPABASE_URL}/storage/v1/{path.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
    }
    if content_type:
        headers["Content-Type"] = content_type
    request_data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(url, data=request_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase Storage ({exc.code}) : {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Supabase Storage est momentanément inaccessible.") from exc


def save_image(file):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXT or not (file.mimetype or "").startswith("image/"):
        raise ValueError("Image non acceptée (formats : gif, png, jpg, jpeg, webp).")
    safe_name = secure_filename(file.filename)
    if not safe_name:
        raise ValueError("Nom de fichier invalide.")
    if _storage_enabled():
        name = f"lessons/{uuid.uuid4().hex[:12]}_{safe_name}"
        _storage_request(
            "POST",
            f"object/{urllib.parse.quote(SUPABASE_STORAGE_BUCKET, safe='')}/{urllib.parse.quote(name, safe='')}",
            body=file.read(),
            content_type=file.mimetype or "application/octet-stream",
        )
        return name

    name = f"{uuid.uuid4().hex[:12]}_{safe_name}"
    file.save(os.path.join(UPLOAD_FOLDER, name))
    return name


def remove_image(name):
    if not name:
        return
    if _storage_enabled() and str(name).startswith("lessons/"):
        try:
            _storage_request(
                "POST",
                f"object/remove/{urllib.parse.quote(SUPABASE_STORAGE_BUCKET, safe='')}",
                body=json.dumps({"prefixes": [name]}),
                content_type="application/json",
            )
        except RuntimeError:
            app.logger.exception("Impossible de supprimer l'image Supabase %s", name)
        return
    path = os.path.join(UPLOAD_FOLDER, os.path.basename(name))
    if os.path.exists(path):
        os.remove(path)


def lesson_image_url(name):
    """Retourne l’URL interne de diffusion d’une image de leçon."""
    if not name:
        return ""
    if _storage_enabled() and str(name).startswith("lessons/"):
        return url_for("lesson_image_proxy", name=name)
    return url_for("static", filename=f"uploads/{os.path.basename(name)}")


@app.route("/media/lecon/<path:name>")
@login_required
def lesson_image_proxy(name):
    """Diffuse une image privée via une URL signée temporaire, sans exposer la clé service-role."""
    if not str(name).startswith("lessons/") or not _storage_enabled():
        abort(404)
    try:
        raw = _storage_request(
            "POST",
            f"object/sign/{urllib.parse.quote(SUPABASE_STORAGE_BUCKET, safe='')}/{urllib.parse.quote(name, safe='/')}",
            body=json.dumps({"expiresIn": SUPABASE_STORAGE_SIGNED_TTL}),
            content_type="application/json",
        )
        data = json.loads(raw.decode("utf-8"))
        signed = data.get("signedURL") or data.get("signedUrl")
        if not signed:
            raise RuntimeError("URL signée absente de la réponse Supabase.")
        if not signed.startswith("http"):
            if signed.startswith("/storage/v1/"):
                signed = f"{SUPABASE_URL}{signed}"
            else:
                signed = f"{SUPABASE_URL}/storage/v1/{signed.lstrip('/')}"
        # L’URL signée contient déjà le jeton d’accès temporaire.
        # On redirige directement le navigateur vers Supabase afin d’éviter
        # les problèmes de diffusion binaire à travers Flask/Render.
        return redirect(signed)
    except (RuntimeError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        app.logger.exception("Impossible de récupérer l’image Supabase %s", name)
        abort(404)

app.jinja_env.globals["lesson_image_url"] = lesson_image_url


@app.route("/formateur/cours/<int:course_id>/lecons/nouvelle", methods=["GET", "POST"])
@trainer_required
def lesson_new(course_id):
    course = own_course(course_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if len(title) < 3:
            flash("Donnez un titre à la leçon.", "bad")
        else:
            try:
                image = save_image(request.files.get("image"))
            except ValueError as exc:
                flash(str(exc), "bad")
                return render_template("formateur/lesson_form.html", course=course, lesson=None)
            pos = get_db().execute("SELECT COALESCE(MAX(position),0)+1 FROM lessons WHERE course_id=?",
                                   (course_id,)).fetchone()[0]
            cur = get_db().execute(
                "INSERT INTO lessons (course_id, position, title, content, image) VALUES (?,?,?,?,?)",
                (course_id, pos, title, request.form.get("content", ""), image))
            get_db().commit()
            flash("Leçon ajoutée. Ajoutez maintenant les questions du quiz.", "ok")
            return redirect(url_for("questions", lesson_id=cur.lastrowid))
    return render_template("formateur/lesson_form.html", course=course, lesson=None)


@app.route("/formateur/lecons/<int:lesson_id>/modifier", methods=["GET", "POST"])
@trainer_required
def lesson_edit(lesson_id):
    les, course = own_lesson(lesson_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        if len(title) < 3:
            flash("Donnez un titre à la leçon.", "bad")
        else:
            image = les["image"]
            try:
                new_image = save_image(request.files.get("image"))
            except ValueError as exc:
                flash(str(exc), "bad")
                return render_template("formateur/lesson_form.html", course=course, lesson=les)
            if new_image or request.form.get("remove_image"):
                remove_image(image)
                image = new_image
            get_db().execute("UPDATE lessons SET title=?, content=?, image=? WHERE id=?",
                             (title, request.form.get("content", ""), image, lesson_id))
            get_db().commit()
            flash("Leçon mise à jour.", "ok")
            return redirect(url_for("course_manage", course_id=course["id"]))
    return render_template("formateur/lesson_form.html", course=course, lesson=les)


@app.route("/formateur/lecons/<int:lesson_id>/supprimer", methods=["POST"])
@trainer_required
def lesson_delete(lesson_id):
    les, course = own_lesson(lesson_id)
    remove_image(les["image"])
    get_db().execute("DELETE FROM lessons WHERE id=?", (lesson_id,))
    get_db().commit()
    flash("Leçon supprimée.", "ok")
    return redirect(url_for("course_manage", course_id=course["id"]))


@app.route("/formateur/lecons/<int:lesson_id>/deplacer", methods=["POST"])
@trainer_required
def lesson_move(lesson_id):
    les, course = own_lesson(lesson_id)
    lessons = lessons_of(course["id"])
    ids = [l["id"] for l in lessons]
    i = ids.index(lesson_id)
    j = i - 1 if request.form.get("dir") == "up" else i + 1
    if 0 <= j < len(ids):
        ids[i], ids[j] = ids[j], ids[i]
        for pos, lid in enumerate(ids, start=1):
            get_db().execute("UPDATE lessons SET position=? WHERE id=?", (pos, lid))
        get_db().commit()
    return redirect(url_for("course_manage", course_id=course["id"]))


@app.route("/formateur/lecons/<int:lesson_id>/questions", methods=["GET", "POST"])
@trainer_required
def questions(lesson_id):
    les, course = own_lesson(lesson_id)
    conn = get_db()
    edit = None
    if request.args.get("edit", type=int):
        edit = conn.execute("SELECT * FROM questions WHERE id=? AND lesson_id=?",
                            (request.args.get("edit", type=int), lesson_id)).fetchone()
    if request.method == "POST":
        f = request.form
        vals = [f.get(k, "").strip() for k in ("text", "option_a", "option_b", "option_c", "option_d")]
        correct = f.get("correct", "")
        if not all(vals) or correct not in ("A", "B", "C", "D"):
            flash("Remplissez la question, les 4 réponses et indiquez la bonne réponse.", "bad")
        else:
            qid = f.get("qid", type=int)
            if qid:
                conn.execute("UPDATE questions SET text=?, option_a=?, option_b=?, option_c=?, option_d=?, "
                             "correct=?, explanation=? WHERE id=? AND lesson_id=?",
                             (*vals, correct, f.get("explanation", "").strip(), qid, lesson_id))
                flash("Question modifiée.", "ok")
            else:
                conn.execute("INSERT INTO questions (lesson_id, text, option_a, option_b, option_c, option_d, "
                             "correct, explanation) VALUES (?,?,?,?,?,?,?,?)",
                             (lesson_id, *vals, correct, f.get("explanation", "").strip()))
                flash("Question ajoutée.", "ok")
            conn.commit()
            return redirect(url_for("questions", lesson_id=lesson_id))
    qs = conn.execute("SELECT * FROM questions WHERE lesson_id=? ORDER BY id", (lesson_id,)).fetchall()
    return render_template("formateur/questions.html", lesson=les, course=course, questions=qs, edit=edit)


@app.route("/formateur/questions/<int:qid>/supprimer", methods=["POST"])
@trainer_required
def question_delete(qid):
    q = get_db().execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
    if q is None:
        abort(404)
    own_lesson(q["lesson_id"])
    get_db().execute("DELETE FROM questions WHERE id=?", (qid,))
    get_db().commit()
    flash("Question supprimée.", "ok")
    return redirect(url_for("questions", lesson_id=q["lesson_id"]))


# --- inscriptions (validation anti-fraude)
@app.route("/formateur/cours/<int:course_id>/inscriptions")
@trainer_required
def enrollments(course_id):
    course = own_course(course_id)
    conn = get_db()
    rows = conn.execute(
        "SELECT e.*, u.full_name, u.email FROM enrollments e JOIN users u ON u.id=e.user_id "
        "WHERE e.course_id=? ORDER BY e.requested_at DESC", (course_id,)).fetchall()
    groups = {k: [r for r in rows if r["status"] == k] for k in STATUS}
    available = conn.execute(
        "SELECT id, full_name, email FROM users WHERE role='stagiaire' AND id NOT IN "
        "(SELECT user_id FROM enrollments WHERE course_id=? AND status IN ('approved','pending')) "
        "ORDER BY full_name", (course_id,)).fetchall()
    return render_template("formateur/enrollments.html", course=course, groups=groups, available=available)


@app.route("/formateur/inscriptions/<int:eid>/<action>", methods=["POST"])
@trainer_required
def enrollment_action(eid, action):
    enr = get_db().execute("SELECT * FROM enrollments WHERE id=?", (eid,)).fetchone()
    if enr is None:
        abort(404)
    own_course(enr["course_id"])
    status_actions = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}
    fee_actions = {"paid": "paid", "unpaid": "unpaid", "exempt": "exempt"}
    if action in status_actions:
        get_db().execute("UPDATE enrollments SET status=?, decided_at=datetime('now'), decided_by=? WHERE id=?",
                         (status_actions[action], g.user["id"], eid))
    elif action in fee_actions:
        get_db().execute("UPDATE enrollments SET fee_status=? WHERE id=?", (fee_actions[action], eid))
    else:
        abort(404)
    get_db().commit()
    flash("Modification enregistrée.", "ok")
    return redirect(url_for("enrollments", course_id=enr["course_id"]))


@app.route("/formateur/cours/<int:course_id>/ajouter-stagiaires", methods=["POST"])
@trainer_required
def enroll_learners(course_id):
    own_course(course_id)
    ids = [int(i) for i in request.form.getlist("user_ids") if i.isdigit()]
    fee = request.form.get("fee_status", "unpaid")
    fee = fee if fee in FEE else "unpaid"
    added = 0
    for uid in ids:
        user = get_db().execute("SELECT id FROM users WHERE id=? AND role='stagiaire'", (uid,)).fetchone()
        if not user:
            continue
        get_db().execute(
            "INSERT INTO enrollments (user_id, course_id, status, fee_status, decided_at, decided_by) "
            "VALUES (?,?, 'approved', ?, datetime('now'), ?) "
            "ON CONFLICT(user_id, course_id) DO UPDATE SET status='approved', fee_status=excluded.fee_status, "
            "decided_at=datetime('now'), decided_by=excluded.decided_by",
            (uid, course_id, fee, g.user["id"]))
        added += 1
    get_db().commit()
    flash(f"{added} stagiaire(s) inscrit(s) et validé(s)." if added else "Aucun stagiaire sélectionné.",
          "ok" if added else "info")
    return redirect(url_for("enrollments", course_id=course_id))


# --- suivi
def tracking_data(course_id):
    conn = get_db()
    lessons = lessons_of(course_id)
    learners = conn.execute(
        "SELECT u.id, u.full_name, u.email, e.fee_status FROM enrollments e JOIN users u ON u.id=e.user_id "
        "WHERE e.course_id=? AND e.status='approved' ORDER BY u.full_name", (course_id,)).fetchall()
    best = {(r["user_id"], r["lesson_id"]): r["best_score"] for r in conn.execute(
        "SELECT p.* FROM progress p JOIN lessons l ON l.id=p.lesson_id WHERE l.course_id=?", (course_id,))}
    att = {(r["user_id"], r["lesson_id"]): r for r in conn.execute(
        "SELECT a.user_id, a.lesson_id, COUNT(*) AS n, SUM(1-a.passed) AS fails, MAX(a.created_at) AS last "
        "FROM attempts a JOIN lessons l ON l.id=a.lesson_id WHERE l.course_id=? "
        "GROUP BY a.user_id, a.lesson_id", (course_id,))}
    certs = {r["user_id"] for r in conn.execute("SELECT user_id FROM certificates WHERE course_id=?", (course_id,))}
    rows = []
    for u in learners:
        cells, done, last, blocked = [], 0, None, None
        scores = []
        for l in lessons:
            key = (u["id"], l["id"])
            a = att.get(key)
            if key in best:
                done += 1
                scores.append(best[key])
                state = "done"
            elif a and a["fails"] >= 1:
                state = "fail"
                if a["fails"] >= 3 and blocked is None:
                    blocked = l["title"]
            else:
                state = "todo"
            if a and (last is None or a["last"] > last):
                last = a["last"]
            cells.append({"state": state, "score": best.get(key), "fails": a["fails"] if a else 0})
        rows.append({"u": u, "cells": cells, "done": done, "total": len(lessons),
                     "pct": int(100 * done / len(lessons)) if lessons else 0,
                     "avg": round(sum(scores) / len(scores)) if scores else None,
                     "last": last, "blocked": blocked, "cert": u["id"] in certs})
    return lessons, rows


@app.route("/formateur/cours/<int:course_id>/suivi")
@trainer_required
def tracking(course_id):
    course = own_course(course_id)
    lessons, rows = tracking_data(course_id)
    return render_template("formateur/tracking.html", course=course, lessons=lessons, rows=rows)


@app.route("/formateur/cours/<int:course_id>/suivi.csv")
@trainer_required
def tracking_csv(course_id):
    course = own_course(course_id)
    _, rows = tracking_data(course_id)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Stagiaire", "E-mail", "Frais", "Leçons validées", "Total leçons", "Progression %",
                "Moyenne quiz %", "Dernière activité", "Certificat"])
    for r in rows:
        w.writerow([r["u"]["full_name"], r["u"]["email"], FEE[r["u"]["fee_status"]], r["done"], r["total"],
                    r["pct"], r["avg"] if r["avg"] is not None else "", r["last"] or "",
                    "Oui" if r["cert"] else "Non"])
    data = "\ufeff" + buf.getvalue()
    name = re.sub(r"[^A-Za-z0-9]+", "_", course["title"]).strip("_")
    return Response(data, mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=suivi_{name}.csv"})


# --- gestion des comptes stagiaires
@app.route("/formateur/stagiaires", methods=["GET", "POST"])
@trainer_required
def learners():
    conn = get_db()
    created = None
    if request.method == "POST":
        raw = request.form.get("bulk", "")
        course_id = request.form.get("course_id", type=int)
        if course_id:
            own_course(course_id)
        created, errors = [], []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            m = EMAIL_RE.search(line)
            name = re.sub(r"[;,|\t]+", " ", line.replace(m.group(0), "")).strip() if m else ""
            if not m or len(name) < 3:
                errors.append(f"Ligne ignorée (format « Nom ; e-mail ») : {line}")
                continue
            email = m.group(0).lower()
            if conn.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
                errors.append(f"Compte déjà existant : {email}")
                continue
            pwd = temp_password()
            uid = conn.execute(
                "INSERT INTO users (full_name,email,password_hash,role,must_change_password,created_by) "
                "VALUES (?,?,?,'stagiaire',1,?)", (name, email, generate_password_hash(pwd), g.user["id"])).lastrowid
            if course_id:
                conn.execute("INSERT INTO enrollments (user_id, course_id, status, decided_at, decided_by) "
                             "VALUES (?,?,'approved',datetime('now'),?)", (uid, course_id, g.user["id"]))
            created.append({"name": name, "email": email, "password": pwd})
        conn.commit()
        for e in errors:
            flash(e, "bad")
    rows = conn.execute(
        "SELECT u.*, (SELECT COUNT(*) FROM enrollments e WHERE e.user_id=u.id AND e.status='approved') AS nb_courses "
        "FROM users u WHERE u.role='stagiaire' ORDER BY u.full_name").fetchall()
    my_courses_list = conn.execute("SELECT id, title FROM courses WHERE trainer_id=? ORDER BY title",
                                   (g.user["id"],)).fetchall()
    return render_template("formateur/learners.html", learners=rows, courses=my_courses_list, created=created)


@app.route("/formateur/stagiaires/<int:uid>/reinitialiser", methods=["POST"])
@trainer_required
def reset_password(uid):
    user = get_db().execute("SELECT * FROM users WHERE id=? AND role='stagiaire'", (uid,)).fetchone()
    if user is None:
        abort(404)
    pwd = temp_password()
    get_db().execute("UPDATE users SET password_hash=?, must_change_password=1 WHERE id=?",
                     (generate_password_hash(pwd), uid))
    get_db().commit()
    flash(f"Nouveau mot de passe temporaire pour {user['full_name']} : {pwd} (à transmettre au stagiaire).", "ok")
    return redirect(url_for("learners"))


# ------------------------------------------------------------------ secrétariat / réception
def get_settings():
    return {r["key"]: r["value"] for r in get_db().execute("SELECT key, value FROM settings")}


def get_reg(rid):
    row = get_db().execute(
        "SELECT r.*, f.name AS filiere FROM registrations r JOIN filieres f ON f.id=r.filiere_id "
        "WHERE r.id=?", (rid,)).fetchone()
    if row is None:
        abort(404)
    return row


def reg_payments(rid):
    return get_db().execute(
        "SELECT p.*, u.full_name AS agent FROM payments p LEFT JOIN users u ON u.id=p.recorded_by "
        "WHERE p.registration_id=? ORDER BY p.id DESC", (rid,)).fetchall()


def registry_rows(where="", params=()):
    """Stagiaires du registre avec leur situation financière calculée."""
    conn = get_db()
    regs = conn.execute(
        "SELECT r.*, f.name AS filiere FROM registrations r JOIN filieres f ON f.id=r.filiere_id "
        + where + " ORDER BY r.id", params).fetchall()
    pays = {}
    for p in conn.execute("SELECT * FROM payments WHERE voided=0"):
        pays.setdefault(p["registration_id"], []).append(p)
    return [{"r": r, "s": fees.summarize(r, pays.get(r["id"], []))} for r in regs]


def refresh_card(rid):
    """Délivre la carte de stagiaire dès que le stagiaire est en ordre. Retourne True si elle vient d'être créée."""
    reg = get_reg(rid)
    if reg["card_code"]:
        return False
    summary = fees.summarize(reg, get_db().execute(
        "SELECT * FROM payments WHERE registration_id=? AND voided=0", (rid,)).fetchall())
    if not summary["en_ordre"]:
        return False
    code = f"INPP-CS-{time.strftime('%Y')}-{secrets.token_hex(3).upper()}"
    get_db().execute("UPDATE registrations SET card_code=?, card_issued_at=datetime('now') WHERE id=?", (code, rid))
    return True


def parse_number(text):
    try:
        return float(str(text).replace(" ", "").replace("\u202f", "").replace(",", "."))
    except ValueError:
        return None


# ------------------------------------------------------------------ présences (sections, cartes QR, pointage)
def get_section(sid):
    row = get_db().execute(
        "SELECT s.*, f.name AS filiere, u.full_name AS trainer_name FROM sections s "
        "JOIN filieres f ON f.id=s.filiere_id JOIN users u ON u.id=s.trainer_id WHERE s.id=?", (sid,)).fetchone()
    if row is None:
        abort(404)
    return row


def own_section(sid):
    section = get_section(sid)
    if section["trainer_id"] != g.user["id"]:
        abort(403)
    return section


def section_members(sid):
    return get_db().execute(
        "SELECT r.* FROM registrations r WHERE r.section_id=? ORDER BY r.full_name", (sid,)).fetchall()


def attendance_for(sid, day):
    return {a["registration_id"]: a for a in get_db().execute(
        "SELECT * FROM attendance WHERE section_id=? AND day=?", (sid, day))}


def mark_attendance(sid, rid, status, source="formateur", note="", checkin_at=None, marked_by=None, day=None):
    day = day or presence.today()
    get_db().execute(
        "INSERT INTO attendance (section_id, registration_id, day, status, checkin_at, source, note, marked_by) "
        "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (section_id, registration_id, day) DO UPDATE SET "
        "status=excluded.status, checkin_at=excluded.checkin_at, source=excluded.source, "
        "note=excluded.note, marked_by=excluded.marked_by",
        (sid, rid, day, status, checkin_at, source, note, marked_by))


@app.route("/carte/<code>/qr.svg")
def card_qr(code):
    reg = get_db().execute("SELECT id FROM registrations WHERE card_code=?", (code,)).fetchone()
    if reg is None:
        abort(404)
    target = request.host_url + "carte/" + code
    img = qrcode.make(target, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), mimetype="image/svg+xml",
                    headers={"Cache-Control": "no-store"})


@app.route("/carte/<code>/signaler", methods=["GET", "POST"])
def card_notice(code):
    reg = get_db().execute("SELECT * FROM registrations WHERE card_code=?", (code,)).fetchone()
    if reg is None:
        abort(404)
    if not reg["section_id"]:
        flash("Vous n'êtes affecté à aucune section de formation pour le moment. "
              "Adressez-vous au secrétariat ou à votre formateur.", "warn")
        return redirect(url_for("card_verify", code=code))
    section = get_section(reg["section_id"])
    if request.method == "POST":
        kind = request.form.get("kind", "")
        for_day = request.form.get("for_day", "").strip()
        message = re.sub(r"\s+", " ", request.form.get("message", "")).strip()
        if kind not in presence.NOTICE_KIND:
            flash("Choisissez le motif : absence ou retard.", "bad")
        elif not re.fullmatch(r"\d{4}-\d{2}-\d{2}", for_day):
            flash("Indiquez la date concernée.", "bad")
        elif len(message) < 3:
            flash("Expliquez brièvement la raison, en quelques mots.", "bad")
        else:
            get_db().execute(
                "INSERT INTO absence_notices (registration_id, section_id, for_day, kind, message) "
                "VALUES (?,?,?,?,?)", (reg["id"], section["id"], for_day, kind, message))
            get_db().commit()
            flash("Message envoyé à votre formateur.", "ok")
            return redirect(url_for("card_verify", code=code))
    return render_template("carte_signaler.html", reg=reg, section=section, today=presence.today())


@app.route("/formateur/presences")
@trainer_required
def sections_list():
    conn = get_db()
    sections = conn.execute(
        "SELECT s.*, f.name AS filiere, "
        "(SELECT COUNT(*) FROM registrations r WHERE r.section_id=s.id) AS nb_membres, "
        "(SELECT COUNT(*) FROM absence_notices n WHERE n.section_id=s.id AND n.status='attente') AS nb_attente "
        "FROM sections s JOIN filieres f ON f.id=s.filiere_id WHERE s.trainer_id=? "
        "ORDER BY s.active DESC, s.name", (g.user["id"],)).fetchall()
    filieres = conn.execute("SELECT * FROM filieres WHERE active=1 ORDER BY name").fetchall()
    return render_template("formateur/sections.html", sections=sections, filieres=filieres, day=presence.today())


@app.route("/formateur/presences/nouvelle", methods=["POST"])
@trainer_required
def section_new():
    conn = get_db()
    name = re.sub(r"\s+", " ", request.form.get("name", "")).strip()
    filiere = conn.execute("SELECT * FROM filieres WHERE id=? AND active=1",
                           (request.form.get("filiere_id", type=int),)).fetchone()
    start = request.form.get("start_time", "08:30").strip()
    end = request.form.get("end_time", "12:30").strip()
    grace = request.form.get("grace_minutes", type=int)
    if len(name) < 2 or filiere is None:
        flash("Indiquez le nom de la section et choisissez une filière.", "bad")
    elif not (presence.valid_hm(start) and presence.valid_hm(end)):
        flash("Les heures de début et de fin doivent être au format HH:MM.", "bad")
    elif grace is None or not 0 <= grace <= 120:
        flash("La tolérance doit être un nombre de minutes entre 0 et 120.", "bad")
    else:
        cur = conn.execute(
            "INSERT INTO sections (filiere_id, trainer_id, name, start_time, grace_minutes, end_time) "
            "VALUES (?,?,?,?,?,?)", (filiere["id"], g.user["id"], name, start, grace, end))
        conn.commit()
        flash("Section créée. Ajoutez-y des stagiaires puis ouvrez le pointage.", "ok")
        return redirect(url_for("section_detail", sid=cur.lastrowid))
    return redirect(url_for("sections_list"))


@app.route("/formateur/presences/<int:sid>/modifier", methods=["POST"])
@trainer_required
def section_edit(sid):
    section = own_section(sid)
    name = re.sub(r"\s+", " ", request.form.get("name", "")).strip()
    start = request.form.get("start_time", "").strip()
    end = request.form.get("end_time", "").strip()
    grace = request.form.get("grace_minutes", type=int)
    if (len(name) < 2 or not (presence.valid_hm(start) and presence.valid_hm(end))
            or grace is None or not 0 <= grace <= 120):
        flash("Vérifiez le nom, les heures (HH:MM) et la tolérance (0 à 120 minutes).", "bad")
    else:
        get_db().execute(
            "UPDATE sections SET name=?, start_time=?, end_time=?, grace_minutes=?, active=? WHERE id=?",
            (name, start, end, grace, 1 if request.form.get("active") else 0, sid))
        get_db().commit()
        flash("Section mise à jour.", "ok")
    return redirect(url_for("section_detail", sid=section["id"]))


@app.route("/formateur/presences/<int:sid>")
@trainer_required
def section_detail(sid):
    section = own_section(sid)
    day = request.args.get("jour", "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = presence.today()
    members = section_members(sid)
    att = attendance_for(sid, day)
    q = request.args.get("q", "").strip()
    candidates = []
    if q:
        candidates = get_db().execute(
            "SELECT * FROM registrations WHERE filiere_id=? AND (section_id IS NULL OR section_id!=?) "
            "AND (full_name LIKE ? OR card_code LIKE ?) ORDER BY full_name LIMIT 10",
            (section["filiere_id"], sid, f"%{q}%", f"%{q}%")).fetchall()
    return render_template("formateur/section_detail.html", section=section, members=members, att=att,
                           day=day, q=q, candidates=candidates, limit_hm=presence.grace_limit(section))


@app.route("/formateur/presences/<int:sid>/ajouter", methods=["POST"])
@trainer_required
def section_add_member(sid):
    section = own_section(sid)
    rid = request.form.get("rid", type=int)
    reg = get_db().execute("SELECT * FROM registrations WHERE id=? AND filiere_id=?",
                           (rid, section["filiere_id"])).fetchone()
    if reg is None:
        flash("Stagiaire introuvable dans cette filière.", "bad")
    else:
        get_db().execute("UPDATE registrations SET section_id=? WHERE id=?", (sid, rid))
        get_db().commit()
        flash(f"{reg['full_name']} ajouté à la section.", "ok")
    return redirect(url_for("section_detail", sid=sid))


@app.route("/formateur/presences/<int:sid>/retirer/<int:rid>", methods=["POST"])
@trainer_required
def section_remove_member(sid, rid):
    own_section(sid)
    get_db().execute("UPDATE registrations SET section_id=NULL WHERE id=? AND section_id=?", (rid, sid))
    get_db().commit()
    flash("Stagiaire retiré de la section.", "info")
    return redirect(url_for("section_detail", sid=sid))


@app.route("/formateur/presences/<int:sid>/pointer/<int:rid>", methods=["POST"])
@trainer_required
def section_mark(sid, rid):
    section = own_section(sid)
    reg = get_db().execute("SELECT * FROM registrations WHERE id=? AND section_id=?", (rid, sid)).fetchone()
    if reg is None:
        abort(404)
    status = request.form.get("status", "")
    note = request.form.get("note", "").strip()
    day = request.form.get("day", "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        day = presence.today()
    if status not in presence.MANUAL_STATUS:
        flash("Statut invalide.", "bad")
    else:
        mark_attendance(sid, rid, status, source="formateur", note=note, marked_by=g.user["id"], day=day)
        get_db().commit()
        flash(f"{reg['full_name']} : {presence.STATUS[status][0].lower()} le {day}.", "ok")
    return redirect(url_for("section_detail", sid=sid, jour=day))


@app.route("/formateur/presences/<int:sid>/pointage")
@trainer_required
def section_kiosk(sid):
    section = own_section(sid)
    return render_template("formateur/pointage.html", section=section, limit_hm=presence.grace_limit(section),
                           result=None)


@app.route("/formateur/presences/<int:sid>/scan", methods=["POST"])
@trainer_required
def section_scan(sid):
    section = own_section(sid)
    code = presence.extract_card_code(request.form.get("code", ""))
    result = {"ok": False, "message": "Carte non reconnue."}
    if code:
        reg = get_db().execute(
            "SELECT * FROM registrations WHERE card_code=? AND section_id=?", (code, sid)).fetchone()
        if reg is None:
            result["message"] = "Cette carte n'appartient pas à un stagiaire de cette section."
        else:
            status = presence.compute_status(section)
            mark_attendance(sid, reg["id"], status, source="qr", checkin_at=presence.now_hm(),
                            marked_by=g.user["id"])
            get_db().commit()
            result = {"ok": True, "name": reg["full_name"], "status": status,
                      "label": presence.STATUS[status][0], "css": presence.STATUS[status][1],
                      "time": presence.now_hm()}
    return render_template("formateur/pointage.html", section=section, limit_hm=presence.grace_limit(section),
                           result=result)


@app.route("/formateur/presences/<int:sid>/messages")
@trainer_required
def section_messages(sid):
    section = own_section(sid)
    notices = get_db().execute(
        "SELECT n.*, r.full_name FROM absence_notices n JOIN registrations r ON r.id=n.registration_id "
        "WHERE n.section_id=? ORDER BY (n.status='attente') DESC, n.for_day DESC, n.id DESC", (sid,)).fetchall()
    return render_template("formateur/messages.html", section=section, notices=notices)


@app.route("/formateur/presences/<int:sid>/messages/<int:nid>/decider", methods=["POST"])
@trainer_required
def section_notice_decide(sid, nid):
    own_section(sid)
    notice = get_db().execute("SELECT * FROM absence_notices WHERE id=? AND section_id=?", (nid, sid)).fetchone()
    if notice is None:
        abort(404)
    status = request.form.get("status", "")
    if status not in presence.MANUAL_STATUS:
        flash("Statut invalide.", "bad")
    else:
        mark_attendance(sid, notice["registration_id"], status, source="formateur",
                        note=f"Suite au message du stagiaire ({presence.NOTICE_KIND[notice['kind']]}).",
                        marked_by=g.user["id"], day=notice["for_day"])
        get_db().execute(
            "UPDATE absence_notices SET status='traite', decided_status=?, decided_by=?, "
            "decided_at=datetime('now') WHERE id=?", (status, g.user["id"], nid))
        get_db().commit()
        flash("Message traité et présence mise à jour.", "ok")
    return redirect(url_for("section_messages", sid=sid))


@app.route("/procedure-inscription")
def procedure():
    filieres, groups = public_catalogue()
    return render_template("procedure.html", cfg=get_settings(), filieres=filieres, groups=groups)


def _pdf_logo(canvas, doc):
    """Dessine un en-tête institutionnel INPP vectoriel, sans dépendance externe."""
    width, height = landscape(A4)
    canvas.saveState()
    blue = colors.HexColor("#2e6da4")
    canvas.setStrokeColor(blue)
    canvas.setFillColor(blue)
    canvas.setLineWidth(1.2)
    canvas.ellipse(17*mm, height-28*mm, 49*mm, height-12*mm, stroke=1, fill=0)
    canvas.setFont("Helvetica-Bold", 13)
    canvas.drawCentredString(33*mm, height-23*mm, "INPP")
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(55*mm, height-17*mm, "INSTITUT NATIONAL DE PRÉPARATION PROFESSIONNELLE")
    canvas.setFont("Helvetica", 8)
    canvas.drawString(55*mm, height-22*mm, "RÉPUBLIQUE DÉMOCRATIQUE DU CONGO")
    canvas.setStrokeColor(colors.HexColor("#b9c9d8"))
    canvas.line(17*mm, height-31*mm, width-17*mm, height-31*mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(colors.HexColor("#666666"))
    canvas.drawRightString(width-17*mm, 8*mm, f"Page {doc.page}")
    canvas.restoreState()


@app.route("/procedure-inscription.pdf")
def procedure_pdf():
    """Génère la fiche PDF directement depuis le catalogue en base."""
    cfg = get_settings()
    _, groups = public_catalogue()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        rightMargin=12*mm, leftMargin=12*mm, topMargin=37*mm, bottomMargin=13*mm,
        title="Fiche de renseignements INPP", author="INPP Académie",
    )
    styles = getSampleStyleSheet()
    cell = ParagraphStyle(
        "FicheCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=7.2, leading=8.5,
    )
    head = ParagraphStyle(
        "FicheHead", parent=cell, fontName="Helvetica-Bold",
        fontSize=7.5, leading=9, alignment=TA_CENTER, textColor=colors.white,
    )
    title = ParagraphStyle(
        "FicheTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=17, leading=20, alignment=TA_CENTER,
        textColor=colors.HexColor("#2e6da4"), spaceAfter=3*mm,
    )
    story = [
        Paragraph("FICHE DE RENSEIGNEMENTS", title),
        Paragraph("Catalogue des filières · métiers · durées · frais matériels et frais généraux",
                  ParagraphStyle("Sub", parent=cell, alignment=TA_CENTER, fontSize=8.5)),
        Spacer(1, 4*mm),
    ]

    def fc(value):
        return f"{float(value):,.0f}".replace(",", " ") + " FC"

    bank = (f"<b>Pour le paiement :</b> {cfg.bank_name or 'Banque à renseigner'}"
            f"<br/>Compte USD : {cfg.bank_account_usd or '—'}"
            f"<br/>Compte FC : {cfg.bank_account_fc or '—'}")
    fees_table = Table([[
        Paragraph(f"<b>1. Inscription :</b> {fc(cfg.inscription_fee)}", cell),
        Paragraph(f"<b>2. Lettre de stage :</b> {fc(cfg.lettre_stage_fee)}", cell),
        Paragraph(f"<b>3. Frais de jury :</b> {fc(cfg.jury_fee)}", cell),
        Paragraph(bank, cell),
    ]], colWidths=[45*mm, 55*mm, 45*mm, 120*mm])
    fees_table.setStyle(TableStyle([
        ("BOX",(0,0),(-1,-1),0.7,colors.HexColor("#8ea8bd")),
        ("INNERGRID",(0,0),(-1,-1),0.35,colors.HexColor("#c7d4df")),
        ("BACKGROUND",(0,0),(-1,-1),colors.HexColor("#f5f8fb")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6), ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),5), ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    story += [
        fees_table, Spacer(1, 3*mm),
        Paragraph(f"<b>Minerval :</b> {fc(cfg.formation_fee)} / mois pour toutes les filières. "
                  "Les frais matériels sont payés une fois pendant la durée de la formation.", cell),
        Spacer(1, 3*mm),
    ]

    data = [[Paragraph("SERVICE", head), Paragraph("FILIÈRE", head),
             Paragraph("MÉTIER", head), Paragraph("DURÉE", head),
             Paragraph("FRAIS MATÉRIELS", head)]]
    spans = []
    body_row = 1
    for group in groups:
        start = body_row
        for f in group["rows"]:
            data.append([
                Paragraph(group["name"].replace("Service ", "", 1), cell) if body_row == start else "",
                Paragraph(str(f["name"] or "—"), cell),
                Paragraph(str(f["metier"] or "—"), cell),
                Paragraph(f"{f['duration_months']} mois", cell),
                Paragraph(f"{float(f['material_fee']):g} USD", cell),
            ])
            body_row += 1
        if body_row - start > 1:
            spans.append((start, body_row - 1))

    table = Table(data, repeatRows=1,
                  colWidths=[40*mm, 70*mm, 88*mm, 30*mm, 35*mm])
    table_style = [
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#2e6da4")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("BOX",(0,0),(-1,-1),0.8,colors.HexColor("#2e6da4")),
        ("INNERGRID",(0,0),(-1,-1),0.35,colors.HexColor("#9fb5c7")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("ALIGN",(3,1),(-1,-1),"CENTER"),
        ("ALIGN",(0,1),(0,-1),"CENTER"),
        ("FONTNAME",(0,1),(0,-1),"Helvetica-Bold"),
        ("LEFTPADDING",(0,0),(-1,-1),4), ("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),3), ("BOTTOMPADDING",(0,0),(-1,-1),3),
    ]
    for start, end in spans:
        table_style.append(("SPAN",(0,start),(0,end)))
    for row in range(1, len(data)):
        if row % 2 == 0:
            table_style.append(("BACKGROUND",(1,row),(-1,row),colors.HexColor("#f7fafc")))
    table.setStyle(TableStyle(table_style))
    story += [
        table, Spacer(1, 3*mm),
        Paragraph("<b>NB :</b> Les frais payés ne sont pas remboursables. "
                  "Les montants affichés correspondent aux valeurs actuellement enregistrées dans le catalogue.", cell),
    ]
    doc.build(story, onFirstPage=_pdf_logo, onLaterPages=_pdf_logo)
    response = Response(buffer.getvalue(), mimetype="application/pdf")
    response.headers["Content-Disposition"] = 'attachment; filename="fiche-renseignements-INPP.pdf"'
    return response


@app.route("/carte/<code>")
def card_verify(code):
    reg = get_db().execute(
        "SELECT r.id FROM registrations r WHERE r.card_code=?", (code,)).fetchone()
    if reg is None:
        abort(404)
    reg = get_reg(reg["id"])
    summary = fees.summarize(reg, get_db().execute(
        "SELECT * FROM payments WHERE registration_id=? AND voided=0", (reg["id"],)).fetchall())
    return render_template("card_verify.html", reg=reg, valid=summary["en_ordre"])


@app.route("/secretariat")
@secretary_required
def sec_dashboard():
    conn = get_db()
    rows = registry_rows()
    count = {k: 0 for k in fees.STATUS}
    for x in rows:
        count[x["s"]["status"]] += 1
    collected = conn.execute(
        "SELECT kind, currency, SUM(amount) AS total FROM payments WHERE voided=0 GROUP BY kind, currency "
        "ORDER BY kind").fetchall()
    letters = [x for x in rows if x["r"]["letter_status"] == "pending"]
    latest = list(reversed(rows))[:8]
    return render_template("secretariat/dashboard.html", total=len(rows), count=count, collected=collected,
                           letters=letters, latest=latest, cards=sum(1 for x in rows if x["r"]["card_code"]),
                           jury_ok=sum(1 for x in rows if x["s"]["jury_ok"]))


def filtered_registry():
    groupe = request.args.get("groupe", "all")
    filiere = request.args.get("filiere", type=int)
    statut = request.args.get("statut", "")
    q = request.args.get("q", "").strip()
    where, params = [], []
    if groupe == "direct":
        where.append("r.trainee_type='non_recommande'")
    elif groupe == "autres":
        where.append("r.trainee_type!='non_recommande'")
    if filiere:
        where.append("r.filiere_id=?")
        params.append(filiere)
    if q:
        where.append("(r.full_name LIKE ? OR r.card_code LIKE ? OR r.institution LIKE ?)")
        params += [f"%{q}%"] * 3
    rows = registry_rows(("WHERE " + " AND ".join(where)) if where else "", params)
    if statut in fees.STATUS:
        rows = [x for x in rows if x["s"]["status"] == statut]
    return rows, {"groupe": groupe, "filiere": filiere, "statut": statut, "q": q}


@app.route("/secretariat/registre")
@secretary_required
def sec_registry():
    rows, flt = filtered_registry()
    filieres = get_db().execute("SELECT id, name FROM filieres ORDER BY name").fetchall()
    return render_template("secretariat/registry.html", rows=rows, flt=flt, filieres=filieres)


@app.route("/secretariat/registre.csv")
@secretary_required
def sec_registry_csv():
    rows, _ = filtered_registry()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["N°", "Noms & Post-noms", "Sexe", "Filière", "Montant inscription (Fc)", "Type de stagiaire",
                "Institution", "Frais matériel ($)", "Frais de formation (Fc)", "Mois de formation payés",
                "Frais de jury (Fc)", "Autorisé au jury", "Situation", "N° carte"])
    for x in rows:
        r, k = x["r"], x["s"]["kinds"]
        w.writerow([r["id"], r["full_name"], r["sex"], r["filiere"],
                    f"{k['inscription']['paid']:.0f}" if k["inscription"]["applicable"] else "dispensé",
                    fees.TYPES[r["trainee_type"]][1], r["institution"],
                    f"{k['materiel']['paid']:g}" if k["materiel"]["applicable"] else "dispensé",
                    f"{k['formation']['paid']:.0f}" if k["formation"]["applicable"] else "dispensé",
                    len(k["formation"]["months"]) if k["formation"]["applicable"] else "",
                    f"{k['jury']['paid']:.0f}" if k["jury"]["applicable"] else "dispensé",
                    "Oui" if x["s"]["jury_ok"] else "Non", fees.STATUS[x["s"]["status"]][0],
                    r["card_code"] or ""])
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=registre_stagiaires.csv"})


@app.route("/secretariat/nouveau", methods=["GET", "POST"])
@secretary_required
def sec_new():
    conn = get_db()
    filieres = conn.execute("SELECT * FROM filieres WHERE active=1 ORDER BY name").fetchall()
    cfg = get_settings()
    if request.method == "POST":
        f = request.form
        name = re.sub(r"\s+", " ", f.get("full_name", "")).strip()
        sex = f.get("sex", "")
        ttype = f.get("trainee_type", "")
        filiere = conn.execute("SELECT * FROM filieres WHERE id=? AND active=1",
                               (f.get("filiere_id", type=int),)).fetchone()
        institution, letter = f.get("institution", "").strip(), f.get("letter_ref", "").strip()
        error = None
        if len(name) < 3:
            error = "Indiquez les noms et post-noms du stagiaire."
        elif sex not in ("M", "F"):
            error = "Indiquez le sexe."
        elif filiere is None:
            error = "Choisissez une filière."
        elif ttype not in fees.TYPES:
            error = "Choisissez le type de stagiaire."
        elif fees.is_recommended(ttype) and (not institution or not letter):
            error = "Un stagiaire recommandé doit avoir une institution d'origine et une lettre de recommandation."
        elif conn.execute("SELECT 1 FROM registrations WHERE lower(full_name)=lower(?) AND filiere_id=?",
                          (name, filiere["id"] if filiere else 0)).fetchone() and not f.get("force"):
            error = ("Un stagiaire portant ce nom est déjà inscrit dans cette filière. "
                     "S'il s'agit d'un homonyme, cochez la case de confirmation.")
            flash(error, "warn")
            return render_template("secretariat/new.html", filieres=filieres, cfg=cfg, form=f, dup=True)
        if error:
            flash(error, "bad")
            return render_template("secretariat/new.html", filieres=filieres, cfg=cfg, form=f, dup=False)
        snap = fees.fee_snapshot(ttype, cfg, filiere)
        recommended = fees.is_recommended(ttype)
        rid = conn.execute(
            "INSERT INTO registrations (full_name, sex, phone, filiere_id, trainee_type, institution, letter_ref, "
            "letter_status, fee_inscription, fee_material, fee_formation, fee_jury, registered_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, sex, f.get("phone", "").strip(), filiere["id"], ttype, institution if recommended else "",
             letter if recommended else "", "pending" if recommended else "none", snap["fee_inscription"],
             snap["fee_material"], snap["fee_formation"], snap["fee_jury"], g.user["id"])).lastrowid
        refresh_card(rid)
        conn.commit()
        if recommended:
            flash("Stagiaire enregistré. Sa lettre de recommandation doit être approuvée par la hiérarchie "
                  "avant qu'il soit inséré dans le registre des apprenants en ordre.", "ok")
        else:
            flash("Stagiaire enregistré. Remettez-lui le numéro de compte de la banque pour payer l'inscription, "
                  "puis enregistrez sa preuve de paiement.", "ok")
        return redirect(url_for("sec_detail", rid=rid))
    return render_template("secretariat/new.html", filieres=filieres, cfg=cfg, form={}, dup=False)


@app.route("/secretariat/<int:rid>")
@secretary_required
def sec_detail(rid):
    reg = get_reg(rid)
    pays = reg_payments(rid)
    summary = fees.summarize(reg, pays)
    default_months = fees.next_periods(reg, pays, 1)[0] if summary["kinds"]["formation"]["applicable"] else None
    return render_template("secretariat/detail.html", reg=reg, pays=pays, s=summary, cfg=get_settings(),
                           next_month=default_months)


@app.route("/secretariat/<int:rid>/paiement", methods=["POST"])
@secretary_required
def sec_payment(rid):
    reg = get_reg(rid)
    conn = get_db()
    pays = reg_payments(rid)
    summary = fees.summarize(reg, pays)
    kind = request.form.get("kind", "")
    ref = request.form.get("bank_ref", "").strip()
    paid_at = request.form.get("paid_at", "").strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", paid_at):
        paid_at = time.strftime("%Y-%m-%d")
    back = redirect(url_for("sec_detail", rid=rid))
    if kind not in fees.KINDS or not summary["kinds"][kind]["applicable"]:
        flash("Ce type de frais n'est pas dû par ce stagiaire.", "bad")
        return back
    if fees.is_recommended(reg["trainee_type"]) and reg["letter_status"] != "approved":
        flash("La lettre de recommandation doit d'abord être approuvée par la hiérarchie.", "bad")
        return back
    if len(ref) < 3:
        flash("Indiquez la référence de la preuve de paiement (bordereau de la banque).", "bad")
        return back
    currency = fees.KINDS[kind][1]
    if kind == "formation":
        months = request.form.get("months", type=int) or 0
        if not 1 <= months <= 12:
            flash("Indiquez un nombre de mois entre 1 et 12.", "bad")
            return back
        for period in fees.next_periods(reg, pays, months):
            conn.execute("INSERT INTO payments (registration_id, kind, amount, currency, period, bank_ref, paid_at, "
                         "recorded_by) VALUES (?,?,?,?,?,?,?,?)",
                         (rid, kind, reg["fee_formation"], currency, period, ref, paid_at, g.user["id"]))
        flash(f"{months} mois de formation enregistré(s).", "ok")
    else:
        amount = parse_number(request.form.get("amount", ""))
        balance = summary["kinds"][kind]["balance"]
        if amount is None or amount <= 0:
            flash("Indiquez un montant valide.", "bad")
            return back
        if amount > balance + 0.004:
            flash(f"Le montant dépasse le solde à payer ({fees.format_money(balance, currency)}).", "bad")
            return back
        conn.execute("INSERT INTO payments (registration_id, kind, amount, currency, bank_ref, paid_at, recorded_by) "
                     "VALUES (?,?,?,?,?,?,?)", (rid, kind, amount, currency, ref, paid_at, g.user["id"]))
        flash("Paiement enregistré.", "ok")
    if refresh_card(rid):
        flash("Le stagiaire est en ordre : sa carte de stagiaire est disponible.", "ok")
    conn.commit()
    return back


@app.route("/secretariat/paiements/<int:pid>/annuler", methods=["POST"])
@secretary_required
def sec_payment_void(pid):
    p = get_db().execute("SELECT * FROM payments WHERE id=?", (pid,)).fetchone()
    if p is None:
        abort(404)
    get_db().execute("UPDATE payments SET voided=1, voided_by=?, voided_at=datetime('now') WHERE id=? AND voided=0",
                     (g.user["id"], pid))
    get_db().commit()
    flash("Paiement annulé (il reste visible dans l'historique).", "ok")
    return redirect(url_for("sec_detail", rid=p["registration_id"]))


@app.route("/secretariat/<int:rid>/lettre/<action>", methods=["POST"])
@secretary_required
def sec_letter(rid, action):
    reg = get_reg(rid)
    if not fees.is_recommended(reg["trainee_type"]):
        abort(404)
    by = request.form.get("decided_by", "").strip()
    note = request.form.get("note", "").strip()
    if action in ("approve", "reject"):
        if len(by) < 3:
            flash("Indiquez le nom et la fonction de la personne de la hiérarchie qui a décidé.", "bad")
            return redirect(url_for("sec_detail", rid=rid))
        get_db().execute("UPDATE registrations SET letter_status=?, letter_decided_by=?, "
                         "letter_decided_at=datetime('now'), letter_note=? WHERE id=?",
                         ("approved" if action == "approve" else "rejected", by, note, rid))
        flash("Lettre approuvée : le stagiaire est inséré dans le registre des apprenants d'autres institutions."
              if action == "approve" else "Lettre refusée.", "ok" if action == "approve" else "info")
    elif action == "reopen":
        get_db().execute("UPDATE registrations SET letter_status='pending', letter_decided_by='', "
                         "letter_decided_at=NULL, letter_note='' WHERE id=?", (rid,))
        flash("Lettre remise en attente d'approbation.", "info")
    else:
        abort(404)
    if action == "approve" and refresh_card(rid):
        flash("Le stagiaire est en ordre : sa carte de stagiaire est disponible.", "ok")
    get_db().commit()
    return redirect(url_for("sec_detail", rid=rid))


@app.route("/secretariat/<int:rid>/carte")
@secretary_required
def sec_card(rid):
    reg = get_reg(rid)
    if not reg["card_code"]:
        flash("La carte n'est délivrée qu'aux stagiaires en ordre avec les frais.", "warn")
        return redirect(url_for("sec_detail", rid=rid))
    return render_template("secretariat/card.html", reg=reg)


@app.route("/secretariat/jury")
@secretary_required
def sec_jury():
    filiere = request.args.get("filiere", type=int)
    rows = registry_rows("WHERE r.filiere_id=?" if filiere else "", (filiere,) if filiere else ())
    filieres = get_db().execute("SELECT id, name FROM filieres ORDER BY name").fetchall()
    return render_template("secretariat/jury.html", ok=[x for x in rows if x["s"]["jury_ok"]],
                           blocked=[x for x in rows if not x["s"]["jury_ok"]], filieres=filieres, filiere=filiere)


@app.route("/secretariat/tarifs", methods=["GET", "POST"])
@secretary_required
def sec_tariffs():
    conn = get_db()
    if request.method == "POST":
        f = request.form
        action = f.get("action")
        if action == "settings":
            vals = {k: parse_number(f.get(k, "")) for k in ("inscription_fee", "formation_fee", "jury_fee")}
            lettre = parse_number(f.get("lettre_stage_fee", "")) or 0
            if any(v is None or v < 0 for v in vals.values()) or lettre < 0:
                flash("Les frais doivent être des nombres positifs.", "bad")
            else:
                for k, v in vals.items():
                    conn.execute("UPDATE settings SET value=? WHERE key=?", (str(v), k))
                conn.execute("UPDATE settings SET value=? WHERE key=?", (str(lettre), "lettre_stage_fee"))
                for k in ("bank_name", "bank_account_usd", "bank_account_fc"):
                    conn.execute("UPDATE settings SET value=? WHERE key=?", (f.get(k, "").strip(), k))
                flash("Tarifs enregistrés. Ils s'appliquent aux prochaines inscriptions.", "ok")
        elif action in ("filiere_add", "filiere_update"):
            name, fee = f.get("name", "").strip(), parse_number(f.get("material_fee", ""))
            metier = f.get("metier", "").strip()
            duration_months = f.get("duration_months", type=int) or 0
            service_id = f.get("service_id", type=int)
            if len(name) < 2 or fee is None or fee < 0:
                flash("Indiquez le nom de la filière et un frais matériel valide (en $).", "bad")
            else:
                try:
                    if action == "filiere_add":
                        conn.execute(
                            "INSERT INTO filieres (name, metier, duration_months, material_fee, service_id) "
                            "VALUES (?,?,?,?,?)", (name, metier, duration_months, fee, service_id))
                        flash("Filière ajoutée.", "ok")
                    else:
                        conn.execute(
                            "UPDATE filieres SET name=?, metier=?, duration_months=?, material_fee=?, "
                            "active=?, service_id=? WHERE id=?",
                            (name, metier, duration_months, fee, 1 if f.get("active") else 0, service_id,
                             f.get("id", type=int)))
                        flash("Filière mise à jour (les stagiaires déjà inscrits gardent leur tarif).", "ok")
                except Exception:
                    flash("Une filière porte déjà ce nom.", "bad")
        elif action in ("service_add", "service_update"):
            name = f.get("name", "").strip()
            chef_id = f.get("chef_id", type=int)
            chef = conn.execute("SELECT id FROM users WHERE id=? AND role='formateur'", (chef_id,)).fetchone()                 if chef_id else None
            if len(name) < 2:
                flash("Indiquez le nom du service (ex. Service Informatique).", "bad")
            else:
                try:
                    if action == "service_add":
                        cur = conn.execute("INSERT INTO services (name, chef_id) VALUES (?,?)",
                                           (name, chef["id"] if chef else None))
                        service_id = cur.lastrowid
                    else:
                        service_id = f.get("id", type=int)
                        conn.execute("UPDATE services SET name=?, chef_id=?, active=? WHERE id=?",
                                     (name, chef["id"] if chef else None, 1 if f.get("active") else 0, service_id))
                    selected = {int(x) for x in f.getlist("formateur_ids") if x.isdigit()}
                    if chef:
                        selected.add(chef["id"])
                    conn.execute("DELETE FROM service_formateurs WHERE service_id=?", (service_id,))
                    for trainer_id in selected:
                        ok = conn.execute("SELECT 1 FROM users WHERE id=? AND role='formateur'",
                                          (trainer_id,)).fetchone()
                        if ok:
                            conn.execute("INSERT INTO service_formateurs (service_id,user_id) VALUES (?,?)",
                                         (service_id, trainer_id))
                    flash("Service et équipe de formateurs mis à jour.", "ok")
                except Exception:
                    flash("Un service porte déjà ce nom.", "bad")
        conn.commit()
        return redirect(url_for("sec_tariffs"))
    filieres = conn.execute(
        "SELECT f.*, s.name AS service_name, (SELECT COUNT(*) FROM registrations r WHERE r.filiere_id=f.id) AS nb "
        "FROM filieres f LEFT JOIN services s ON s.id=f.service_id ORDER BY f.name").fetchall()
    services = conn.execute(
        "SELECT sv.*, u.full_name AS chef_name, "
        "(SELECT COUNT(*) FROM filieres f WHERE f.service_id=sv.id) AS nb_filieres FROM services sv "
        "LEFT JOIN users u ON u.id=sv.chef_id ORDER BY sv.name").fetchall()
    formateurs = conn.execute("SELECT id, full_name FROM users WHERE role='formateur' ORDER BY full_name").fetchall()
    service_formateurs = {}
    for sv in services:
        service_formateurs[sv["id"]] = {
            r["user_id"] for r in conn.execute(
                "SELECT user_id FROM service_formateurs WHERE service_id=?", (sv["id"],)
            ).fetchall()
        }
    return render_template("secretariat/tariffs.html", cfg=get_settings(), filieres=filieres, services=services,
                           formateurs=formateurs, service_formateurs=service_formateurs)


# ------------------------------------------------------------------ erreurs
@app.errorhandler(403)
def forbidden(_e):
    return render_template("error.html", code=403, message="Vous n'avez pas accès à cette page."), 403


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, message="Cette page n'existe pas."), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, message=getattr(e, "description", "Requête invalide.")), 400


@app.errorhandler(413)
def too_large(_e):
    return render_template("error.html", code=413, message="Fichier trop volumineux (8 Mo maximum)."), 413


ensure_ready()

if __name__ == "__main__":
    host = os.environ.get("INPP_HOST", "127.0.0.1")
    app.run(host=host, port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("INPP_DEBUG") == "1")
