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
    print(f"🔧 Starting Database Migration V4...")
    print(f"📂 Database Path: {DB_PATH}")
    
    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)
    
    # 1. Add services to metrics
    print("1️⃣  Checking/Applying column migrations (metrics.services)...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE metrics ADD COLUMN services TEXT"))
            conn.commit()
            print("   ✅ Added 'services' to 'metrics' table.")
        except Exception as e:
            err = str(e).lower()
            if "duplicate column name" in err:
                print("   ℹ️  Column 'services' already exists in 'metrics'.")
            else:
                print(f"   ⚠️  Could not add 'services': {e}")

    print("\n✅ Migration V4 completed.")

if __name__ == "__main__":
    migrate()
