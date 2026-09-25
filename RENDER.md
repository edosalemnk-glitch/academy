# Déploiement sur Render

Le dépôt est préparé pour Render avec un service Web Python.

## Configuration

Le fichier `render.yaml` configure :

- Python + Gunicorn avec `wsgi:app`
- une clé `SECRET_KEY` générée par Render
- SQLite sur un disque persistant monté dans `/var/data`
- `INPP_DB=/var/data/formation.db`
- `SEO_BASE_URL` à renseigner avec l'URL publique du service

## Mise en ligne

1. Dans Render, créez un nouveau **Blueprint** depuis ce dépôt GitHub.
2. Render détectera `render.yaml`.
3. Validez la création du service.
4. Après création, renseignez `SEO_BASE_URL` avec l'URL HTTPS publique, par exemple `https://inpp-academie.onrender.com`.
5. Déployez.

## Données

La base SQLite est placée sur le disque persistant Render. Les fichiers téléversés dans `static/uploads` ne sont pas encore déplacés sur ce disque : si l'application stocke des fichiers importants, il faudra ensuite externaliser ces uploads (ou les déplacer vers le disque persistant).

## Sécurité

Ne mettez pas la valeur réelle de `SECRET_KEY` dans GitHub. Render la génère automatiquement via `generateValue: true`.

Le fichier local `secret.key` est maintenant ignoré par Git.
