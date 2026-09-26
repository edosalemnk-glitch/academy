"""Données de démonstration : 1 formateur, 10 stagiaires, 3 cours complets avec quiz."""
from werkzeug.security import generate_password_hash

import fees

FORMATEUR = ("Prof. Daniel Mbayo", "formateur@inpp.cd", "Formateur2026!")
SECRETAIRE = ("Bibiche Kanyinda", "secretariat@inpp.cd", "Secretariat2026!")
PWD_STAGIAIRE = "Stagiaire2026!"

# Catalogue officiel des filières de l'INPP (Direction Provinciale de Kinshasa), par service :
# nom de la filière -> (métier visé, durée en mois, frais matériel en $, payables une seule fois).
# Source : fiche de renseignements INPP. La filière « Développement des Applications » (Informatique)
# n'a pas de durée ni de frais matériel lisibles sur la fiche d'origine : elle n'est donc pas reprise ici.
CATALOGUE = {
    "Service Électronique": [
        ("Audio radio / Vidéofréquence", "Réparateur des appareils électroniques", 4, 70),
        ("Technique Cellulaire", "Technicien cellulaire", 2, 70),
        ("Télécommunication", "Installateur des réseaux téléphoniques", 4, 70),
        ("Maintenance des micro-ordinateurs et réseau local", "Maintenancier des micro-ordinateurs", 3, 70),
        ("Prise de vue", "Preneur de vue", 2, 70),
        ("Montage vidéo", "Monteur vidéo", 2, 70),
        ("Domotique (Vidéo surveillance)", "Domoticien", 2, 70),
        ("Montage des amplificateurs audio et enceinte acoustiques",
         "Monteur des amplificateurs audio et enceintes acoustiques", 4, 70),
        ("Pilotage de drone civil", "Pilote de Drone civil", 2, 70),
        ("Animation et présentation des émissions TV/Radio", "Animateur / Présentateur", 3, 70),
    ],
    "Service Électricité": [
        ("Électricité industrielle", "Électricien", 6, 60),
        ("Électricité de bâtiment", "Électricien du bâtiment", 4, 60),
        ("Bobinage", "Électricien Bobineur", 3, 60),
    ],
    "Service Énergies renouvelables": [
        ("Énergie Solaire (Photovoltaïque)", "Technicien installateur des générateurs photovoltaïques", 3, 60),
        ("Efficacité Énergétique du Bâtiment", "Technicien en efficacité énergétique du bâtiment", 2, 60),
    ],
    "Service Froid et Climatisation": [
        ("Froid ménager", "Technicien en froid ménager", 2, 90),
        ("Froid commercial et industriel", "Technicien en froid commercial et industriel", 6, 90),
        ("Climatisation centrale", "Technicien en climatisation centrale", 4, 90),
    ],
    "Service Mécanique Automobile": [
        ("Maintenance Automobile", "Maintenancier Auto", 4, 60),
        ("Moteur à Essence", "Mécanicien en moteur à essence", 6, 60),
        ("Moteur Diesel", "Mécanicien en moteur diesel", 6, 60),
        ("Moteur Diesel spécial", "Mécanicien en moteur diesel", 3, 60),
        ("Injection électronique d'essence", "Technicien en injection électronique moteur essence", 4, 60),
        ("Électricité Automobile", "Électricien automobile", 6, 60),
        ("Révision matérielle d'injection", "Mécanicien en pompe d'injection", 3, 50),
        ("Réparation et entretien de groupe électrogène", "Maintenancier des groupes électrogènes", 7, 70),
        ("Conduite Automobile", "Conducteur des véhicules automobiles légers", 3, 60),
        ("Conduite automobile accélérée", "Conducteur des véhicules automobiles légers", 1, 250),
        ("Climatisation automobile", "Technicien en climatisation auto", 3, 90),
    ],
    "Service Mécanique Générale": [
        ("Tournage", "Tourneur sur machines conventionnelles", 5, 60),
        ("Fraisage", "Fraiseur sur machines conventionnelles", 5, 60),
        ("Conducteur de chariot élévateur à conducteur porté", "Cariste", 2, 500),
        ("Technique de maintenance des équipements hydropneumatiques",
         "Maintenancier des installations hydropneumatiques", 3, 200),
    ],
    "Service Tôlerie / Soudure": [
        ("Ajustage-soudage", "Ajusteur-soudeur", 4, 60),
        ("Plomberie sanitaire", "Installateur sanitaire", 3, 60),
        ("Menuiserie en aluminium", "Menuisier en aluminium", 3, 60),
    ],
    "Service CCEC": [
        ("Esthétique et Coiffure", "Esthéticien - coiffeur", 3, 60),
        ("Coupe et Couture", "Couturier", 4, 70),
        ("Modélisme", "Modéliste", 3, 70),
        ("Décoration événementielle", "Décorateur des événements", 2, 70),
        ("Maintenance de machine à coudre", "Maintenancier de machine à coudre", 2, 70),
        ("Make up", "Maquilleuse", 1, 100),
    ],
    "Service CFPRP": [
        ("Inspecteur de Protection Industrielle", "Inspecteur de protection industrielle", 4, 60),
        ("Officier de Police Judiciaire", "Officier de police judiciaire", 4, 60),
        ("Logistique des approvisionnements", "Logisticien des approvisionnements", 2, 60),
        ("Gestion des Projets", "Gestionnaire des projets", 2, 60),
        ("Maintenance des Systèmes de Détection d'incendie",
         "Maintenancier des systèmes de détection d'incendie", 4, 60),
        ("Entrepreneuriat", "Entrepreneur", 2, 60),
        ("Prévention et lutte anti incendie", "Pompier auxiliaire", 1, 100),
        ("Secourisme industriel", "Secouriste", 1, 100),
        ("Passation des Marchés Publics", "Chargé de passation des marchés", 2, 60),
        ("Gestion des ressources humaines", "Gestionnaire des ressources humaines", 2, 60),
    ],
    "Service Langues": [
        ("Anglais débutant", "", 3, 50),
        ("Anglais Intermédiaire", "", 3, 50),
        ("Anglais Avancé", "", 3, 50),
        ("Anglais des Affaires ou Business English", "", 3, 70),
        ("ETI (Étude de Traduction et d'Interprétation)", "", 3, 70),
        ("Français Expression Orale", "", 2, 50),
        ("Français Expression Écrite", "", 2, 50),
    ],
    "Service Hôtellerie et Restauration": [
        ("Restauration", "Serveur", 4, 70),
        ("Pâtisserie", "Commis pâtissier", 4, 70),
        ("Cuisine", "Commis cuisinier", 4, 70),
        ("Hébergement", "Technicien d'hébergement", 3, 70),
        ("Accueil et protocole", "Hôte ou Hôtesse d'accueil", 3, 70),
    ],
    "Service Bâtiment et Génie Civil": [
        ("Métré et devis de bâtiment", "Métreur - deviseur", 6, 70),
        ("Cartographie Numérique (SIG)", "Technicien en cartographie numérique", 3, 70),
        ("Maçonnerie", "Maçon", 6, 70),
        ("Menuiserie et ébénisterie", "Menuisier de bâtiment ébéniste", 6, 70),
        ("Perspective et maquette", "Maquettiste", 6, 70),
        ("Dessin de bâtiment", "Dessinateur de bâtiment", 6, 70),
        ("Carrelage", "Carreleur", 6, 70),
        ("Peinture", "Peintre de bâtiment", 4, 70),
        ("Topographie", "Technicien en topographie", 6, 70),
        ("Calcul des structures", "Analyste des structures de construction", 6, 70),
        ("Robbot", "Analyste des structures de construction à l'aide de l'ordinateur", 3, 70),
        ("Dessin assisté par ordinateur (DAO)", "Dessinateur de bâtiment assisté par ordinateur", 3, 70),
        ("Conducteur des travaux", "Conducteur des travaux", 4, 70),
        ("Staff et décoration", "Staffeur - décorateur", 4, 90),
        ("Peinture Design", "Peintre Designer", 4, 70),
        ("Charpente en bois & Couverture", "Charpentier couvreur", 6, 90),
        ("Assainissement", "", 4, 90),
        ("Aménagement paysagers", "Aménageur des jardins et espaces", 4, 90),
    ],
    "Service Informatique": [
        ("Bureautique Word", "", 1, 60),
        ("Bureautique Excel", "", 1, 60),
        ("PowerPoint", "", 1, 60),
        ("Académie Cisco : IT Essentials", "IT Professionnel", 3, 70),
        ("CCNA 1 : Notion sur réseaux", "Technicien en réseaux CISCO", 2, 90),
        ("CCNA 2 : Protocole et concept de routage", "Technicien en réseaux CISCO", 2, 90),
        ("CCNA 3 : Communication de réseau LAN et réseau sans fil — Accès au réseau étendu",
         "Technicien en réseaux CISCO", 2, 90),
        ("Administration Systèmes : Conceptions et applications sur le réseau", "Administrateur système", 2, 70),
        ("Administration Systèmes : Administration Windows 2021 server", "Administrateur système", 2, 70),
        ("Administration des Bases de Données : Modélisation d'une base de données",
         "Technicien de base de données", 2, 70),
        ("Sous MS ACCESS ou SQL server 2019", "Technicien de base de données", 3, 70),
        ("Webmaster (création d'un site dynamique)", "Concepteur et réalisateur des sites web", 3, 70),
        ("Infographie : Adobe Photoshop / Adobe InDesign", "Graphiste", 2, 70),
        ("Cyber - sécurité", "Technicien en Cybersécurité", 4, 100),
    ],
}
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
    "start_date": "2026-10-12", "end_date": "2026-11-06",
    "schedule": "Lundi–Vendredi · 08h30–12h30", "location": "INPP Matadi",
    "seats": 30,
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


def _default_case_study(data):
    category = data.get("category", "").lower()
    title = data.get("title", "").lower()
    if "bases de données" in category and "niveau 1" in title:
        return ("Vous êtes agent informatique dans un centre de formation. La direction vous demande de retrouver "
                "rapidement les stagiaires, leurs résultats et les informations utiles dans une base de données. "
                "Votre mission : interroger les tables, filtrer les données et produire les bons résultats.")
    if "bases de données" in category and "niveau 2" in title:
        return ("Le responsable administratif doit consolider les informations pour préparer un rapport mensuel. "
                "Votre mission : relier les tables, construire des requêtes avancées et extraire des indicateurs fiables.")
    if "bureautique" in category:
        return ("Le secrétariat reçoit chaque semaine des documents de plusieurs services. Votre mission : "
                "organiser les fichiers, retrouver rapidement un document et éviter les erreurs de classement.")
    return data.get("case_study", "")


def _add_course(db, trainer_id, data):
    service = db.execute(
        "SELECT service_id FROM service_formateurs WHERE user_id=? ORDER BY service_id LIMIT 1",
        (trainer_id,)
    ).fetchone()
    service_id = service["service_id"] if service else None
    cur = db.execute(
        "INSERT INTO courses (title, category, level, description, case_study, fee_amount, pass_mark, "
        "start_date, end_date, schedule, location, seats, registration_open, service_id, trainer_id) "
        "VALUES (?,?,?,?,?,?,?, ?,?,?,?,?,?,?,?)",
        (data["title"], data["category"], data["level"], data["description"], _default_case_study(data),
         data["fee"], 70, data.get("start_date"), data.get("end_date"), data.get("schedule", ""),
         data.get("location", ""), data.get("seats", 0), data.get("registration_open", 1), service_id, trainer_id))
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


def restore_demo(db):
    """Restaure les données de démonstration manquantes sans remplacer les données existantes."""
    pw = generate_password_hash

    def user(full_name, email, password, role, created_by=None):
        row = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if row:
            return row["id"]
        return db.execute(
            "INSERT INTO users (full_name,email,password_hash,role,created_by) VALUES (?,?,?,?,?)",
            (full_name, email, pw(password), role, created_by)
        ).lastrowid

    fid = user(FORMATEUR[0], FORMATEUR[1], FORMATEUR[2], "formateur")
    secid = user(SECRETAIRE[0], SECRETAIRE[1], SECRETAIRE[2], "secretaire")

    # Le catalogue officiel existe déjà en production : on ne le remplace jamais.
    svc_ids = {}
    for service_name in CATALOGUE:
        row = db.execute("SELECT id FROM services WHERE name=?", (service_name,)).fetchone()
        if row:
            svc_ids[service_name] = row["id"]
        else:
            chef = fid if service_name == "Service Informatique" else None
            svc_ids[service_name] = db.execute(
                "INSERT INTO services (name,chef_id) VALUES (?,?)", (service_name, chef)
            ).lastrowid

    # Le formateur de démonstration est membre du service Informatique.
    if "Service Informatique" in svc_ids:
        db.execute(
            "INSERT INTO service_formateurs (service_id,user_id) VALUES (?,?) ON CONFLICT DO NOTHING",
            (svc_ids["Service Informatique"], fid)
        )

    # Trois filières présentes dans la sauvegarde formation.db, hors catalogue actuel.
    legacy_services = {
        "Service Informatique de gestion": fid,
        "Service Électricité": None,
    }
    for name, chef in legacy_services.items():
        row = db.execute("SELECT id FROM services WHERE name=?", (name,)).fetchone()
        if not row:
            db.execute("INSERT INTO services (name,chef_id) VALUES (?,?)", (name, chef))
    extra_filieres = [
        ("Informatique de gestion", 50, 1, "Service Informatique de gestion"),
        ("Électricité du bâtiment", 80, 1, "Service Électricité"),
        ("Coupe et couture", 40, 1, "Service CCEC"),
    ]
    for name, material_fee, active, service_name in extra_filieres:
        if not db.execute("SELECT 1 FROM filieres WHERE name=?", (name,)).fetchone():
            sid = db.execute("SELECT id FROM services WHERE name=?", (service_name,)).fetchone()["id"]
            db.execute(
                "INSERT INTO filieres (name,material_fee,active,service_id) VALUES (?,?,?,?)",
                (name, material_fee, active, sid)
            )

    trainee_ids = {}
    for i, name in enumerate(STAGIAIRES, start=1):
        trainee_ids[name] = user(
            name, f"stagiaire{i:02d}@inpp.cd", PWD_STAGIAIRE, "stagiaire", fid
        )

    course_ids = {}
    lesson_ids = {}
    for course_data in (SQL1, SQL2, FICHIERS):
        row = db.execute("SELECT id FROM courses WHERE title=?", (course_data["title"],)).fetchone()
        if row:
            cid = row["id"]
            nlessons = db.execute("SELECT COUNT(*) AS n FROM lessons WHERE course_id=?", (cid,)).fetchone()["n"]
            if nlessons == 0:
                cid, lids = _add_course(db, fid, course_data)
            else:
                lids = [r["id"] for r in db.execute(
                    "SELECT id FROM lessons WHERE course_id=? ORDER BY position", (cid,)
                ).fetchall()]
        else:
            cid, lids = _add_course(db, fid, course_data)
        course_ids[course_data["title"]] = cid
        lesson_ids[course_data["title"]] = lids
        existing_schedule = db.execute(
            "SELECT start_date, end_date, schedule, location, seats FROM courses WHERE id=?", (cid,)
        ).fetchone()
        if existing_schedule and not existing_schedule["start_date"]:
            db.execute(
                "UPDATE courses SET start_date=?, end_date=?, schedule=?, location=?, seats=?, registration_open=? WHERE id=?",
                (course_data.get("start_date"), course_data.get("end_date"), course_data.get("schedule", ""),
                 course_data.get("location", ""), course_data.get("seats", 0), course_data.get("registration_open", 1), cid)
            )

    c1 = course_ids[SQL1["title"]]
    c2 = course_ids[SQL2["title"]]
    c3 = course_ids[FICHIERS["title"]]

    # Examen final du fichier de sauvegarde.
    exam = db.execute("SELECT id FROM exams WHERE course_id=?", (c2,)).fetchone()
    if exam:
        exam_id = exam["id"]
    else:
        exam_id = db.execute(
            "INSERT INTO exams (course_id,title,duration_minutes,pass_mark,max_attempts,published) "
            "VALUES (?,?,?,?,?,1)",
            (c2, "Examen final — SQL Niveau 2", 20, 60, 2)
        ).lastrowid
    if db.execute("SELECT COUNT(*) AS n FROM exam_questions WHERE exam_id=?", (exam_id,)).fetchone()["n"] == 0:
        for text, opts, correct, expl in [
            ("Quelle commande affiche toutes les colonnes d'une table ?",
             ["SELECT * FROM table", "GET * FROM table", "SHOW table", "READ table"], "A",
             "SELECT * FROM table affiche toutes les colonnes."),
            ("À quoi sert la clause WHERE ?",
             ["Trier les résultats", "Filtrer les lignes", "Compter les lignes", "Renommer une colonne"], "B",
             "WHERE filtre les lignes selon une condition."),
            ("Que fait ORDER BY ?",
             ["Filtre les lignes", "Trie les résultats", "Supprime des lignes", "Crée une table"], "B",
             "ORDER BY trie le résultat selon une ou plusieurs colonnes."),
            ("Quelle clé identifie une ligne de façon unique ?",
             ["Clé étrangère", "Clé primaire", "Index", "Alias"], "B",
             "La clé primaire (souvent id) est unique pour chaque ligne.")
        ]:
            db.execute(
                "INSERT INTO exam_questions (exam_id,text,option_a,option_b,option_c,option_d,correct,explanation) "
                "VALUES (?,?,?,?,?,?,?,?)", (exam_id, text, *opts, correct, expl)
            )

    def enroll(name, course_id, status, fee_status):
        uid = trainee_ids[name]
        if not db.execute(
            "SELECT 1 FROM enrollments WHERE user_id=? AND course_id=?", (uid, course_id)
        ).fetchone():
            db.execute(
                "INSERT INTO enrollments (user_id,course_id,status,fee_status,decided_at,decided_by) "
                "VALUES (?,?,?,?,CASE WHEN ?='pending' THEN NULL ELSE datetime('now','-10 days') END,"
                "CASE WHEN ?='pending' THEN NULL ELSE ? END)",
                (uid, course_id, status, fee_status, status, status, fid)
            )

    for name, fee in [
        ("Aline Mbuyi", "paid"), ("Christian Tshibanda", "paid"),
        ("Divine Mukendi", "exempt"), ("Emmanuel Ilunga", "unpaid"),
        ("Fabrice Kasongo", "paid"), ("Grâce Lukusa", "paid")
    ]:
        enroll(name, c1, "approved", fee)
    enroll("Héritier Banza", c1, "pending", "unpaid")
    enroll("Isaac Ngoy", c1, "pending", "unpaid")
    enroll("Jocelyne Mutombo", c1, "rejected", "unpaid")
    enroll("Aline Mbuyi", c2, "approved", "paid")
    enroll("Christian Tshibanda", c2, "approved", "unpaid")
    for name in ("Divine Mukendi", "Emmanuel Ilunga", "Fabrice Kasongo"):
        enroll(name, c3, "approved", "exempt")

    def done(name, lesson_id, score, days):
        uid = trainee_ids[name]
        if not db.execute(
            "SELECT 1 FROM progress WHERE user_id=? AND lesson_id=?", (uid, lesson_id)
        ).fetchone():
            db.execute(
                "INSERT INTO attempts (user_id,lesson_id,score,passed,created_at) VALUES (?,?,?,1,datetime('now',?))",
                (uid, lesson_id, score, f"-{days} days")
            )
            db.execute(
                "INSERT INTO progress (user_id,lesson_id,best_score,completed_at) VALUES (?,?,?,datetime('now',?))",
                (uid, lesson_id, score, f"-{days} days")
            )

    def fail(name, lesson_id, score, days):
        uid = trainee_ids[name]
        if not db.execute(
            "SELECT 1 FROM attempts WHERE user_id=? AND lesson_id=? AND score=? AND passed=0",
            (uid, lesson_id, score)
        ).fetchone():
            db.execute(
                "INSERT INTO attempts (user_id,lesson_id,score,passed,created_at) VALUES (?,?,?,0,datetime('now',?))",
                (uid, lesson_id, score, f"-{days} days")
            )

    l1 = lesson_ids[SQL1["title"]]
    l3 = lesson_ids[FICHIERS["title"]]
    for k, lid in enumerate(l1):
        done("Aline Mbuyi", lid, [100, 100, 100, 100, 100, 100][k], 9-k)
    done("Aline Mbuyi", lesson_ids[SQL2["title"]][0], 100, 2)
    for k in range(4):
        done("Christian Tshibanda", l1[k], [100, 100, 75, 100][k], 8-k)
    done("Divine Mukendi", l1[0], 100, 6)
    done("Divine Mukendi", l1[1], 100, 5)
    for score in (33, 33, 0):
        fail("Divine Mukendi", l1[2], score, 1)
    done("Emmanuel Ilunga", l1[0], 100, 4)
    fail("Fabrice Kasongo", l1[0], 33, 1)
    for k in range(3):
        done("Grâce Lukusa", l1[k], 100, 7-k)
    done("Divine Mukendi", l3[0], 100, 3)
    done("Divine Mukendi", l3[1], 100, 2)
    done("Emmanuel Ilunga", l3[0], 100, 2)

    if not db.execute("SELECT 1 FROM certificates WHERE code=?", ("INPP-2026-A1B2C3",)).fetchone():
        db.execute(
            "INSERT INTO certificates (user_id,course_id,code) VALUES (?,?,?)",
            (trainee_ids["Aline Mbuyi"], c1, "INPP-2026-A1B2C3")
        )

    # Données administratives présentes dans formation.db : on les ajoute seulement si absentes.
    fil_map = {
        "Informatique de gestion": "Informatique de gestion",
        "Électricité du bâtiment": "Électricité du bâtiment",
        "Coupe et couture": "Coupe et couture",
    }
    legacy_regs = [
        ("Josué Kalala", "M", "", "Informatique de gestion", "non_recommande", "", "", "none",
         "", None, "", 40000, 50, 50000, 25000, "INPP-CS-2026-4471B9"),
        ("Nadège Mwamba", "F", "", "Électricité du bâtiment", "non_recommande", "", "", "none",
         "", None, "", 40000, 80, 50000, 25000, None),
        ("Patrick Ilunga", "M", "", "Coupe et couture", "recommande_total", "ISP Kinshasa", "ISP/2026/014", "approved",
         "Directeur des études", "2026-09-22", "", 0, 0, 0, 0, "INPP-CS-2026-8C6905"),
        ("Solange Kabeya", "F", "", "Informatique de gestion", "recommande_partiel", "Ministère de l'Emploi",
         "MIN-EMP/2026/077", "pending", "", None, "", 0, 50, 0, 25000, None),
    ]
    reg_ids = {}
    for (name, sex, phone, filiere_name, trainee_type, institution, letter_ref, letter_status,
         decided_by, decided_at, letter_note, fi, fm, ff, fj, card_code) in legacy_regs:
        row = db.execute("SELECT id FROM registrations WHERE full_name=?", (name,)).fetchone()
        if row:
            reg_ids[name] = row["id"]
            continue
        fid_legacy = db.execute("SELECT id FROM filieres WHERE name=?", (filiere_name,)).fetchone()["id"]
        reg_ids[name] = db.execute(
            "INSERT INTO registrations (full_name,sex,phone,filiere_id,trainee_type,institution,letter_ref,"
            "letter_status,letter_decided_by,letter_decided_at,letter_note,fee_inscription,fee_material,"
            "fee_formation,fee_jury,card_code,registered_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (name,sex,phone,fid_legacy,trainee_type,institution,letter_ref,letter_status,decided_by,
             decided_at,letter_note,fi,fm,ff,fj,card_code,secid)
        ).lastrowid

    for name, kind, amount, currency, period, ref, days in [
        ("Josué Kalala","inscription",40000,"FC",None,"FN-0001",20),
        ("Josué Kalala","materiel",50,"USD",None,"FN-0002",20),
        ("Josué Kalala","formation",50000,"FC","2026-09","FN-0003",20),
        ("Nadège Mwamba","inscription",40000,"FC",None,"FN-0004",5),
    ]:
        if not db.execute("SELECT 1 FROM payments WHERE bank_ref=?", (ref,)).fetchone():
            db.execute(
                "INSERT INTO payments (registration_id,kind,amount,currency,period,bank_ref,paid_at,recorded_by) "
                "VALUES (?,?,?,?,?,?,date('now',?),?)",
                (reg_ids[name],kind,amount,currency,period,ref,f"-{days} days",secid)
            )

    section = db.execute("SELECT id FROM sections WHERE name=?", ("Informatique de gestion - groupe A",)).fetchone()
    if not section:
        fid_legacy = db.execute("SELECT id FROM filieres WHERE name=?", ("Informatique de gestion",)).fetchone()["id"]
        section_id = db.execute(
            "INSERT INTO sections (filiere_id,trainer_id,name,start_time,grace_minutes,end_time) VALUES (?,?,?,?,?,?)",
            (fid_legacy,fid,"Informatique de gestion - groupe A","08:30",15,"12:30")
        ).lastrowid
    else:
        section_id = section["id"]
    for name in ("Josué Kalala","Nadège Mwamba","Patrick Ilunga","Solange Kabeya"):
        db.execute("UPDATE registrations SET section_id=? WHERE id=?", (section_id, reg_ids[name]))
    today = __import__("time").strftime("%Y-%m-%d")
    if not db.execute("SELECT 1 FROM attendance WHERE section_id=? AND registration_id=? AND day=?",
                      (section_id,reg_ids["Josué Kalala"],today)).fetchone():
        db.execute("INSERT INTO attendance (section_id,registration_id,day,status,checkin_at,source,marked_by) "
                   "VALUES (?,?,?,?,?,?,?)",
                   (section_id,reg_ids["Josué Kalala"],today,"present","08:31","qr",fid))
    if not db.execute("SELECT 1 FROM attendance WHERE section_id=? AND registration_id=? AND day=?",
                      (section_id,reg_ids["Patrick Ilunga"],today)).fetchone():
        db.execute("INSERT INTO attendance (section_id,registration_id,day,status,checkin_at,source,marked_by) "
                   "VALUES (?,?,?,?,?,?,?)",
                   (section_id,reg_ids["Patrick Ilunga"],today,"retard","09:10","qr",fid))
    if not db.execute("SELECT 1 FROM absence_notices WHERE registration_id=? AND section_id=? AND for_day=?",
                      (reg_ids["Nadège Mwamba"],section_id,today)).fetchone():
        db.execute("INSERT INTO absence_notices (registration_id,section_id,for_day,kind,message) VALUES (?,?,?,?,?)",
                   (reg_ids["Nadège Mwamba"],section_id,today,"retard","Embouteillage, j'arriverai vers 9h."))

    for key, value in [
        ("inscription_fee","40000"),("formation_fee","50000"),("jury_fee","25000"),
        ("bank_name","FN BANK"),("bank_account","")
    ]:
        if not db.execute("SELECT 1 FROM settings WHERE key=?", (key,)).fetchone():
            db.execute("INSERT INTO settings (key,value) VALUES (?,?)", (key,value))

    db.commit()
    return {"users": 12, "courses": 3, "lessons": 13, "questions": 33}

def seed(db):
    """Remplit une base vide. Retourne un résumé."""
    pw = generate_password_hash
    fid = db.execute("INSERT INTO users (full_name,email,password_hash,role) VALUES (?,?,?,'formateur')",
                     (FORMATEUR[0], FORMATEUR[1], pw(FORMATEUR[2]))).lastrowid
    secid = db.execute("INSERT INTO users (full_name,email,password_hash,role) VALUES (?,?,?,'secretaire')",
                       (SECRETAIRE[0], SECRETAIRE[1], pw(SECRETAIRE[2]))).lastrowid

    # Un service par catégorie du catalogue officiel ; le formateur de démonstration dirige le service
    # Informatique (auquel appartient la filière "Bureautique Word" utilisée plus bas).
    svc_ids = {}
    for service_name in CATALOGUE:
        chef = fid if service_name == "Service Informatique" else None
        svc_ids[service_name] = db.execute(
            "INSERT INTO services (name, chef_id) VALUES (?,?)", (service_name, chef)).lastrowid

    fil_ids = {}   # nom de filière -> id
    for service_name, rows in CATALOGUE.items():
        for name, metier, duration_months, fee in rows:
            fil_ids[name] = db.execute(
                "INSERT INTO filieres (name, metier, duration_months, material_fee, service_id) "
                "VALUES (?,?,?,?,?)", (name, metier, duration_months, fee, svc_ids[service_name])).lastrowid

    def register(name, sex, filiere_name, trainee_type, institution="", letter_ref="", letter_status="none"):
        import fees as _fees
        cfg = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM settings")}
        filiere = db.execute("SELECT * FROM filieres WHERE id=?", (fil_ids[filiere_name],)).fetchone()
        snap = _fees.fee_snapshot(trainee_type, cfg, filiere)
        return db.execute(
            "INSERT INTO registrations (full_name, sex, filiere_id, trainee_type, institution, letter_ref, "
            "letter_status, fee_inscription, fee_material, fee_formation, fee_jury, registered_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (name, sex, fil_ids[filiere_name], trainee_type, institution, letter_ref, letter_status,
             snap["fee_inscription"], snap["fee_material"], snap["fee_formation"], snap["fee_jury"], secid)).lastrowid

    def pay(rid, kind, amount, currency, ref, days_ago, period=None):
        db.execute("INSERT INTO payments (registration_id, kind, amount, currency, period, bank_ref, paid_at, "
                   "recorded_by) VALUES (?,?,?,?,?,?,date('now',?),?)",
                   (rid, kind, amount, currency, period, ref, f"-{days_ago} days", secid))

    # Stagiaire non recommandé, en ordre (inscription + matériel payés)
    r1 = register("Josué Kalala", "M", "Bureautique Word", "non_recommande")
    pay(r1, "inscription", 58000, "FC", "FN-0001", 20)
    pay(r1, "materiel", 60, "USD", "FN-0002", 20)
    pay(r1, "formation", 60000, "FC", "FN-0003", 20, period=__import__("time").strftime("%Y-%m"))
    db.commit()

    # Stagiaire non recommandé, paiement partiel (encore en attente)
    r2 = register("Nadège Mwamba", "F", "Électricité de bâtiment", "non_recommande")
    pay(r2, "inscription", 58000, "FC", "FN-0004", 5)

    # Stagiaire recommandé total (institution privée) : aucun frais, en ordre dès l'approbation de la lettre
    r3 = register("Patrick Ilunga", "M", "Coupe et Couture", "recommande_total", institution="ISP Kinshasa",
                  letter_ref="ISP/2026/014", letter_status="approved")
    db.execute("UPDATE registrations SET letter_decided_by=?, letter_decided_at=date('now','-3 days') WHERE id=?",
              ("Directeur des études", r3))

    # Stagiaire recommandé partiel (institution étatique) : lettre en attente d'approbation
    r4 = register("Solange Kabeya", "F", "Bureautique Word", "recommande_partiel", institution="Ministère de l'Emploi",
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
        "VALUES (?,?,?,?,?,?)",
        (fil_ids["Bureautique Word"], fid, "Bureautique Word - groupe A", "08:30", 15, "12:30")).lastrowid
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
