# INPP Académie (v3)

Plateforme de formation en ligne : **vitrine publique** (filières, procédure, FAQ, référencement), catalogue, abonnement, validation par le formateur, parcours verrouillé par quiz, **examen final chronométré**, certificat vérifiable, terrain d'entraînement SQL — et module Secrétariat / Réception pour l'inscription physique au centre (frais, types de stagiaires, lettres de recommandation, carte de stagiaire avec **scanner caméra**).

Démarrage : voir **ACTIONS.md** (double-clic sur `lancer.bat` sous Windows).

## Technique

- Python 3.10+ · Flask · SQLite (fichier `formation.db`, créé au premier lancement). Aucune connexion Internet requise pour fonctionner.
- `app.py` : routes · `db.py` : schéma · `seed.py` : démonstration · `sqllab.py` : terrain SQL en lecture seule · `utils.py` : rendu des leçons · `fees.py` : règles de frais et de situation financière du secrétariat.
- Variables d'environnement : `SECRET_KEY`, `PORT`, `INPP_HOST` (`0.0.0.0` pour ouvrir au réseau local), `INPP_DB`, `INPP_ENFORCE_FEES=1`, `INPP_DEBUG=1`.

## Module Secrétariat / Réception (inscription au centre)

Un troisième rôle, **secrétaire**, gère l'inscription physique décrite dans le cahier des charges (`projet.md`), séparément du catalogue de formations en ligne :

- **Frais** : inscription (40 000 Fc, obligatoire), matériel (40 $ / 50 $ / 80 $ selon la filière), formation (50 000 Fc/mois), jury (25 000 Fc, obligatoire avant de passer le jury). Modifiables par le secrétariat dans *Tarifs* ; une modification ne s'applique qu'aux futures inscriptions.
- **Types de stagiaires** : Non recommandé (paie tout), Recommandé total — institution privée (ne paie rien), Recommandé partiel — institution étatique (paie matériel + jury). Un stagiaire recommandé doit avoir sa lettre approuvée par la hiérarchie (nom et fonction de la personne, horodaté) avant de pouvoir payer et avant d'être considéré « en ordre ».
- **Registre** : liste filtrable (registre principal des stagiaires directs / registre des apprenants d'autres institutions), export CSV, situation financière calculée automatiquement à partir des paiements.
- **Carte de stagiaire** : délivrée automatiquement dès que le stagiaire est en ordre avec les frais ; vérifiable publiquement à `/carte/<code>`.
- **Jury** : liste des stagiaires autorisés (frais de jury réglés et lettre approuvée le cas échéant) et de ceux qui ne le sont pas encore, avec le motif.
- Chaque paiement enregistre la référence de la preuve de paiement (bordereau **FN BANK**) et peut être annulé (conservé dans l'historique, jamais supprimé).

Ce module est indépendant du catalogue de cours en ligne : un compte secrétaire n'a pas accès à l'espace formateur, et réciproquement.

## Vitrine publique (visibilité sur Internet)

Séparée de l'espace connecté, une vitrine accessible sans compte donne à l'INPP une présence sur le web :

- **Accueil** (`/`) : présentation du fonctionnement hybride — présentiel obligatoire pour la formation, site pour s'informer, s'entraîner et passer l'examen.
- **Filières** (`/filieres`), **À propos** (`/a-propos`), **FAQ** (`/faq`), **Contact** (`/contact`) : contenu public, à compléter (adresse, téléphone) avant mise en ligne réelle.
- **Catalogue** (déjà existant) et **procédure d'inscription** restent accessibles depuis la vitrine.
- **Référencement** : `robots.txt` et `sitemap.xml` générés automatiquement ; chaque page publique a sa propre balise `<meta name="description">`.

## Examen final (distinct des quiz de leçon)

Un cours en ligne peut avoir, en plus des quiz de chaque leçon, un **examen final** unique, géré par le formateur depuis *Gérer le cours* :

- **Configuration** : titre, durée (minutes), seuil de réussite, nombre de tentatives autorisées, créneau d'ouverture/fermeture optionnel (pour le faire coïncider avec une séance en salle), publication.
- **Questions** : à choix multiple, comme les quiz de leçon ; ordre et réponses mélangés à chaque tentative.
- **Passage** : accessible au stagiaire uniquement après avoir terminé toutes les leçons du cours et pendant le créneau ouvert. Chronomètre côté navigateur avec **soumission automatique** à l'échéance ; toute tentative rouverte après le délai est corrigée automatiquement (hors délai = non validé), pour éviter qu'une tentative reste ouverte indéfiniment.
- **Certificat** : si un examen publié existe pour le cours, le certificat n'est délivré qu'après réussite des leçons **et** de l'examen (sinon, comme avant, la réussite des leçons suffit).
- **Résultats** : liste des tentatives par stagiaire, consultable par le formateur.

## Module Présences (carte QR, pointage, absences)

- **Organisation** : à l'INPP, les formations sont regroupées en **filières**, elles-mêmes rattachées à un **service** (ex. Service Informatique, Service Électronique). Chaque service a un **chef de service**, qui est aussi formateur. Le secrétariat gère les services et le rattachement des filières dans *Tarifs*.
- **Sections** : un formateur crée ses propres **sections** (*Présences → Nouvelle section*) : nom, filière, heure de début (par défaut 8h30), tolérance avant retard (par défaut 15 min), heure de fin. Chaque formateur ne voit que ses sections et la grille des cartes de ses stagiaires.
- **Carte QR** : la carte de stagiaire délivrée par le secrétariat porte désormais un QR code (vérifiable publiquement à `/carte/<code>`, comme avant).
- **Pointage** : sur l'écran *Pointage* d'une section (à ouvrir sur l'appareil placé à l'entrée), deux façons de pointer : **la caméra de l'appareil** (bouton *Activer la caméra*, lecture du QR en direct grâce à la bibliothèque jsQR embarquée — aucune connexion Internet requise) ou la **saisie du code à la main** dans le même champ (utile aussi avec un lecteur QR physique USB/Bluetooth, qui « tape » le code comme un clavier). Dans les deux cas, le système pointe automatiquement **présent** (dans la tolérance) ou **en retard** (au-delà).
- **Statuts manuels** : dans la grille de la section, le formateur peut poser à la main **malade**, **permission**, **absent**, ou corriger présent/retard, pour n'importe quel jour.
- **Messages des stagiaires** : depuis sa carte (`/carte/<code>/signaler`, sans connexion), un stagiaire peut prévenir son formateur d'une absence ou d'un retard prévu, avec la date et la raison. Le formateur voit la liste (*Présences → Messages*) et pose lui-même le statut correspondant.

## Sécurité déjà en place

Mots de passe hachés · jeton CSRF sur tous les formulaires · verrouillage après 5 échecs de connexion · cloisonnement formateur / stagiaire (un formateur ne modifie que ses cours) · quiz corrigés côté serveur · ordre des questions et réponses aléatoire · terrain SQL isolé (base en mémoire, SELECT uniquement, délai limité).

## Mise en ligne (production)

Le serveur lancé par `python app.py` (ou `lancer.bat`) est un serveur de **développement** : une requête à la fois, pas fait pour être exposé directement sur Internet. Pour une vraie mise en ligne :

1. **Serveur WSGI** : installez les dépendances (`pip install -r requirements.txt`, qui inclut désormais `waitress`), puis lancez `waitress-serve --host=127.0.0.1 --port=8000 wsgi:app`. `wsgi.py` est le point d'entrée fourni à cet effet.
2. **HTTPS** : placez un reverse proxy (nginx, Caddy, ou IIS sous Windows) devant, avec un certificat (Let's Encrypt via Caddy est le plus simple), qui redirige vers `127.0.0.1:8000`. Ne jamais exposer le port 8000 directement sans HTTPS : mots de passe et cookies de session transiteraient en clair.
3. **Variables d'environnement** : définissez une vraie valeur secrète et aléatoire pour `SECRET_KEY` (`python -c "import secrets; print(secrets.token_hex(32))"`), et `INPP_ENFORCE_FEES=1` pour activer les règles de frais en production.
4. **Mots de passe de démonstration** : changez les mots de passe créés par `seed.py` (ou ne lancez pas le seed en production — voir `manage.py` pour créer de vrais comptes formateur/secrétaire).
5. **Sauvegardes** : `formation.db` est un simple fichier SQLite ; programmez une copie régulière (tâche planifiée / cron) vers un autre disque ou un stockage externe.
6. **Contenu de la vitrine** : complétez la page `/contact` (adresse, téléphone, e-mail, horaires réels) avant la mise en ligne — les champs sont volontairement laissés en `[à compléter]`.

## Limites connues

Pas de récupération de mot de passe par e-mail · pas de rôle administrateur (les formateurs supplémentaires se créent avec `manage.py`) · pas de paiement en ligne (suivi manuel des frais) · pas de vidéo hébergée · SQLite convient à quelques centaines d'utilisateurs, au-delà prévoir PostgreSQL · le scanner caméra du pointage demande un navigateur récent avec accès à la caméra (Chrome, Firefox, Safari mobiles récents) — la saisie manuelle ou un lecteur QR physique restent disponibles en secours.
