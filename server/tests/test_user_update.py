import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.main import app, get_engine, get_password_hash
from app.models import Base, User

# Configuración de base de datos de prueba
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

from sqlalchemy.pool import StaticPool

@pytest.fixture(name="client")
def client_fixture():
    # Parchear engine en main
    from app import main
    
    # Crear engine en memoria con StaticPool para compartir conexión
    test_engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(test_engine)
    
    # Guardar engine original
    original_engine = main.engine
    main.engine = test_engine
    
    # Reiniciar app para asegurar que use el nuevo engine si fuera necesario (aunque main.engine es global)
    # Pero cuidado, si app ya se instanció, las rutas ya están definidas.
    # Afortunadamente, las rutas usan 'with Session(engine)' accediendo a la variable global 'engine'.
    
    with TestClient(app) as client:
        yield client
    
    # Restaurar
    main.engine = original_engine
    test_engine.dispose()

@pytest.fixture(name="session")
def session_fixture(client):
    # Usar el mismo engine que tiene client (que es main.engine ahora)
    from app import main
    with Session(main.engine) as session:
        yield session

def test_create_user_with_alerts(client, session):
    # 1. Crear admin para autenticarse (simulado)
    # En main.py, require_admin busca un token en la DB.
    # Insertamos un usuario y una sesión válida.
    from app.models import UserSession
    import uuid
    
    admin_pass = get_password_hash("admin123")
    admin = User(email="admin@test.com", password_hash=admin_pass, is_admin=True)
    session.add(admin)
    session.commit()
    
    token = "test-token-admin"
    user_session = UserSession(token=token, user_id=admin.id)
    session.add(user_session)
    session.commit()
    
    headers = {"x-dashboard-token": token}
    
    # 2. Crear usuario con receive_alerts=True
    payload = {
        "email": "newuser@test.com",
        "password": "password123",
        "name": "New User",
        "is_admin": False,
        "receive_alerts": True
    }
    
    response = client.post("/api/admin/users", json=payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert data["receive_alerts"] is True # Verificar que se guardó True
    
    # Verificar en DB
    u = session.execute(select(User).where(User.email == "newuser@test.com")).scalar_one()
    assert u.receive_alerts is True

def test_update_user_alerts(client, session):
    # Setup admin
    from app.models import UserSession
    admin_pass = get_password_hash("admin123")
    admin = User(email="admin@test.com", password_hash=admin_pass, is_admin=True)
    session.add(admin)
    session.commit()
    token = "test-token-admin"
    session.add(UserSession(token=token, user_id=admin.id))
    
    # Crear usuario sin alertas
    user = User(email="user@test.com", password_hash=admin_pass, receive_alerts=False)
    session.add(user)
    session.commit()
    
    headers = {"x-dashboard-token": token}
    
    # Actualizar a True
    response = client.put(f"/api/admin/users/{user.id}", json={"receive_alerts": True}, headers=headers)
    assert response.status_code == 200
    assert response.json()["receive_alerts"] is True
    
    # Verificar persistencia
    session.refresh(user)
    assert user.receive_alerts is True
