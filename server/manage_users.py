import sys
import os
import argparse

# Add current directory to path so we can import app
sys.path.append(os.getcwd())

try:
    from app.main import engine
    from app.models import User
    from sqlalchemy.orm import Session
    from sqlalchemy import select
except ImportError:
    # If running from parent directory
    sys.path.append(os.path.join(os.getcwd(), 'server'))
    from app.main import engine
    from app.models import User
    from sqlalchemy.orm import Session
    from sqlalchemy import select

def list_users():
    with Session(engine) as sess:
        users = sess.execute(select(User)).scalars().all()
        print(f"{'ID':<5} {'Email':<30} {'Admin':<10} {'Name':<20}")
        print("-" * 70)
        for u in users:
            print(f"{u.id:<5} {u.email:<30} {str(u.is_admin):<10} {u.name or ''}")

def set_admin(email, is_admin):
    with Session(engine) as sess:
        user = sess.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            print(f"Error: User {email} not found.")
            return
        
        user.is_admin = bool(int(is_admin))
        sess.commit()
        print(f"User {email} updated. is_admin = {user.is_admin}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage users")
    subparsers = parser.add_subparsers(dest="command")
    
    # List command
    subparsers.add_parser("list", help="List all users")
    
    # Set Admin command
    parser_set = subparsers.add_parser("set-admin", help="Set admin status")
    parser_set.add_argument("email", help="User email")
    parser_set.add_argument("status", help="1 for Admin, 0 for User", choices=['0', '1'])
    
    args = parser.parse_args()
    
    if args.command == "list":
        list_users()
    elif args.command == "set-admin":
        set_admin(args.email, args.status)
    else:
        parser.print_help()
