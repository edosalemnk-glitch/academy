"""Test de bout en bout : python tests/smoke_test.py (utilise une base temporaire)."""
import os, re, sys, tempfile

os.environ["INPP_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as appmod  # noqa: E402

app = appmod.app
db = appmod.database


def client():
    return app.test_client()


def token(c, url="/connexion"):
    html = c.get(url).get_data(as_text=True)
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    return m.group(1)


def post(c, url, data=None, page="/connexion", follow=True):
    data = dict(data or {})
    data["_csrf"] = token(c, page)
    return c.post(url, data=data, follow_redirects=follow)


def login(c, email, pwd):
    return post(c, "/connexion", {"email": email, "password": pwd})


def check(label, cond):
    print(("OK   " if cond else "FAIL ") + label)
    if not cond:
        check.failed = True


check.failed = False
conn = db.connect()

# 1. CSRF : un POST sans jeton est refusé
c = client()
check("POST sans jeton CSRF refusé", c.post("/connexion", data={"email": "x", "password": "y"}).status_code == 400)

# 2. Connexion stagiaire, accès verrouillé sans validation
s = client()
r = login(s, "stagiaire07@inpp.cd", "Stagiaire2026!")
check("connexion stagiaire", "Mes formations" in r.get_data(as_text=True))
sql1 = conn.execute("SELECT id FROM courses WHERE title LIKE 'SQL – Niveau 1%'").fetchone()[0]
r = s.get(f"/apprendre/{sql1}", follow_redirects=True)
check("stagiaire en attente : accès refusé", "validé par le formateur" in r.get_data(as_text=True))
lessons = [r[0] for r in conn.execute("SELECT id FROM lessons WHERE course_id=? ORDER BY position", (sql1,))]
check("leçon directe refusée sans validation", "validé par le formateur" in s.get(f"/lecon/{lessons[0]}", follow_redirects=True).get_data(as_text=True))

# 3. Le formateur valide
f = client()
login(f, "formateur@inpp.cd", "Formateur2026!")
check("dashboard formateur", "Stagiaires en difficulté" in f.get("/formateur").get_data(as_text=True))
eid = conn.execute("SELECT e.id FROM enrollments e JOIN users u ON u.id=e.user_id WHERE u.email='stagiaire07@inpp.cd' AND e.course_id=?", (sql1,)).fetchone()[0]
post(f, f"/formateur/inscriptions/{eid}/approve", page="/formateur")
check("validation par le formateur", conn.execute("SELECT status FROM enrollments WHERE id=?", (eid,)).fetchone()[0] == "approved")

# 4. Parcours séquentiel + quiz
r = s.get(f"/lecon/{lessons[1]}", follow_redirects=True)
check("leçon 2 verrouillée avant leçon 1", "débloquer celle-ci" in r.get_data(as_text=True))
check("leçon 1 accessible", s.get(f"/lecon/{lessons[0]}").status_code == 200)

def answers(lesson_id, wrong=False):
    d = {}
    for q in conn.execute("SELECT id, correct FROM questions WHERE lesson_id=?", (lesson_id,)):
        d[f"q_{q['id']}"] = ("A" if q["correct"] != "A" else "B") if wrong else q["correct"]
    return d

r = post(s, f"/lecon/{lessons[0]}/quiz", answers(lessons[0], wrong=True), page=f"/lecon/{lessons[0]}/quiz")
html = r.get_data(as_text=True)
check("quiz raté : pas de correction affichée", "Bonne réponse :" not in html and "Réessayer" in html)
check("leçon 2 toujours verrouillée après échec", "débloquer celle-ci" in s.get(f"/lecon/{lessons[1]}", follow_redirects=True).get_data(as_text=True))
r = post(s, f"/lecon/{lessons[0]}/quiz", answers(lessons[0]), page=f"/lecon/{lessons[0]}/quiz")
check("quiz réussi : correction affichée", "Bonne réponse :" in r.get_data(as_text=True))
check("leçon 2 débloquée", s.get(f"/lecon/{lessons[1]}").status_code == 200)

# 5. Certificat quand tout est terminé
for lid in lessons[1:]:
    post(s, f"/lecon/{lid}/quiz", answers(lid), page=f"/lecon/{lid}/quiz")
cert = conn.execute("SELECT code FROM certificates c JOIN users u ON u.id=c.user_id WHERE u.email='stagiaire07@inpp.cd'").fetchone()
check("certificat émis", cert is not None)
check("certificat public vérifiable", "Héritier Banza" in client().get(f"/certificat/{cert[0]}").get_data(as_text=True))

# 6. Cloisonnement des rôles
check("stagiaire interdit sur /formateur", s.get("/formateur").status_code == 403)
check("catalogue public", "Catalogue" in client().get("/catalogue").get_data(as_text=True))

# 7. Inscription libre + abonnement
n = client()
post(n, "/inscription", {"full_name": "Nouveau Visiteur", "email": "nv@exemple.cd", "password": "motdepasse1", "confirm": "motdepasse1"}, page="/inscription")
sql2 = conn.execute("SELECT id FROM courses WHERE title LIKE 'SQL – Niveau 2%'").fetchone()[0]
post(n, f"/cours/{sql2}/abonner", page=f"/cours/{sql2}")
check("abonnement en attente", conn.execute("SELECT status FROM enrollments e JOIN users u ON u.id=e.user_id WHERE u.email='nv@exemple.cd'").fetchone()[0] == "pending")

# 8. Formateur : création de comptes, suivi, export, ajout de leçon/question
r = post(f, "/formateur/stagiaires", {"bulk": "Marie Kabeya ; marie.kabeya@exemple.cd\nligne invalide", "course_id": str(sql1)}, page="/formateur/stagiaires")
check("création de compte en lot", "Mot de passe temporaire" in r.get_data(as_text=True) and "Marie Kabeya" in r.get_data(as_text=True))
check("suivi affiché", "Bloqué" in f.get(f"/formateur/cours/{sql1}/suivi").get_data(as_text=True))
csv_r = f.get(f"/formateur/cours/{sql1}/suivi.csv")
check("export CSV", csv_r.status_code == 200 and b"Stagiaire;" in csv_r.data)
post(f, f"/formateur/cours/{sql1}/lecons/nouvelle", {"title": "Leçon test", "content": "## Test\n- a\n- b"}, page=f"/formateur/cours/{sql1}/lecons/nouvelle")
new_l = conn.execute("SELECT id FROM lessons WHERE title='Leçon test'").fetchone()[0]
post(f, f"/formateur/lecons/{new_l}/questions", {"text": "Q ?", "option_a": "1", "option_b": "2", "option_c": "3", "option_d": "4", "correct": "C"}, page=f"/formateur/lecons/{new_l}/questions")
check("question ajoutée", conn.execute("SELECT COUNT(*) FROM questions WHERE lesson_id=?", (new_l,)).fetchone()[0] == 1)

# 9. Un formateur ne peut pas modifier le cours d'un autre
conn.execute("INSERT INTO users (full_name,email,password_hash,role) VALUES ('Autre','autre@inpp.cd',?, 'formateur')", (appmod.generate_password_hash("Autreform123"),))
conn.commit()
o = client(); login(o, "autre@inpp.cd", "Autreform123")
check("autre formateur : 403 sur mon cours", o.get(f"/formateur/cours/{sql1}").status_code == 403)

# 10. Terrain SQL
r = post(s, "/terrain-sql", {"sql": "SELECT nom FROM employes LIMIT 3"}, page="/terrain-sql")
check("terrain SQL SELECT", "Mukendi" in r.get_data(as_text=True))
r = post(s, "/terrain-sql", {"sql": "DELETE FROM employes"}, page="/terrain-sql")
check("terrain SQL refuse DELETE", "lecture seule" in r.get_data(as_text=True))
r = post(s, "/terrain-sql", {"sql": "SELECT nom, prenom FROM employes", "challenge": "1"}, page="/terrain-sql")
check("défi SQL validé", "Bravo" in r.get_data(as_text=True))

# 11. Mot de passe temporaire : changement forcé
m = client(); rr = login(m, "marie.kabeya@exemple.cd", "x")
check("mauvais mot de passe refusé", "incorrect" in rr.get_data(as_text=True))

# 12. Pages GET sans erreur 500
for url in ["/catalogue", f"/cours/{sql1}", "/mes-cours", f"/apprendre/{sql1}", f"/lecon/{lessons[0]}", f"/lecon/{lessons[0]}/quiz", "/terrain-sql?defi=3"]:
    check(f"GET {url} (stagiaire)", s.get(url).status_code == 200)
for url in ["/formateur", "/formateur/stagiaires", f"/formateur/cours/{sql1}", f"/formateur/cours/{sql1}/inscriptions", f"/formateur/cours/{sql1}/modifier", "/formateur/cours/nouveau", f"/formateur/lecons/{lessons[0]}/modifier", f"/formateur/lecons/{lessons[0]}/questions", f"/formateur/lecons/{lessons[0]}/questions?edit=1", f"/apprendre/{sql1}", f"/lecon/{lessons[3]}/quiz"]:
    check(f"GET {url} (formateur)", f.get(url).status_code == 200)

# 13. Secrétariat / réception (inscription au centre, frais, lettre, carte)
sec = client()
login(sec, "secretariat@inpp.cd", "Secretariat2026!")
check("cloisonnement : stagiaire interdit sur /secretariat", s.get("/secretariat").status_code == 403)
check("cloisonnement : formateur interdit sur /secretariat", f.get("/secretariat").status_code == 403)
check("cloisonnement : secrétaire interdit sur /formateur", sec.get("/formateur").status_code == 403)
check("tableau de bord secrétariat", sec.get("/secretariat").status_code == 200)

fid = conn.execute("SELECT id FROM filieres LIMIT 1").fetchone()[0]
r = post(sec, "/secretariat/nouveau",
        {"full_name": "Smoke Test Stagiaire", "sex": "M", "filiere_id": str(fid), "trainee_type": "non_recommande"},
        page="/secretariat/nouveau")
rid = conn.execute("SELECT id FROM registrations WHERE full_name='Smoke Test Stagiaire'").fetchone()[0]
check("inscription au centre enregistrée", rid is not None)
check("pas de carte avant paiement", conn.execute("SELECT card_code FROM registrations WHERE id=?", (rid,)).fetchone()[0] is None)

post(sec, f"/secretariat/{rid}/paiement", {"kind": "inscription", "amount": "40000", "bank_ref": "SMOKE-1"}, page=f"/secretariat/{rid}")
r = post(sec, f"/secretariat/{rid}/paiement", {"kind": "materiel", "amount": "9999", "bank_ref": "SMOKE-2"}, page=f"/secretariat/{rid}")
check("paiement au-delà du solde refusé", "dépasse le solde" in r.get_data(as_text=True))
reg = conn.execute("SELECT fee_material FROM registrations WHERE id=?", (rid,)).fetchone()
post(sec, f"/secretariat/{rid}/paiement", {"kind": "materiel", "amount": str(reg["fee_material"]), "bank_ref": "SMOKE-3"}, page=f"/secretariat/{rid}")
check("carte délivrée une fois en ordre", conn.execute("SELECT card_code FROM registrations WHERE id=?", (rid,)).fetchone()[0] is not None)
code = conn.execute("SELECT card_code FROM registrations WHERE id=?", (rid,)).fetchone()[0]
check("carte vérifiable publiquement", "valide" in client().get(f"/carte/{code}").get_data(as_text=True).lower())

# Stagiaire recommandé partiel : bloqué tant que la lettre n'est pas approuvée
r = post(sec, "/secretariat/nouveau",
        {"full_name": "Smoke Recommande", "sex": "F", "filiere_id": str(fid), "trainee_type": "recommande_partiel",
         "institution": "Ministère Test", "letter_ref": "REF-1"}, page="/secretariat/nouveau")
rid2 = conn.execute("SELECT id FROM registrations WHERE full_name='Smoke Recommande'").fetchone()[0]
r = post(sec, f"/secretariat/{rid2}/paiement", {"kind": "materiel", "amount": "40", "bank_ref": "SMOKE-4"}, page=f"/secretariat/{rid2}")
check("paiement refusé avant approbation de la lettre", "abord" in r.get_data(as_text=True) and "approuvée" in r.get_data(as_text=True))
post(sec, f"/secretariat/{rid2}/lettre/approve", {"decided_by": "Directeur Général"}, page=f"/secretariat/{rid2}")
check("lettre approuvée", conn.execute("SELECT letter_status FROM registrations WHERE id=?", (rid2,)).fetchone()[0] == "approved")
post(sec, f"/secretariat/{rid2}/paiement", {"kind": "materiel", "amount": "40", "bank_ref": "SMOKE-5"}, page=f"/secretariat/{rid2}")
post(sec, f"/secretariat/{rid2}/paiement", {"kind": "jury", "amount": "25000", "bank_ref": "SMOKE-6"}, page=f"/secretariat/{rid2}")
check("recommandé partiel en ordre après matériel+jury", conn.execute("SELECT card_code FROM registrations WHERE id=?", (rid2,)).fetchone()[0] is not None)

for url in ["/secretariat", "/secretariat/registre", "/secretariat/registre.csv", "/secretariat/nouveau",
            "/secretariat/tarifs", "/secretariat/jury", "/procedure-inscription", f"/secretariat/{rid}"]:
    check(f"GET {url} (secrétariat)", sec.get(url).status_code == 200)

print("\nÉCHEC" if check.failed else "\nTous les tests passent.")
sys.exit(1 if check.failed else 0)
