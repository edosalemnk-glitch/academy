"""Outils d'administration.

  python manage.py reset                          Efface la base et recrée les données de démonstration
  python manage.py add-formateur "Nom" e@mail.cd  Ajoute un compte formateur (mot de passe demandé)
  python manage.py add-secretaire "Nom" e@mail.cd Ajoute un compte secrétariat/réception (mot de passe demandé)
"""
import getpass
import os
import sys


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "reset":
        import db
        if input("Cela efface TOUTES les données. Tapez « oui » pour confirmer : ").strip().lower() != "oui":
            print("Annulé.")
            return
        if os.path.exists(db.DB_PATH):
            os.remove(db.DB_PATH)
        import app  # noqa: F401  (recrée la base et les données de démonstration)
        print("Base réinitialisée avec les données de démonstration.")
    elif cmd in ("add-formateur", "add-secretaire") and len(sys.argv) == 4:
        import app
        from werkzeug.security import generate_password_hash
        role = "formateur" if cmd == "add-formateur" else "secretaire"
        label = "Formateur" if role == "formateur" else "Secrétaire"
        name, email = sys.argv[2], sys.argv[3].lower()
        pwd = getpass.getpass("Mot de passe (8 caractères minimum) : ")
        if len(pwd) < 8:
            sys.exit("Mot de passe trop court.")
        conn = app.database.connect()
        try:
            conn.execute("INSERT INTO users (full_name,email,password_hash,role) VALUES (?,?,?,?)",
                         (name, email, generate_password_hash(pwd), role))
            conn.commit()
            print(f"{label} créé : {email}")
        except Exception as exc:
            sys.exit(f"Erreur : {exc}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
