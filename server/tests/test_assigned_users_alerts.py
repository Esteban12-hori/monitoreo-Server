
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.models import Base, Server, User, AlertRecipient, AlertRule, UserServerLink
from app.main import get_alert_recipients

# Use in-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture
def session():
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as sess:
        yield sess
    Base.metadata.drop_all(bind=engine)

def test_assigned_user_receives_alerts_default(session):
    """Test that by default (link.receive_alerts=True), assigned user gets alerts."""
    # 1. Create Server
    srv = Server(server_id="server-1", token="abc")
    session.add(srv)
    
    # 2. Create User (Global flag shouldn't matter now, but let's set it False to prove override)
    user = User(email="user@example.com", name="Test User", password_hash="hash", is_admin=False, receive_alerts=False)
    session.add(user)
    session.commit()
    
    session.refresh(srv)
    session.refresh(user)
    
    # 3. Assign User to Server (Implicitly creates link with default True)
    # Since 'servers' relationship is now viewonly=True, we must use UserServerLink explicitly
    link = UserServerLink(user=user, server=srv)
    session.add(link)
    session.commit()
    
    # 4. Verify recipients
    session.refresh(srv)
    recipients, rules = get_alert_recipients(session, srv, "cpu")
    
    assert "user@example.com" in recipients

def test_assigned_user_disabled_alerts(session):
    """Test that if link.receive_alerts is False, user does NOT get alerts."""
    # 1. Create Server
    srv = Server(server_id="server-2", token="abc")
    session.add(srv)
    
    # 2. Create User
    user = User(email="quiet@example.com", name="Quiet User", password_hash="hash", is_admin=False, receive_alerts=True)
    session.add(user)
    session.commit()
    
    session.refresh(srv)
    session.refresh(user)
    
    # 3. Assign User to Server manually via Link to set receive_alerts=False
    link = UserServerLink(user_id=user.id, server_id=srv.id, receive_alerts=False)
    session.add(link)
    session.commit()
    
    # 4. Verify recipients
    session.refresh(srv)
    recipients, rules = get_alert_recipients(session, srv, "cpu")
    
    assert "quiet@example.com" not in recipients

def test_global_recipients_mixed_with_assigned(session):
    # 1. Global recipient
    global_r = AlertRecipient(email="admin@example.com", name="Admin")
    session.add(global_r)
    
    # 2. Server and Assigned User
    srv = Server(server_id="server-3", token="abc")
    user = User(email="user@example.com", name="User", password_hash="hash", receive_alerts=True)
    session.add(srv)
    session.add(user)
    session.commit()
    
    session.refresh(srv)
    session.refresh(user)
    
    link = UserServerLink(user=user, server=srv)
    session.add(link)
    session.commit()
    
    # 3. Verify both are present
    session.refresh(srv)
    recipients, rules = get_alert_recipients(session, srv, "disk")
    
    assert "admin@example.com" in recipients
    assert "user@example.com" in recipients
