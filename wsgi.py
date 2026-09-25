"""Point d'entrée WSGI pour un vrai serveur de production.

Le serveur de développement Flask (celui lancé par `python app.py`) n'est pas fait pour être
exposé sur Internet : une seule requête à la fois, pas de durcissement contre les usages
malveillants. Pour la mise en ligne réelle, utilisez ce fichier avec un serveur WSGI, par
exemple waitress (inclus dans requirements.txt, fonctionne aussi sous Windows) :

    waitress-serve --host=0.0.0.0 --port=8000 wsgi:app

Placez ensuite un reverse proxy (nginx, Caddy, IIS...) devant, avec un certificat HTTPS,
et pointez-le vers 127.0.0.1:8000. Voir la section "Mise en ligne" de README.md.
"""
from app import app

if __name__ == "__main__":
    app.run()
