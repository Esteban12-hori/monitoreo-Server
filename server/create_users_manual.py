import sys
import os

# Agregar el directorio actual al path para poder importar app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.main import Session, engine, User, get_password_hash
from sqlalchemy import select

def create_admin(email, password, name):
    try:
        with Session(engine) as session:
            user = session.execute(select(User).where(User.email == email)).scalars().first()
            if user:
                print(f"Usuario {email} ya existe. Actualizando contraseña...")
                user.password_hash = get_password_hash(password)
                user.is_admin = True
            else:
                print(f"Creando usuario {email}...")
                user = User(
                    email=email,
                    name=name,
                    password_hash=get_password_hash(password),
                    is_admin=True
                )
                session.add(user)
            session.commit()
            print(f"Usuario {email} configurado correctamente.")
    except Exception as e:
        print(f"Error configurando {email}: {e}")

if __name__ == "__main__":
    print("Iniciando creación manual de usuarios...")
    create_admin("rlarenas@wingsoft.com", "q0<>E55NV", "Ramiro Larenas")
    create_admin("jguajardo@wingsoft.com", "Pombolita1", "Joaquín Guajardo")
    print("Finalizado.")
