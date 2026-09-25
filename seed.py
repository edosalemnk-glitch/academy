"""Données de démonstration : 1 formateur, 10 stagiaires, 3 cours complets avec quiz."""
from werkzeug.security import generate_password_hash

import fees

FORMATEUR = ("Prof. Daniel Mbayo", "formateur@inpp.cd", "Formateur2026!")
SECRETAIRE = ("Bibiche Kanyinda", "secretariat@inpp.cd", "Secretariat2026!")
PWD_STAGIAIRE = "Stagiaire2026!"

# Filières du centre : nom -> frais matériel en $ (40, 50 ou 80 selon projet.md)
FILIERES = [("Informatique de gestion", 50), ("Électricité du bâtiment", 80), ("Coupe et couture", 40)]
STAGIAIRES = [
    "Aline Mbuyi", "Christian Tshibanda", "Divine Mukendi", "Emmanuel Ilunga", "Fabrice Kasongo",
    "Grâce Lukusa", "Héritier Banza", "Isaac Ngoy", "Jocelyne Mutombo", "Kevin Kanku",
]

# (question, [option_a, option_b, option_c, option_d], lettre_correcte, explication)
SQL1 = {
    "title": "SQL – Niveau 1 : Fondamentaux",
    "category": "Bases de données", "level": "Débutant", "fee": 0,
    "description": ("Apprenez à interroger une base de données de zéro : SELECT, WHERE, tri, regroupements "
                    "et modification des données. Chaque leçon se termine par un quiz, et un terrain SQL "
                    "vous permet de vous entraîner sur une vraie base d'exemple."),
    "lessons": [
        ("Comprendre une base de données", """Une **base de données** stocke des informations de façon organisée. Elle est composée de **tables**.

Une table ressemble à un tableau Excel :
- chaque **colonne** décrit une information (nom, salaire...) ;
- chaque **ligne** (ou enregistrement) représente un élément, par exemple un employé ;
- la **clé primaire** est la colonne qui identifie chaque ligne de façon unique (souvent `id`).

Le logiciel qui gère la base s'appelle un **SGBD** (SQLite, MySQL, PostgreSQL, SQL Server...). **SQL** est le langage commun pour lui parler.

## Notre base d'exemple
Dans le Terrain SQL, vous trouverez trois tables : `departements`, `employes` et `projets`. Ouvrez-le et regardez leurs colonnes avant de continuer.

> Retenez : une table = un sujet (les employés), une ligne = un élément, une colonne = une information.""",
         [("Que représente une ligne d'une table ?", ["Un enregistrement (un élément, par exemple un employé)", "Une information commune à tous les éléments", "Le nom de la base de données", "Un logiciel de gestion"], "A", "Une ligne est un enregistrement ; une colonne est une information."),
          ("À quoi sert la clé primaire ?", ["À chiffrer les données", "À identifier chaque ligne de façon unique", "À trier la table", "À supprimer les doublons du nom"], "B", "La clé primaire (souvent `id`) est unique pour chaque ligne."),
          ("Que signifie SGBD ?", ["Système de Gestion de Bases de Données", "Suite Générale de Bureautique Digitale", "Serveur Global de Bases Distantes", "Service de Gestion des Bases Dynamiques"], "A", "Le SGBD est le logiciel qui gère les bases (SQLite, MySQL, PostgreSQL...).")]),
        ("Lire des données avec SELECT", """La commande **SELECT** sert à lire des données. Sa forme de base :

```
SELECT colonnes FROM table;
```

Exemples :
```
SELECT nom, prenom FROM employes;
SELECT * FROM departements;
SELECT DISTINCT poste FROM employes;
```

- `*` signifie « toutes les colonnes » ;
- `DISTINCT` supprime les doublons dans le résultat ;
- on peut renommer une colonne avec `AS` : `SELECT salaire AS paie FROM employes;`

> À vous : ouvrez le Terrain SQL et affichez le poste de tous les employés, sans doublon.""",
         [("Quelle requête affiche le nom et le prénom de tous les employés ?", ["GET nom, prenom FROM employes", "SELECT nom, prenom FROM employes", "SELECT employes FROM nom, prenom", "SHOW nom, prenom IN employes"], "B", "La forme est SELECT colonnes FROM table."),
          ("Que fait SELECT * FROM projets ?", ["Supprime tous les projets", "Compte les projets", "Affiche toutes les colonnes de tous les projets", "Affiche seulement la première colonne"], "C", "L'étoile * désigne toutes les colonnes."),
          ("À quoi sert DISTINCT ?", ["À trier les résultats", "À supprimer les doublons du résultat", "À limiter le nombre de lignes", "À renommer une colonne"], "B", "SELECT DISTINCT poste donne la liste des postes sans répétition.")]),
        ("Filtrer avec WHERE", """La clause **WHERE** garde seulement les lignes qui respectent une condition.

```
SELECT * FROM employes WHERE salaire > 1500;
SELECT * FROM employes WHERE departement_id = 1 AND salaire >= 1600;
SELECT * FROM employes WHERE poste = 'Comptable' OR poste = 'Secrétaire';
```

Opérateurs utiles :
- comparaisons : `=`, `<>` (différent), `<`, `>`, `<=`, `>=` ;
- `AND`, `OR`, `NOT` pour combiner les conditions ;
- `BETWEEN 1000 AND 1500`, `IN (1, 3)` ;
- `LIKE 'M%'` : commence par M (`%` remplace n'importe quels caractères) ;
- `IS NULL` / `IS NOT NULL` pour les valeurs absentes.

> Attention : on écrit `IS NULL`, jamais `= NULL`. Le texte se met entre apostrophes.""",
         [("Quelle condition sélectionne les salaires supérieurs à 1500 ?", ["WHERE salaire > 1500", "WHERE salaire => 1500", "IF salaire > 1500", "FILTER salaire > 1500"], "A", "La clause s'écrit WHERE suivie de la condition."),
          ("Que fait WHERE nom LIKE 'M%' ?", ["Cherche les noms qui finissent par M", "Cherche les noms qui commencent par M", "Cherche les noms égaux à M%", "Cherche les noms qui contiennent 5 lettres"], "B", "Le % remplace n'importe quelle suite de caractères : 'M%' = commence par M."),
          ("Comment trouver les employés sans département ?", ["WHERE departement_id = NULL", "WHERE departement_id = 0", "WHERE departement_id IS NULL", "WHERE departement_id EMPTY"], "C", "NULL se teste avec IS NULL, jamais avec =.")]),
        ("Trier et limiter les résultats", """**ORDER BY** trie le résultat, **LIMIT** en garde seulement un certain nombre.

```
SELECT nom, salaire FROM employes ORDER BY salaire DESC;
SELECT nom, salaire FROM employes ORDER BY salaire DESC LIMIT 3;
SELECT nom FROM employes ORDER BY nom ASC;
```

- `ASC` = croissant (par défaut), `DESC` = décroissant ;
- on peut trier sur plusieurs colonnes : `ORDER BY departement_id, salaire DESC` ;
- `LIMIT` se place toujours en dernier.

Ordre d'écriture d'une requête : `SELECT ... FROM ... WHERE ... ORDER BY ... LIMIT ...`

> Exercice : quels sont les 3 employés les mieux payés ?""",
         [("Comment trier les employés du salaire le plus haut au plus bas ?", ["ORDER BY salaire ASC", "ORDER BY salaire DESC", "SORT salaire DOWN", "GROUP BY salaire"], "B", "DESC trie en ordre décroissant."),
          ("Quelle requête donne les 5 premiers employés ?", ["SELECT * FROM employes TOP 5", "SELECT * FROM employes FIRST 5", "SELECT * FROM employes LIMIT 5", "SELECT 5 FROM employes"], "C", "LIMIT 5 garde 5 lignes maximum.")]),
        ("Compter et regrouper : GROUP BY", """Les **fonctions d'agrégation** calculent une valeur sur plusieurs lignes : `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`.

```
SELECT COUNT(*) FROM employes;
SELECT AVG(salaire) FROM employes;
SELECT departement_id, COUNT(*) FROM employes GROUP BY departement_id;
SELECT departement_id, SUM(salaire) FROM employes
GROUP BY departement_id HAVING SUM(salaire) > 3000;
```

- **GROUP BY** crée un groupe par valeur et applique la fonction à chaque groupe ;
- **HAVING** filtre les groupes (comme WHERE, mais après le regroupement) ;
- `WHERE` filtre les lignes **avant** le regroupement, `HAVING` filtre les groupes **après**.

> Exercice : combien d'employés y a-t-il dans chaque département ?""",
         [("Quelle fonction calcule la moyenne ?", ["MEAN()", "AVG()", "MOYENNE()", "SUM()"], "B", "AVG() calcule la moyenne, SUM() la somme."),
          ("Que fait GROUP BY departement_id ?", ["Trie les employés par département", "Supprime les départements", "Crée un groupe par département pour appliquer un calcul", "Affiche uniquement le premier département"], "C", "GROUP BY regroupe les lignes qui ont la même valeur."),
          ("Quelle clause filtre les groupes après un GROUP BY ?", ["WHERE", "LIMIT", "HAVING", "DISTINCT"], "C", "HAVING s'applique aux groupes ; WHERE s'applique aux lignes avant regroupement.")]),
        ("Modifier les données : INSERT, UPDATE, DELETE", """Trois commandes modifient le contenu d'une table :

```
INSERT INTO departements (id, nom, ville) VALUES (6, 'Juridique', 'Kinshasa');
UPDATE employes SET salaire = 1900 WHERE id = 1;
DELETE FROM employes WHERE id = 9;
```

- **INSERT** ajoute une ligne ;
- **UPDATE** modifie des lignes existantes ;
- **DELETE** supprime des lignes.

> DANGER : un `UPDATE` ou un `DELETE` sans `WHERE` agit sur TOUTES les lignes de la table. Vérifiez toujours avec un `SELECT` et le même `WHERE` avant de modifier.

Le Terrain SQL de la plateforme est en lecture seule : vous ne pouvez pas casser la base d'exemple.""",
         [("Quelle commande ajoute une nouvelle ligne ?", ["ADD ROW", "UPDATE", "INSERT INTO", "CREATE LINE"], "C", "INSERT INTO ajoute une ligne dans une table."),
          ("Que se passe-t-il avec DELETE FROM employes; (sans WHERE) ?", ["Rien, la commande est refusée", "Seul le premier employé est supprimé", "Tous les employés sont supprimés", "Seuls les employés sans département sont supprimés"], "C", "Sans WHERE, la commande s'applique à toutes les lignes."),
          ("Quelle bonne pratique avant un UPDATE ?", ["Lancer un SELECT avec le même WHERE", "Redémarrer l'ordinateur", "Supprimer la table", "Ne jamais utiliser WHERE"], "A", "Le SELECT montre exactement les lignes qui seront modifiées.")]),
    ],
}

SQL2 = {
    "title": "SQL – Niveau 2 : Jointures et analyses",
    "category": "Bases de données", "level": "Intermédiaire", "fee": 30,
    "description": ("Relier plusieurs tables, gérer les valeurs absentes et écrire des requêtes d'analyse. "
                    "Ce cours suppose que vous maîtrisez SELECT, WHERE et GROUP BY (Niveau 1)."),
    "lessons": [
        ("Relations et clés étrangères", """Dans une base bien construite, on ne répète pas les informations. Au lieu d'écrire « Informatique » sur chaque employé, on stocke le numéro du département.

La colonne `departement_id` de la table `employes` est une **clé étrangère** : elle pointe vers la clé primaire `id` de la table `departements`.

- 1 département a **plusieurs** employés (relation un-à-plusieurs) ;
- une jointure permet de recomposer l'information complète à partir de plusieurs tables.

> Avantage : si le nom d'un département change, on le modifie à un seul endroit.""",
         [("Qu'est-ce qu'une clé étrangère ?", ["Une colonne qui référence la clé primaire d'une autre table", "Une clé pour chiffrer la base", "Une colonne toujours vide", "Le nom de la table"], "A", "departement_id référence departements.id."),
          ("Pourquoi éviter de répéter les informations dans chaque ligne ?", ["Pour gagner de la place uniquement", "Pour qu'une modification soit faite à un seul endroit", "Parce que SQL l'interdit", "Pour trier plus vite"], "B", "Une donnée stockée une seule fois reste cohérente.")]),
        ("Jointures avec INNER JOIN", """**JOIN** relie deux tables grâce à une condition `ON`.

```
SELECT e.nom, e.prenom, d.nom AS departement
FROM employes e
JOIN departements d ON d.id = e.departement_id;
```

- `e` et `d` sont des **alias** : des noms courts pour les tables ;
- on écrit `table.colonne` (ou `alias.colonne`) quand deux tables ont une colonne de même nom ;
- un `INNER JOIN` (ou simplement `JOIN`) ne garde que les lignes qui ont une correspondance des deux côtés.

> Résultat : les employés sans département (departement_id NULL) n'apparaissent pas.""",
         [("Que fait la condition ON dans une jointure ?", ["Elle trie le résultat", "Elle indique comment relier les lignes des deux tables", "Elle supprime les doublons", "Elle limite le nombre de lignes"], "B", "ON précise la correspondance entre les colonnes des deux tables."),
          ("Un INNER JOIN retourne :", ["Toutes les lignes de la table de gauche", "Toutes les lignes des deux tables", "Uniquement les lignes avec correspondance des deux côtés", "Uniquement les lignes sans correspondance"], "C", "INNER JOIN ne garde que les correspondances."),
          ("À quoi servent les alias (e, d) ?", ["À chiffrer les tables", "À raccourcir et distinguer les noms de tables", "À créer de nouvelles tables", "À trier les colonnes"], "B", "Les alias rendent la requête plus courte et plus claire.")]),
        ("LEFT JOIN et valeurs NULL", """Un **LEFT JOIN** garde **toutes** les lignes de la table de gauche, même sans correspondance à droite. Les colonnes manquantes valent `NULL`.

```
SELECT e.nom, d.nom AS departement
FROM employes e
LEFT JOIN departements d ON d.id = e.departement_id;
```

Ici, Kanku (sans département) apparaît, avec `NULL` dans la colonne departement.

Trouver les lignes SANS correspondance :
```
SELECT e.nom FROM employes e
LEFT JOIN departements d ON d.id = e.departement_id
WHERE d.id IS NULL;
```

> Utile pour détecter des données incomplètes : employés sans département, clients sans commande...""",
         [("Quelle est la différence entre LEFT JOIN et INNER JOIN ?", ["Aucune", "LEFT JOIN garde aussi les lignes de gauche sans correspondance", "LEFT JOIN est plus lent mais identique", "LEFT JOIN supprime les NULL"], "B", "LEFT JOIN conserve toute la table de gauche."),
          ("Comment trouver les employés sans département avec un LEFT JOIN ?", ["WHERE d.id = 0", "WHERE d.id IS NULL", "WHERE d.id = NULL", "HAVING d.id > 0"], "B", "Sans correspondance, les colonnes de droite valent NULL, testées avec IS NULL.")]),
        ("Sous-requêtes et analyses", """Une **sous-requête** est une requête placée dans une autre.

Employés mieux payés que la moyenne :
```
SELECT nom, salaire FROM employes
WHERE salaire > (SELECT AVG(salaire) FROM employes);
```

Employés du département « Formation » :
```
SELECT nom FROM employes
WHERE departement_id IN (SELECT id FROM departements WHERE nom = 'Formation');
```

Combiner jointure, regroupement et filtre :
```
SELECT d.nom, COUNT(*) AS nb, AVG(e.salaire) AS moyenne
FROM departements d JOIN employes e ON e.departement_id = d.id
GROUP BY d.nom
HAVING COUNT(*) >= 3
ORDER BY moyenne DESC;
```

> Méthode : écrivez d'abord la sous-requête seule, vérifiez son résultat, puis intégrez-la.""",
         [("Que calcule (SELECT AVG(salaire) FROM employes) placé dans un WHERE ?", ["La somme des salaires", "Le salaire moyen, utilisé comme valeur de comparaison", "Le nombre d'employés", "Le salaire maximum"], "B", "La sous-requête renvoie une valeur (la moyenne) utilisée dans la comparaison."),
          ("Quelle méthode est recommandée pour écrire une sous-requête ?", ["L'écrire directement dans la grande requête", "L'écrire et la tester seule d'abord", "Éviter les tests", "Utiliser uniquement DELETE"], "B", "Tester la sous-requête seule évite les erreurs difficiles à repérer."),
          ("Dans l'exemple final, HAVING COUNT(*) >= 3 sert à :", ["Garder les départements d'au moins 3 employés", "Limiter à 3 lignes", "Trier par 3 colonnes", "Supprimer 3 départements"], "A", "HAVING filtre les groupes selon le résultat de COUNT(*).")]),
    ],
}

FICHIERS = {
    "title": "Bureautique – Gérer ses fichiers et dossiers",
    "category": "Bureautique", "level": "Débutant", "fee": 0,
    "description": "Les bases de l'organisation d'un ordinateur Windows : créer, renommer, copier et déplacer dossiers et fichiers.",
    "lessons": [
        ("Créer un dossier", """Un **dossier** range vos fichiers, comme un classeur.

Étapes :
- ouvrez l'Explorateur de fichiers (touches Windows + E) ;
- placez-vous à l'endroit voulu (par exemple Documents) ;
- faites un clic droit dans un espace vide, puis **Nouveau > Dossier** ;
- tapez le nom du dossier et appuyez sur Entrée.

> Astuce : le raccourci Ctrl + Maj + N crée directement un nouveau dossier.""",
         [("Quel raccourci crée un nouveau dossier ?", ["Ctrl + Maj + N", "Ctrl + Z", "Alt + F4", "Ctrl + P"], "A", "Ctrl + Maj + N crée un dossier dans l'Explorateur."),
          ("Où fait-on le clic droit pour créer un dossier ?", ["Sur un fichier existant", "Dans un espace vide du dossier courant", "Sur la barre des tâches", "Sur le bureau uniquement"], "B", "On clique dans un espace vide de l'emplacement voulu.")]),
        ("Renommer un dossier", """Pour changer le nom d'un dossier :
- sélectionnez-le d'un clic ;
- appuyez sur la touche **F2** (ou clic droit puis **Renommer**) ;
- tapez le nouveau nom et validez avec Entrée.

Un nom de dossier ne peut pas contenir les caractères suivants : `\\ / : * ? " < > |`

> Conseil : choisissez des noms clairs, par exemple `Factures_2026` plutôt que `Nouveau dossier (3)`.""",
         [("Quelle touche permet de renommer un élément sélectionné ?", ["F1", "F2", "F5", "Échap"], "B", "F2 passe le nom en mode édition."),
          ("Quel caractère est interdit dans un nom de dossier ?", ["Le tiret bas _", "Le chiffre 2", "Le point d'interrogation ?", "La lettre A"], "C", "Les caractères \\ / : * ? \" < > | sont interdits.")]),
        ("Copier et déplacer un fichier", """- **Copier** crée un double : le fichier reste à sa place d'origine (Ctrl + C, puis Ctrl + V ailleurs) ;
- **Déplacer** change l'emplacement : le fichier n'est plus à l'ancien endroit (Ctrl + X, puis Ctrl + V ailleurs) ;
- on peut aussi faire **glisser-déposer** le fichier vers un dossier.

Pour sélectionner plusieurs fichiers : maintenez Ctrl et cliquez sur chacun, ou utilisez Ctrl + A pour tout sélectionner.

> Avant de déplacer des fichiers importants, faites toujours une copie de sauvegarde.""",
         [("Quelle est la différence entre copier et déplacer ?", ["Aucune", "Copier garde l'original, déplacer le retire de l'ancien emplacement", "Déplacer garde l'original", "Copier supprime le fichier"], "B", "Copier duplique ; déplacer change l'emplacement."),
          ("Quel raccourci sélectionne tous les fichiers du dossier ?", ["Ctrl + A", "Ctrl + S", "Ctrl + N", "Ctrl + T"], "A", "Ctrl + A = tout sélectionner.")]),
    ],
}


def _add_course(db, trainer_id, data):
    cur = db.execute(
        "INSERT INTO courses (title, category, level, description, fee_amount, pass_mark, trainer_id) "
        "VALUES (?,?,?,?,?,70,?)",
        (data["title"], data["category"], data["level"], data["description"], data["fee"], trainer_id))
    course_id = cur.lastrowid
    lesson_ids = []
    for pos, (title, content, questions) in enumerate(data["lessons"], start=1):
        lid = db.execute("INSERT INTO lessons (course_id, position, title, content) VALUES (?,?,?,?)",
                         (course_id, pos, title, content)).lastrowid
        lesson_ids.append(lid)
        for text, opts, correct, expl in questions:
            db.execute("INSERT INTO questions (lesson_id, text, option_a, option_b, option_c, option_d, correct, explanation) "
                       "VALUES (?,?,?,?,?,?,?,?)", (lid, text, *opts, correct, expl))
    return course_id, lesson_ids


def seed(db):
    """Remplit une base vide. Retourne un résumé."""
    pw = generate_password_hash
    fid = db.execute("INSERT INTO users (full_name,email,password_hash,role) VALUES (?,?,?,'formateur')",
                     (FORMATEUR[0], FORMATEUR[1], pw(FORMATEUR[2]))).lastrowid
    secid = db.execute("INSERT INTO users (full_name,email,password_hash,role) VALUES (?,?,?,'secretaire')",
                       (SECRETAIRE[0], SECRETAIRE[1], pw(SECRETAIRE[2]))).lastrowid

    svc_id = db.execute("INSERT INTO services (name, chef_id) VALUES (?,?)",
                        ("Service Informatique de gestion", fid)).lastrowid
    db.execute("INSERT INTO services (name) VALUES (?)", ("Service Électricité",))

    fil_ids = []
    for name, fee in FILIERES:
        fil_ids.append(db.execute("INSERT INTO filieres (name, material_fee) VALUES (?,?)", (name, fee)).lastrowid)
    db.execute("UPDATE filieres SET service_id=? WHERE id=?", (svc_id, fil_ids[0]))

    def register(name, sex, filiere_idx, trainee_type, institution="", letter_ref="", letter_status="none"):
        import fees as _fees
        cfg = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
        filiere = db.execute("SELECT * FROM filieres WHERE id=?", (fil_ids[filiere_idx],)).fetchone()
        snap = _fees.fee_snapshot(trainee_type, cfg, filiere)
        return db.execute(
            "INSERT INTO registrations (full_name, sex, filiere_id, trainee_type, institution, letter_ref, "
            "letter_status, fee_inscription, fee_material, fee_formation, fee_jury, registered_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, sex, fil_ids[filiere_idx], trainee_type, institution, letter_ref, letter_status,
             snap["fee_inscription"], snap["fee_material"], snap["fee_formation"], snap["fee_jury"], secid)).lastrowid

    def pay(rid, kind, amount, currency, ref, days_ago, period=None):
        db.execute("INSERT INTO payments (registration_id, kind, amount, currency, period, bank_ref, paid_at, "
                   "recorded_by) VALUES (?,?,?,?,?,?,date('now',?),?)",
                   (rid, kind, amount, currency, period, ref, f"-{days_ago} days", secid))

    # Stagiaire non recommandé, en ordre (inscription + matériel payés)
    r1 = register("Josué Kalala", "M", 0, "non_recommande")
    pay(r1, "inscription", 40000, "FC", "FN-0001", 20)
    pay(r1, "materiel", 50, "USD", "FN-0002", 20)
    pay(r1, "formation", 50000, "FC", "FN-0003", 20, period=__import__("time").strftime("%Y-%m"))
    db.commit()

    # Stagiaire non recommandé, paiement partiel (encore en attente)
    r2 = register("Nadège Mwamba", "F", 1, "non_recommande")
    pay(r2, "inscription", 40000, "FC", "FN-0004", 5)

    # Stagiaire recommandé total (institution privée) : aucun frais, en ordre dès l'approbation de la lettre
    r3 = register("Patrick Ilunga", "M", 2, "recommande_total", institution="ISP Kinshasa",
                  letter_ref="ISP/2026/014", letter_status="approved")
    db.execute("UPDATE registrations SET letter_decided_by=?, letter_decided_at=date('now','-3 days') WHERE id=?",
              ("Directeur des études", r3))

    # Stagiaire recommandé partiel (institution étatique) : lettre en attente d'approbation
    r4 = register("Solange Kabeya", "F", 0, "recommande_partiel", institution="Ministère de l'Emploi",
                  letter_ref="MIN-EMP/2026/077", letter_status="pending")

    for rid in (r1, r3):
        summary = fees.summarize(db.execute("SELECT * FROM registrations WHERE id=?", (rid,)).fetchone(),
                                 db.execute("SELECT * FROM payments WHERE registration_id=?", (rid,)).fetchall())
        if summary["en_ordre"]:
            code = f"INPP-CS-{__import__('time').strftime('%Y')}-{__import__('secrets').token_hex(3).upper()}"
            db.execute("UPDATE registrations SET card_code=?, card_issued_at=datetime('now') WHERE id=?", (code, rid))

    # Section de démonstration (présences) : les 4 stagiaires du secrétariat, horaire 8h30 + 15 min
    section_id = db.execute(
        "INSERT INTO sections (filiere_id, trainer_id, name, start_time, grace_minutes, end_time) "
        "VALUES (?,?,?,?,?,?)", (fil_ids[0], fid, "Informatique de gestion - groupe A", "08:30", 15, "12:30")).lastrowid
    for rid in (r1, r2, r3, r4):
        db.execute("UPDATE registrations SET section_id=? WHERE id=?", (section_id, rid))
    import time as _time
    db.execute("INSERT INTO attendance (section_id, registration_id, day, status, checkin_at, source, marked_by) "
              "VALUES (?,?,?,?,?,?,?)", (section_id, r1, _time.strftime("%Y-%m-%d"), "present", "08:31", "qr", fid))
    db.execute("INSERT INTO attendance (section_id, registration_id, day, status, checkin_at, source, marked_by) "
              "VALUES (?,?,?,?,?,?,?)", (section_id, r3, _time.strftime("%Y-%m-%d"), "retard", "09:10", "qr", fid))
    db.execute("INSERT INTO absence_notices (registration_id, section_id, for_day, kind, message) "
              "VALUES (?,?,?,?,?)",
              (r2, section_id, _time.strftime("%Y-%m-%d"), "retard", "Embouteillage, j'arriverai vers 9h."))

    sid = []
    for i, name in enumerate(STAGIAIRES, start=1):
        sid.append(db.execute(
            "INSERT INTO users (full_name,email,password_hash,role,created_by) VALUES (?,?,?,'stagiaire',?)",
            (name, f"stagiaire{i:02d}@inpp.cd", pw(PWD_STAGIAIRE), fid)).lastrowid)

    c1, l1 = _add_course(db, fid, SQL1)
    c2, l2 = _add_course(db, fid, SQL2)
    c3, l3 = _add_course(db, fid, FICHIERS)

    # Examen final de démonstration sur SQL Niveau 2 : publié, sans créneau fixé (ouvert dès maintenant),
    # 2 tentatives, 20 minutes. Sur ce cours, seuls stagiaire01 et stagiaire02 sont inscrits (voir plus bas).
    exam_id = db.execute(
        "INSERT INTO exams (course_id, title, duration_minutes, pass_mark, max_attempts, published) "
        "VALUES (?,?,?,?,?,1)", (c2, "Examen final — SQL Niveau 2", 20, 60, 2)).lastrowid
    for text, opts, correct, expl in [
        ("Quelle commande affiche toutes les colonnes d'une table ?",
         ["SELECT * FROM table", "GET * FROM table", "SHOW table", "READ table"], "A",
         "SELECT * FROM table affiche toutes les colonnes."),
        ("À quoi sert la clause WHERE ?", ["Trier les résultats", "Filtrer les lignes", "Compter les lignes",
         "Renommer une colonne"], "B", "WHERE filtre les lignes selon une condition."),
        ("Que fait ORDER BY ?", ["Filtre les lignes", "Trie les résultats", "Supprime des lignes",
         "Crée une table"], "B", "ORDER BY trie le résultat selon une ou plusieurs colonnes."),
        ("Quelle clé identifie une ligne de façon unique ?", ["Clé étrangère", "Clé primaire", "Index",
         "Alias"], "B", "La clé primaire (souvent id) est unique pour chaque ligne."),
    ]:
        db.execute("INSERT INTO exam_questions (exam_id, text, option_a, option_b, option_c, option_d, "
                   "correct, explanation) VALUES (?,?,?,?,?,?,?,?)", (exam_id, text, *opts, correct, expl))

    def enroll(idx, course, status="approved", fee="unpaid"):
        db.execute("INSERT INTO enrollments (user_id,course_id,status,fee_status,decided_at,decided_by) "
                   "VALUES (?,?,?,?,CASE WHEN ?='pending' THEN NULL ELSE datetime('now','-10 days') END,"
                   "CASE WHEN ?='pending' THEN NULL ELSE ? END)",
                   (sid[idx - 1], course, status, fee, status, status, fid))

    def done(idx, lesson, score, days):
        db.execute("INSERT INTO attempts (user_id,lesson_id,score,passed,created_at) VALUES (?,?,?,1,datetime('now',?))",
                   (sid[idx - 1], lesson, score, f"-{days} days"))
        db.execute("INSERT INTO progress (user_id,lesson_id,best_score,completed_at) VALUES (?,?,?,datetime('now',?))",
                   (sid[idx - 1], lesson, score, f"-{days} days"))

    def fail(idx, lesson, score, days):
        db.execute("INSERT INTO attempts (user_id,lesson_id,score,passed,created_at) VALUES (?,?,?,0,datetime('now',?))",
                   (sid[idx - 1], lesson, score, f"-{days} days"))

    # SQL 1 : 1 à 6 inscrits (validés), 7 et 8 en attente, 9 refusé
    for i, fee in zip(range(1, 7), ["paid", "paid", "exempt", "unpaid", "paid", "paid"]):
        enroll(i, c1, fee=fee)
    enroll(7, c1, "pending"); enroll(8, c1, "pending"); enroll(9, c1, "rejected")
    # SQL 2 : stagiaires 1 et 2
    enroll(1, c2, fee="paid"); enroll(2, c2, fee="unpaid")
    # Bureautique : 3, 4, 5
    for i in (3, 4, 5):
        enroll(i, c3, fee="exempt")

    # Progressions de démonstration
    for k, lid in enumerate(l1):                      # Aline : SQL 1 terminé
        done(1, lid, [100, 67 + 33, 100, 100, 100, 100][k], 9 - k)
    done(1, l2[0], 100, 2)
    for k in range(4):                                # Christian : 4/6
        done(2, l1[k], [100, 100, 75, 100][k], 8 - k)
    done(3, l1[0], 100, 6); done(3, l1[1], 100, 5)    # Divine : bloquée en leçon 3
    for s in (33, 33, 0):
        fail(3, l1[2], s, 1)
    done(4, l1[0], 100, 4)                            # Emmanuel : 1/6
    fail(5, l1[0], 33, 1)                             # Fabrice : n'a pas encore réussi la 1
    for k in range(3):                                # Grâce : 3/6
        done(6, l1[k], 100, 7 - k)
    for k in range(3):                                # Bureautique
        done(3, l3[k], 100, 3 - k) if k < 2 else None
    done(4, l3[0], 100, 2)

    # Certificat pour Aline (SQL 1 terminé)
    db.execute("INSERT INTO certificates (user_id,course_id,code) VALUES (?,?,?)", (sid[0], c1, "INPP-2026-A1B2C3"))
    db.commit()
    return {"formateur": FORMATEUR[1], "stagiaires": len(sid), "cours": 3}
