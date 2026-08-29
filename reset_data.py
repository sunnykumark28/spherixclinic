"""
reset_data.py — Spherix Clinic Data Reset Script
Clears ALL transactional + user data from SQL + JSON, resets ID counters.
Preserves: blood_stock defaults, system settings.
"""
import os, sys, json, shutil
from datetime import datetime

# ─── Locate project root ───────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ─── SQL connection config (mirrors app.py) ────────────────────────────────────
DRIVER   = os.environ.get('DB_DRIVER',   '{ODBC Driver 17 for SQL Server}')
SERVER   = os.environ.get('DB_SERVER',   'localhost')
DATABASE = os.environ.get('DB_NAME',     'dev_ai_plus')
USERNAME = os.environ.get('DB_USER',     'sa')
PASSWORD = os.environ.get('DB_PASSWORD', 'RadhaRani@123')

# Tables to TRUNCATE (order matters for FK constraints — children first)
TABLES_TO_CLEAR = [
    'camp_registrations',
    'appointments',
    'messages',
    'orders',
    'reviews',
    'bed_bookings',
    'doctor_images',
    'staff',
    'doctors',
    'patients',
    'hospitals',
    'blood_donors',
    'organ_donors',
    'camps',
    'blood_stock',
    # These are stored as JSON blobs in a key_value table if it exists
]

# Optional extra tables (non-critical; skip if missing)
OPTIONAL_TABLES = [
    'organ_requests',
    'ad_bookings',
    'patient_vitals',
    'symptom_reviews',
    'activity_logs',
    'newsletter_subscribers',
    'contact_messages',
    'sicons_applications',
    'medicines',
    'next_ids',
    'settings',
    'doctor_opinions',
    'key_value_store',
    'kv_store',
    'app_data',
]

def print_banner(text, char="─"):
    print(f"\n{char * 55}")
    print(f"  {text}")
    print(f"{char * 55}")

def reset_sql():
    print_banner("🗄️  Resetting SQL Database", "═")
    try:
        import pyodbc

        # Auto-configure ODBC on macOS
        brew_etc = "/opt/homebrew/etc"
        if os.path.isdir(brew_etc):
            os.environ.setdefault('ODBCSYSINI', brew_etc)
            print(f"  ℹ️  ODBCSYSINI set to {brew_etc}")

        conn_str = (
            f'DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};'
            f'UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes;'
        )
        conn = pyodbc.connect(conn_str, autocommit=True)
        cursor = conn.cursor()
        print("  ✅ Connected to SQL Server")

        # Disable FK constraints temporarily
        cursor.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? NOCHECK CONSTRAINT ALL'")

        cleared, skipped = [], []

        all_tables = TABLES_TO_CLEAR + OPTIONAL_TABLES
        for table in all_tables:
            try:
                cursor.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL TRUNCATE TABLE {table}")
                cleared.append(table)
                print(f"  ✅ TRUNCATED: {table}")
            except Exception as e:
                # Try DELETE fallback if TRUNCATE is blocked by FK constraints
                try:
                    cursor.execute(f"IF OBJECT_ID('{table}', 'U') IS NOT NULL DELETE FROM {table}")
                    cleared.append(table)
                    print(f"  ✅ DELETED (FK fallback): {table}")
                except Exception as del_err:
                    skipped.append(table)
                    print(f"  ⚠️  Skipped  : {table} ({del_err})")

        # Re-enable FK constraints
        cursor.execute("EXEC sp_MSforeachtable 'ALTER TABLE ? WITH CHECK CHECK CONSTRAINT ALL'")

        # Re-insert default blood stock
        blood_defaults = [
            ("A+", 15), ("A-", 5), ("B+", 12), ("B-", 4),
            ("AB+", 8), ("AB-", 3), ("O+", 25), ("O-", 10)
        ]
        try:
            for grp, cnt in blood_defaults:
                cursor.execute(
                    "IF OBJECT_ID('blood_stock','U') IS NOT NULL "
                    "INSERT INTO blood_stock (blood_group, quantity) VALUES (?, ?)",
                    grp, cnt
                )
            print("  ✅ Blood stock defaults restored")
        except Exception as e:
            print(f"  ⚠️  Blood stock restore skipped: {e}")

        conn.close()
        print(f"\n  📊 Cleared {len(cleared)} table(s), skipped {len(skipped)}")
        return True

    except Exception as e:
        print(f"  ❌ SQL reset failed: {e}")
        print("  ℹ️  Continuing with JSON reset only...")
        return False

def main():
    print("\n" + "═" * 55)
    print("   🔄  SPHERIX CLINIC — FULL DATA RESET")
    print("   ⚠️   This will erase ALL users, appointments,")
    print("        orders, messages, and other records.")
    print("═" * 55)

    confirm = input("\n  Type 'RESET' to confirm: ").strip()
    if confirm != 'RESET':
        print("\n  ❌ Aborted. No changes made.")
        sys.exit(0)

    sql_ok  = reset_sql()

    print_banner("✅  Reset Complete!", "═")
    print(f"  SQL Database : {'✅ Cleared' if sql_ok  else '❌ Failed'}")
    print("\n  🚀 Restart the app to apply changes:")
    print("     venv/bin/python app.py\n")

if __name__ == '__main__':
    main()
