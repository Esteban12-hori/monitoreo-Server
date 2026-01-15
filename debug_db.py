import sqlite3
import os
import sys

# Force flush
sys.stdout.reconfigure(encoding='utf-8')

db_path = os.path.join(os.getcwd(), 'server', 'data', 'monitor.db')
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

print(f"Using DB: {db_path}")
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check columns in user_server_link
print("\n--- SCHEMA CHECK ---")
try:
    c.execute("PRAGMA table_info(user_server_link)")
    cols = [row[1] for row in c.fetchall()]
    print(f"Columns in user_server_link: {cols}")
    if 'receive_alerts' not in cols:
        print("WARNING: receive_alerts column missing!")
except Exception as e:
    print(f"Error checking schema: {e}")

print("\n--- USUARIOS ---")
try:
    for row in c.execute("SELECT id, email, is_admin FROM users"):
        uid, email, is_admin = row
        print(f"ID: {uid} | Email: {email} | Admin: {is_admin}")
        
        # Get links
        links = []
        try:
            # Select only columns we know exist or *
            c2 = conn.cursor()
            c2.execute("SELECT server_id FROM user_server_link WHERE user_id=?", (uid,))
            links = [l[0] for l in c2.fetchall()]
        except Exception as e:
            print(f"  Error getting links: {e}")
        print(f"   Servers asignados: {links}")
except Exception as e:
    print(f"Error querying users: {e}")

print("\n--- SERVIDORES ---")
try:
    for row in c.execute("SELECT server_id FROM servers"):
        print(f"ID: {row[0]}")
except Exception as e:
    print(f"Error querying servers: {e}")

conn.close()
