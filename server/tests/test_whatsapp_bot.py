import pytest

from app.main import handle_whatsapp_conversation, _wa_reset_session


def test_whatsapp_initial_greeting_requests_email():
    wa_id = "test-user-1"
    _wa_reset_session(wa_id)
    replies = handle_whatsapp_conversation(wa_id, "hola")
    joined = "\n".join(replies).lower()
    assert "correo" in joined


def test_whatsapp_asks_password_after_email():
    wa_id = "test-user-2"
    _wa_reset_session(wa_id)
    handle_whatsapp_conversation(wa_id, "hola")
    replies = handle_whatsapp_conversation(wa_id, "user@test.com")
    joined = "\n".join(replies).lower()
    assert "contraseña" in joined

