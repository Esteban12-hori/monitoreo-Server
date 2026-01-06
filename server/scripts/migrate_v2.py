import sys
import os

# Add 'server' directory to sys.path so we can import 'app'
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir) # .../server
sys.path.append(server_dir)

from sqlalchemy import create_engine, text
from app.config import DB_PATH
from app.models import Base

def migrate():
    print(f"🔧 Starting Database Migration V2...")
    print(f"📂 Database Path: {DB_PATH}")
    
    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)
    
    # 1. Create any missing tables (safe to run, skips existing)
    # This should create 'user_server_link'
    print("1️⃣  Checking/Creating missing tables (user_server_link)...")
    try:
        Base.metadata.create_all(engine)
        print("   ✅ Tables verified.")
    except Exception as e:
        print(f"   ❌ Error creating tables: {e}")

    # 2. Apply specific column migrations
    print("2️⃣  Checking/Applying column migrations...")
    with engine.connect() as conn:
        # Migration: Add receive_alerts to users
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN receive_alerts BOOLEAN DEFAULT 0"))
            conn.commit()
            print("   ✅ Added 'receive_alerts' to 'users' table.")
        except Exception as e:
            err = str(e).lower()
            if "duplicate column name" in err:
                print("   ℹ️  Column 'receive_alerts' already exists in 'users'.")
            else:
                print(f"   ⚠️  Could not add 'receive_alerts': {e}")

    print("\n✅ Migration V2 completed.")

if __name__ == "__main__":
    migrate()
