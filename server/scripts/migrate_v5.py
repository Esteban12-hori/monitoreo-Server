import os
import sys
from sqlalchemy import create_engine, text

# Adjust path to find the database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "monitor.db")

def migrate():
    print(f"🔧 Starting Database Migration V5...")
    print(f"📂 Database Path: {DB_PATH}")
    
    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)
    
    # 1. Add postman_access_level to user_server_link
    print("1️⃣  Checking/Applying column migrations (user_server_link.postman_access_level)...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE user_server_link ADD COLUMN postman_access_level VARCHAR(20) DEFAULT 'none'"))
            conn.commit()
            print("   ✅ Added 'postman_access_level' to 'user_server_link' table.")
        except Exception as e:
            err = str(e).lower()
            if "duplicate column name" in err:
                print("   ℹ️  Column 'postman_access_level' already exists in 'user_server_link'.")
            else:
                print(f"   ⚠️  Could not add 'postman_access_level': {e}")

    # 2. Add extra_emails to alert_rules
    print("2️⃣  Checking/Applying column migrations (alert_rules.extra_emails)...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE alert_rules ADD COLUMN extra_emails TEXT"))
            conn.commit()
            print("   ✅ Added 'extra_emails' to 'alert_rules' table.")
        except Exception as e:
            err = str(e).lower()
            if "duplicate column name" in err:
                print("   ℹ️  Column 'extra_emails' already exists in 'alert_rules'.")
            else:
                print(f"   ⚠️  Could not add 'extra_emails': {e}")

    print("\n✅ Migration V5 completed.")

if __name__ == "__main__":
    migrate()
