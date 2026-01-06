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
    print(f"🔧 Starting Database Migration V3...")
    print(f"📂 Database Path: {DB_PATH}")
    
    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)
    
    # 1. Create alert_rules table
    print("1️⃣  Checking/Creating missing tables (alert_rules)...")
    try:
        Base.metadata.create_all(engine)
        print("   ✅ Tables verified.")
    except Exception as e:
        print(f"   ❌ Error creating tables: {e}")

    # 2. Add group_name to servers
    print("2️⃣  Checking/Applying column migrations...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE servers ADD COLUMN group_name VARCHAR(255)"))
            conn.commit()
            print("   ✅ Added 'group_name' to 'servers' table.")
        except Exception as e:
            err = str(e).lower()
            if "duplicate column name" in err:
                print("   ℹ️  Column 'group_name' already exists in 'servers'.")
            else:
                print(f"   ⚠️  Could not add 'group_name': {e}")

    print("\n✅ Migration V3 completed.")

if __name__ == "__main__":
    migrate()
