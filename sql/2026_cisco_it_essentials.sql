-- Ajoute le cours "Académie Cisco : IT Essentials" (déjà appliqué en direct sur le
-- projet Supabase "inpp-academie", id qyxzdmruhxmltrrmmvyj). Ce script sert à
-- reproduire la même donnée sur un autre environnement (staging, autre base).
-- Adapter trainer_id / service_id si différents chez vous
-- (ici : trainer_id=13 = formateur@inpp.cd, service_id=91 = Service Informatique).

WITH c AS (
  INSERT INTO courses (title, category, level, description, case_study, fee_amount,
    currency, pass_mark, published, start_date, end_date, schedule, location, seats,
    registration_open, trainer_id, service_id)
  VALUES (
    'Académie Cisco : IT Essentials',
    'Réseaux et maintenance',
    'Débutant',
    'Bases du matériel informatique, assemblage sécurisé d''un poste et notions de réseau, pour aborder sereinement la maintenance des micro-ordinateurs.',
    'Vous êtes technicien informatique stagiaire au service Informatique de l''INPP Matadi. Le secrétariat signale qu''un poste de travail refuse de démarrer et qu''un autre doit être remis en état avant la rentrée des inscriptions. Votre mission : diagnostiquer une panne matérielle simple, vérifier les composants internes, remettre le poste en service et rédiger une fiche d''intervention claire pour le formateur responsable.',
    0, 'USD', 70, 1, '2026-11-16', '2027-02-16', 'Lundi–Vendredi · 08h30–12h30', 'INPP Matadi', 25, 1, 13, 91
  ) RETURNING id
), l1 AS (
  INSERT INTO lessons (course_id, position, title, content)
  SELECT id, 1, 'Découvrir les composants d''un ordinateur', $$## Les grandes familles de composants

Un ordinateur de bureau se construit autour de quelques éléments : la **carte mère**, qui relie tout le reste ; le **processeur (CPU)**, qui exécute les calculs ; la **mémoire vive (RAM)**, qui stocke les données en cours d'utilisation ; le **disque de stockage** (SSD ou disque dur), qui garde les fichiers de façon permanente ; et le **bloc d'alimentation**, qui fournit l'électricité à l'ensemble.

- La RAM se vide dès que l'ordinateur s'éteint : c'est une mémoire volatile.
- Le disque de stockage garde les données même hors tension.
- Le CPU chauffe : un dissipateur et un ventilateur l'accompagnent presque toujours.

> Avant d'ouvrir un boîtier, coupez toujours l'alimentation et débranchez le câble secteur.

## Les périphériques courants

Clavier, souris, écran, imprimante : ce sont des **périphériques**, reliés à l'ordinateur par des ports (USB, HDMI, Ethernet...). Chaque port a une forme et un usage précis.$$
  FROM c RETURNING id
), l2 AS (
  INSERT INTO lessons (course_id, position, title, content)
  SELECT id, 2, 'Assembler et sécuriser un poste de travail', $$## Manipuler le matériel sans risque

L'électricité statique de votre corps peut endommager des composants sensibles comme la RAM ou une carte réseau. Avant de toucher l'intérieur d'un boîtier :

- touchez une partie métallique non peinte du châssis pour vous décharger ;
- évitez de travailler sur un tapis ou en vêtements synthétiques par temps sec ;
- manipulez les cartes par les bords, jamais par les contacts dorés.

## Remonter un poste étape par étape

1. Fixez la carte mère dans le boîtier avec les entretoises prévues.
2. Installez le processeur en respectant le détrompeur (encoche) du socket, puis le dissipateur.
3. Enfoncez les barrettes de RAM dans leurs slots jusqu'au clic des loquets.
4. Branchez l'alimentation à la carte mère et aux disques.
5. Refermez le boîtier et rebranchez les périphériques avant de remettre sous tension.

> Un poste qui ne démarre pas après un remontage a souvent une connexion mal enfoncée : RAM, câble d'alimentation ou câble de disque. Vérifiez-les avant de conclure à une panne grave.$$
  FROM c RETURNING id
), l3 AS (
  INSERT INTO lessons (course_id, position, title, content)
  SELECT id, 3, 'Notions de base des réseaux et dépannage', $$## Comment les postes communiquent

Un réseau local relie plusieurs ordinateurs entre eux, souvent via un **switch** ou une **box**. Chaque poste reçoit une **adresse IP**, son identifiant sur le réseau. Deux formats fréquents :

- une adresse fixe, configurée manuellement ;
- une adresse automatique, distribuée par un serveur **DHCP** (le cas le plus courant sur un petit réseau).

## Une méthode simple de dépannage

Face à un poste qui « n'a plus internet » :

1. Vérifiez le câble ou la connexion Wi-Fi (voyants du port, icône réseau).
2. Vérifiez que l'adresse IP a bien été attribuée (pas de 169.254.x.x, signe d'un échec DHCP).
3. Testez la connexion à un autre appareil sur le même réseau pour isoler la panne (poste, câblage, ou box).
4. Redémarrez l'équipement réseau (box, switch) seulement après avoir écarté une simple erreur de câble.

> Une méthode de dépannage progressive - du plus simple au plus complexe - évite de changer une pièce qui fonctionnait déjà.$$
  FROM c RETURNING id
), q AS (
  INSERT INTO questions (lesson_id, text, option_a, option_b, option_c, option_d, correct, explanation)
  SELECT (SELECT id FROM l1), 'Quel composant exécute les calculs de l''ordinateur ?', 'Le CPU (processeur)', 'La RAM', 'Le disque dur', 'L''alimentation', 'A', 'Le CPU (processeur) est le composant qui exécute les instructions et les calculs.'
  UNION ALL SELECT (SELECT id FROM l1), 'Que se passe-t-il dans la RAM quand l''ordinateur s''éteint ?', 'Les données sont effacées (mémoire volatile)', 'Les données restent stockées', 'Les données sont copiées sur le disque automatiquement', 'Rien, la RAM continue sur batterie', 'A', 'La RAM est une mémoire volatile : son contenu disparaît à l''extinction.'
  UNION ALL SELECT (SELECT id FROM l1), 'Avant d''ouvrir le boîtier d''un ordinateur, il faut d''abord :', 'Couper l''alimentation et débrancher le câble secteur', 'Redémarrer l''ordinateur', 'Augmenter le volume', 'Lancer une mise à jour', 'A', 'Travailler sous tension expose à un risque de choc électrique et de dégât matériel.'
  UNION ALL SELECT (SELECT id FROM l2), 'Pourquoi se décharger d''électricité statique avant de toucher les composants ?', 'Pour éviter d''endommager des composants sensibles', 'Pour accélérer le démarrage', 'Pour économiser l''électricité', 'Ce n''est pas nécessaire', 'A', 'Une décharge électrostatique peut détruire une RAM ou une carte réseau.'
  UNION ALL SELECT (SELECT id FROM l2), 'Comment doit-on tenir une carte d''extension (réseau, graphique...) ?', 'Par les bords, jamais par les contacts dorés', 'Par les contacts dorés uniquement', 'Peu importe', 'Toujours avec un chiffon humide', 'A', 'Toucher les contacts dorés peut les encrasser ou les endommager.'
  UNION ALL SELECT (SELECT id FROM l2), 'Un poste ne démarre plus après un remontage : quelle est la première chose à vérifier ?', 'Les connexions (RAM, alimentation, câbles de disque)', 'La météo', 'Le mot de passe Windows', 'La carte de stagiaire', 'A', 'La majorité des pannes après remontage viennent d''une connexion mal enfoncée.'
  UNION ALL SELECT (SELECT id FROM l3), 'Qu''est-ce qu''une adresse IP ?', 'L''identifiant d''un poste sur le réseau', 'Le nom de l''utilisateur', 'Le numéro de série du disque dur', 'Un mot de passe', 'A', 'L''adresse IP identifie un poste sur son réseau.'
  UNION ALL SELECT (SELECT id FROM l3), 'Une adresse commençant par 169.254.x.x signale généralement :', 'Un échec d''attribution automatique (DHCP)', 'Une connexion très rapide', 'Un antivirus actif', 'Un poste éteint', 'A', 'C''est l''adresse que Windows s''attribue lui-même quand le DHCP ne répond pas.'
  UNION ALL SELECT (SELECT id FROM l3), 'Face à une panne réseau, quelle est la bonne approche ?', 'Vérifier du plus simple (câble, voyants) au plus complexe', 'Redémarrer immédiatement toute la box sans rien vérifier', 'Changer directement la carte réseau', 'Réinstaller Windows', 'A', 'Une méthode progressive évite de changer une pièce qui fonctionnait déjà.'
  RETURNING 1
), r AS (
  INSERT INTO resources (course_id, title, kind, description, content, published, created_by)
  SELECT id, 'Support — Les composants d''un poste de travail', 'support',
    'Récapitulatif illustré des composants internes et de leur rôle.',
    $$# Les composants essentiels

- **Carte mère** : relie tous les composants entre eux.
- **CPU** : exécute les calculs, chauffe, a besoin d'un dissipateur.
- **RAM** : mémoire de travail, se vide à l'extinction.
- **Stockage (SSD/HDD)** : garde les fichiers même hors tension.
- **Alimentation** : convertit le courant secteur pour tous les composants.

# Sécurité avant intervention

1. Éteindre et débrancher le poste.
2. Se décharger de l'électricité statique (toucher le châssis métallique).
3. Manipuler les cartes par les bords.

# À retenir

Un poste qui ne démarre pas après une intervention a très souvent un simple problème de connexion (RAM, câble d'alimentation, câble de disque) plutôt qu'une pièce défectueuse.$$,
    1, 13
  FROM c
  UNION ALL
  SELECT id, 'Travaux pratiques — Diagnostiquer une panne simple', 'exercice',
    'Grille de diagnostic à suivre pas à pas face à un poste en panne.',
    $$# Mise en situation

Un poste du secrétariat ne s'allume plus. Suivez cette grille dans l'ordre, sans sauter d'étape.

# Grille de diagnostic

1. Le câble secteur est-il bien branché des deux côtés (prise et bloc d'alimentation) ?
2. L'interrupteur du bloc d'alimentation (à l'arrière) est-il sur « I » ?
3. Le bouton d'allumage du boîtier est-il bien relié à la carte mère ?
4. En ouvrant le boîtier (poste débranché), la RAM est-elle bien enfoncée dans son slot ?
5. Les câbles d'alimentation internes (carte mère, disque) sont-ils bien enfichés ?

# Rapport d'intervention

Rédigez un court rapport : panne constatée, étapes vérifiées, cause trouvée, solution appliquée. C'est ce document que vous remettriez à votre formateur ou à votre chef de service.$$,
    1, 13
  FROM c
  RETURNING 1
)
SELECT 'ok';
