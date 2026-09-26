# Ce que tu dois faire — résumé

## Étape 1 — Réparer Python sur ton PC (5 à 10 minutes)

Ton Python actuel (version Microsoft Store) est cassé : il ne trouve plus sa bibliothèque standard (`importlib`, `sqlite3` introuvables). Le projet n'y est pour rien.

1. **Paramètres → Applications → Applications installées** : désinstalle « Python 3.13 ».
2. **Paramètres → Applications → Paramètres avancés des applications → Alias d'exécution d'application** : désactive `python.exe` et `python3.exe`.
3. Télécharge Python sur **python.org/downloads** (Windows, 64 bits).
4. Pendant l'installation, **coche « Add python.exe to PATH »**, puis Install.
5. Ferme et rouvre l'invite de commandes. Vérifie : `python --version`.

## Étape 2 — Lancer la plateforme

1. Dézippe le fichier zip fourni.
2. **Double-clique sur `lancer.bat`** (il crée l'environnement, installe Flask et démarre le serveur).
3. Ouvre **http://127.0.0.1:5000** dans le navigateur.

Sans le fichier `.bat` : `python -m venv .venv`, puis `.venv\Scripts\activate`, `pip install -r requirements.txt`, `python app.py`.

## Étape 3 — Comptes de démonstration

| Rôle | E-mail | Mot de passe |
|---|---|---|
| Formateur | `formateur@inpp.cd` | `Formateur2026!` |
| Secrétariat (réception) | `secretariat@inpp.cd` | `Secretariat2026!` |
| 10 stagiaires | `stagiaire01@inpp.cd` … `stagiaire10@inpp.cd` | `Stagiaire2026!` |

Données préchargées : 3 cours (SQL Niveau 1, SQL Niveau 2, Bureautique), 13 leçons, 33 questions de quiz, un **examen final de démonstration sur SQL Niveau 2** (4 questions, publié), des inscriptions validées / en attente / refusées, des progressions simulées (un stagiaire certifié, un bloqué), 3 filières du centre (Informatique de gestion, Électricité du bâtiment, Coupe et couture) et 4 stagiaires inscrits au secrétariat (un en ordre avec carte délivrée, un en attente de paiement, un recommandé total déjà approuvé, un recommandé partiel en attente d'approbation de sa lettre).

## Étape 3 bis-bis — Tester la vitrine publique et l'examen final

1. Dans une fenêtre privée (sans connexion), ouvre **http://127.0.0.1:5000** : c'est la nouvelle page d'accueil publique. Parcours *Filières*, *À propos*, *FAQ*, *Contact* dans le pied de page.
2. Connecte-toi avec `formateur@inpp.cd` → *SQL Niveau 2 → Gérer le cours* : la section **Examen final** en bas de page montre l'examen déjà configuré (4 questions, publié). Clique *Modifier* pour voir les réglages (durée, seuil, tentatives, créneau), ou *Résultats* pour la liste des tentatives.
3. Connecte-toi avec `stagiaire01@inpp.cd` (déjà validée sur SQL Niveau 2, mais leçons pas toutes terminées dans le seed) → termine les 4 leçons de SQL Niveau 2 → un bouton **Passer l'examen final** apparaît sur la page du cours. Lance-le : chrono visible, soumission automatique à zéro. En réussissant, une attestation provisoire de réussite est délivrée automatiquement (visible depuis la page de résultat).

## Étape 3 bis — Tester le secrétariat (inscription au centre)

1. Connectez-vous avec `secretariat@inpp.cd`.
2. *Nouvelle inscription* : enregistrez un stagiaire (choisissez son type — non recommandé / recommandé total / recommandé partiel — et sa filière).
3. Ouvrez sa fiche : enregistrez le paiement des frais d'inscription, puis du matériel (avec la référence du bordereau **FN BANK**). Dès qu'il est en ordre, sa carte de stagiaire est délivrée automatiquement.
4. Pour un stagiaire recommandé : approuvez d'abord sa lettre de recommandation (nom et fonction de la personne de la hiérarchie) avant de pouvoir enregistrer ses paiements.
5. *Registre* : filtrez entre stagiaires directs et apprenants d'autres institutions, exportez en CSV.
6. *Jury* : consultez qui est autorisé à passer le jury (frais réglés) et qui ne l'est pas encore.
7. *Tarifs* : ajustez les frais généraux et les frais matériel par filière (s'applique aux prochaines inscriptions).

## Étape 3 ter — Tester le module Présences (carte QR, pointage)

1. Connectez-vous avec `formateur@inpp.cd`, ouvrez *Présences* : une section de démonstration existe déjà
   (« Informatique de gestion - groupe A », 8h30 + 15 min, fin 12h30) avec 4 stagiaires.
2. Ouvrez la section : vous voyez la grille des cartes, avec le statut du jour de chacun (déjà pointés pour
   la démonstration). Testez *Poser* un statut malade/permission/absent sur un stagiaire.
3. Ouvrez *Pointage* : deux façons de tester —
   - **Caméra** : cliquez *Activer la caméra*, autorisez l'accès si le navigateur le demande, puis présentez à l'écran le QR code d'une carte (ouvrez la carte d'un stagiaire dans un autre onglet, ou imprimez-la) : le pointage se fait automatiquement dès que le code est lu, sans rien taper.
   - **Manuel** : copiez le numéro de carte d'un stagiaire (visible dans la grille) dans le champ, appuyez sur Entrée — le système pointe automatiquement présent ou en retard selon l'heure. C'est ce même champ qu'un lecteur de QR code physique remplirait en scannant la carte.
4. Ouvrez *Messages* : un message de retard est déjà en attente ; choisissez un statut et cliquez *Poser*.
5. Ouvrez la carte d'un stagiaire (*Secrétariat → un stagiaire en ordre → Voir la carte*) : le QR code y figure.
   Scannez-le avec un téléphone (ou ouvrez `/carte/<code>`) : la page publique propose *Signaler une absence
   ou un retard*, accessible sans connexion.
6. **Secrétariat** : dans *Tarifs*, la section *Services* permet de créer un service, lui désigner un chef
   (un formateur), et de rattacher une filière à un service.

## Étape 3 ter — Vitrine des formations programmées

1. Sans connexion, ouvre **Catalogue** : par défaut, les sessions **à venir** sont affichées avec date de début/fin, horaires, lieu et capacité.
2. Utilise les filtres **Recherche, Domaine, Niveau, Période et Mois de début**.
3. Clique **Télécharger le programme PDF** : le PDF reprend les filtres actifs et les sessions visibles.
4. Ouvre une formation puis **Créer un compte et s'inscrire** : le visiteur crée son compte stagiaire et la demande d'inscription est envoyée automatiquement au formateur.
5. Côté formateur : *Cours → Modifier* permet maintenant de programmer une session (dates, horaires, lieu, places et ouverture des inscriptions).
6. Les sessions d'exemple sont préchargées pour octobre–décembre 2026 afin de tester immédiatement la vitrine.

## Étape 4 — Test en 10 minutes (à faire avant la présentation)

1. **Formateur** : connecte-toi, regarde le tableau de bord (alerte « Stagiaires en difficulté »), puis *SQL Niveau 1 → Inscriptions* : **valide** les demandes de Héritier Banza et Isaac Ngoy.
2. Ouvre *Suivi des stagiaires* : matrice leçons × stagiaires, frais, export CSV.
3. **Stagiaire** (fenêtre privée du navigateur) : connecte-toi avec `stagiaire07@inpp.cd`, ouvre SQL Niveau 1. La leçon 2 est verrouillée.
4. Fais la leçon 1, rate volontairement le quiz (aucune correction), refais-le et réussis : la leçon 2 se débloque.
5. Va dans **Terrain SQL** et résous un défi.
6. Reviens côté formateur : le suivi montre la progression et les échecs en direct.
7. Crée un compte depuis la page d'accueil (visiteur), abonne-toi à « SQL Niveau 2 » : la demande arrive chez le formateur.

## Étape 5 — Préparer la présentation au DG

- Le document **`Dossier_Projet_INPP_Academie.docx`** contient la description complète du projet (contexte, fonctionnalités, anti-fraude, comparaison avec NetAcad, feuille de route, risques, décisions demandées).
- Imprime-le, ou envoie-le à l'avance.
- Prépare la démonstration en direct (étape 4) : 10 minutes suffisent. Lance la plateforme **avant** d'entrer en salle et garde `lancer.bat` ouvert.
- Sois clair sur l'état actuel : c'est un **prototype fonctionnel** (pilote), pas encore un service ouvert au public. Le dossier explique ce qu'il reste à faire pour y arriver.

## Utilisation courante côté formateur

- **Créer des comptes en lot** : menu *Stagiaires* → une ligne par stagiaire (`Nom ; e-mail`). Les mots de passe temporaires s'affichent une seule fois, à imprimer.
- **Valider une inscription** : *Cours → Inscriptions → Valider*. Un abonné non validé n'accède à aucune leçon.
- **Suivre les frais** : sur la même page, marque Payé / Non payé / Exonéré. Pour **bloquer l'accès** aux impayés : lance le serveur avec `set INPP_ENFORCE_FEES=1` avant `python app.py`.
- **Ajouter un cours** : *Nouveau cours* → leçons → questions du quiz (4 réponses, 1 correcte).

## Commandes utiles

- `python manage.py reset` : efface tout et remet les données de démonstration.
- `python manage.py add-formateur "Nom" e-mail` : ajoute un autre formateur.
- `python tests/smoke_test.py` : vérifie que toute la plateforme fonctionne (44 contrôles).

## Avant de l'ouvrir à de vrais stagiaires

À faire (détaillé dans le dossier) : hébergement avec HTTPS, sauvegardes automatiques de `formation.db`, changement des mots de passe de démonstration, récupération de mot de passe par e-mail, rôle administrateur, paiement en ligne.


## Ressources de révision

Le site distingue désormais clairement la **formation en présentiel à l'INPP Matadi** et l'accompagnement numérique :

- les visiteurs consultent les filières, services, sessions programmées, dates, frais et procédure ;
- les stagiaires validés disposent d'un espace **Ressources** ;
- les formateurs peuvent publier des supports de révision, exercices pratiques, documents, liens et fichiers depuis la gestion de chaque formation ;
- les ressources sont stockées dans Supabase Storage lorsque le stockage est configuré ;
- les quiz et l'examen final restent des outils d'évaluation/accompagnement, pas une présentation de l'INPP comme école entièrement en ligne.
