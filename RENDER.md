# Déploiement Render — INPP Académie

Le projet est configuré pour un **Web Service Render Free** avec **PostgreSQL Supabase** comme base de données principale.

## 1. Créer le Web Service

Dans Render :
1. **New → Web Service**
2. Sélectionner `edosalemnk-glitch/academy`
3. Branche : `main`
4. Root Directory : vide
5. Runtime : Python 3
6. Build Command : `pip install -r requirements.txt`
7. Start Command : `gunicorn --bind 0.0.0.0:$PORT wsgi:app`
8. Compute : **Free** pour les essais.

## 2. Supabase PostgreSQL

Créer un projet PostgreSQL sur Supabase, puis ouvrir **Connect**.
Pour Render, utiliser de préférence la chaîne de connexion PostgreSQL fournie par Supabase, idéalement le **Session pooler** si la connexion directe n'est pas accessible depuis l'environnement IPv4.

Dans Render → **Environment Variables**, ajouter :
- `DATABASE_URL` = chaîne PostgreSQL Supabase
- `SECRET_KEY` = **Generate**
- `INPP_ENFORCE_FEES` = `0`
- `SEO_BASE_URL` = URL publique Render, par exemple `https://inpp-academie.onrender.com`

Ne jamais enregistrer `DATABASE_URL` dans GitHub.

## 3. Base de données

L'application principale n'utilise plus SQLite pour ses données métier : elle se connecte à PostgreSQL via `DATABASE_URL`.
Le fichier `db.py` conserve une petite couche de compatibilité pour les requêtes historiques (`?`, dates SQLite et `lastrowid`) afin d'éviter de réécrire toutes les routes Flask.
Le **Terrain SQL pédagogique** (`sqllab.py`) reste volontairement en SQLite en mémoire : c'est une base d'exemple isolée utilisée uniquement pour les exercices SQL et elle n'est pas la base de production.

## 4. Fichiers téléversés

Le plan Free de Render possède un système de fichiers éphémère. Les fichiers placés localement dans `static/uploads/` peuvent donc être perdus lors d'un redémarrage, d'un redéploiement ou d'une mise en veille.
Pour les documents/images de production, une prochaine étape recommandée est de migrer les uploads vers **Supabase Storage**.

## 5. Secret

`secret.key` ne doit pas être remis dans GitHub. En production, Render génère `SECRET_KEY`.

## 6. Vérification après déploiement

Tester : page d'accueil ; inscription / connexion ; catalogue ; création d'un cours ; inscription d'un stagiaire ; secrétariat ; présences ; examens ; certificats ; persistance des données après redéploiement.
