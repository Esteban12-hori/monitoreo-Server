import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine, text
from server.app.config import DB_PATH

def migrate():
    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)
    
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE servers ADD COLUMN report_interval INTEGER DEFAULT 2400"))
            conn.commit()
            print("Migration successful: Added report_interval column.")
        except Exception as e:
            if "duplicate column name" in str(e).lower():
                print("Column report_interval already exists.")
            else:
                print(f"Migration error: {e}")

if __name__ == "__main__":
    migrate()
