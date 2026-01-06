import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import get_engine, ensure_default_users, get_current_user_from_token
from app.models import User
from sqlalchemy.orm import Session
from sqlalchemy import select

def test_users_update():
    engine = get_engine()
    with Session(engine) as sess:
        ensure_default_users(sess)
        
        # Check for jguajardo
        user = sess.execute(select(User).where(User.email == "jguajardo@wingsoft.com")).scalar_one_or_none()
        if user:
            print(f"User found: {user.email}, Admin: {user.is_admin}")
            # We can't easily decrypt bcrypt, but we know ensure_default_users checks it.
        else:
            print("User NOT found!")

if __name__ == "__main__":
    test_users_update()
