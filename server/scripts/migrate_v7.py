import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.append(server_dir)

from sqlalchemy import create_engine, text
from app.config import DB_PATH


def migrate():
    print("🔧 Starting Database Migration V7...")
    print(f"📂 Database Path: {DB_PATH}")

    db_url = f"sqlite:///{DB_PATH}"
    engine = create_engine(db_url, future=True)

    statements = [
        "ALTER TABLE metrics ADD COLUMN net_bytes_sent REAL",
        "ALTER TABLE metrics ADD COLUMN net_bytes_recv REAL",
        "ALTER TABLE metrics ADD COLUMN net_packets_sent REAL",
        "ALTER TABLE metrics ADD COLUMN net_packets_recv REAL",
    ]

    with engine.connect() as conn:
        for stmt in statements:
            col_name = stmt.split("ADD COLUMN", 1)[1].strip().split()[0]
            print(f"1️⃣  Applying column migration for {col_name}...")
            try:
                conn.execute(text(stmt))
                conn.commit()
                print(f"   ✅ Added '{col_name}' to 'metrics' table.")
            except Exception as e:
                err = str(e).lower()
                if "duplicate column name" in err:
                    print(f"   ℹ️  Column '{col_name}' already exists in 'metrics'.")
                else:
                    print(f"   ⚠️  Could not add '{col_name}': {e}")

    print("\n✅ Migration V7 completed.")


if __name__ == "__main__":
    migrate()

