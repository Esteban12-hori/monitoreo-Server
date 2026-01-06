import os
import sys
from pathlib import Path
import sqlalchemy
from sqlalchemy import create_engine, text

# Add parent directory to path to allow importing app modules
sys.path.append(str(Path(__file__).resolve().parent))

try:
    from app.config import DB_PATH
    from app.models import Base
    print(f"✅ Configuration loaded. DB_PATH: {DB_PATH}")
except ImportError as e:
    print(f"❌ Error importing app configuration: {e}")
    sys.exit(1)

def check_permissions():
    print("\n--- Checking Permissions ---")
    data_dir = DB_PATH.parent
    
    # Check Data Directory
    if not data_dir.exists():
        print(f"❌ Data directory does not exist: {data_dir}")
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Created data directory: {data_dir}")
        except Exception as e:
            print(f"❌ Failed to create data directory: {e}")
            return False
    else:
        print(f"✅ Data directory exists: {data_dir}")

    # Check Directory Write Permissions
    if os.access(data_dir, os.W_OK):
        print(f"✅ Data directory is writable")
    else:
        print(f"❌ Data directory is NOT writable by current user ({os.getlogin()})")
        return False

    # Check DB File
    if DB_PATH.exists():
        print(f"✅ Database file exists: {DB_PATH}")
        if os.access(DB_PATH, os.R_OK | os.W_OK):
            print(f"✅ Database file is readable and writable")
        else:
            print(f"❌ Database file is NOT readable/writable")
            return False
    else:
        print(f"⚠️ Database file does not exist (will be created by app)")
    
    return True

def check_database():
    print("\n--- Checking Database ---")
    try:
        engine = create_engine(f"sqlite:///{DB_PATH}")
        with engine.connect() as conn:
            print(f"✅ Database connection successful")
            
            # Check Tables
            tables = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table';")).fetchall()
            table_names = [t[0] for t in tables]
            print(f"ℹ️  Found tables: {', '.join(table_names)}")
            
            required_tables = ['servers', 'metrics', 'alerts', 'users', 'sessions', 'alert_recipients']
            missing = [t for t in required_tables if t not in table_names]
            
            if missing:
                print(f"⚠️ Missing tables: {missing}")
                print(f"ℹ️  Attempting to create tables...")
                Base.metadata.create_all(engine)
                print(f"✅ Tables created")
            else:
                print(f"✅ All required tables present")
                
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print(f"Running as user: {os.getlogin()}")
    print(f"Python version: {sys.version}")
    
    perms_ok = check_permissions()
    db_ok = check_database()
    
    if perms_ok and db_ok:
        print("\n✅ SYSTEM CHECK PASSED")
    else:
        print("\n❌ SYSTEM CHECK FAILED")
