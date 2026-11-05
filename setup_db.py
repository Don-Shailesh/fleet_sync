#!/usr/bin/env python3
"""
FleetSync - Database Initialization & Seeding Script
Executes schema.sql on MySQL (XAMPP) to set up tables and demo data.
"""

import sys
import os
import mysql.connector
from mysql.connector import Error
from config import Config

def init_database():
    print("=" * 65)
    print("  FleetSync Enterprise - Database Setup & Seeder")
    print(f"  Target: {Config.MYSQL_HOST}:{Config.MYSQL_PORT} | DB: {Config.MYSQL_DB}")
    print("=" * 65)

    schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
    if not os.path.exists(schema_file):
        print(f"[ERROR] schema.sql not found at: {schema_file}")
        sys.exit(1)

    try:
        print(f"[*] Connecting to MySQL server at {Config.MYSQL_HOST}:{Config.MYSQL_PORT} (User: {Config.MYSQL_USER})...")
        conn = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            charset='utf8mb4',
            use_pure=True
        )
        cursor = conn.cursor()
        print("[OK] Connected to MySQL successfully!")

        print("[*] Reading and executing schema.sql...")
        with open(schema_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Split SQL file by statements separated by semicolon
        # Filter comments and empty lines
        statements = []
        current_stmt = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith('--') or stripped.startswith('/*'):
                continue
            current_stmt.append(line)
            if stripped.endswith(';'):
                statement_str = '\n'.join(current_stmt).strip()
                if statement_str:
                    statements.append(statement_str)
                current_stmt = []

        print(f"[*] Executing {len(statements)} SQL statements...")
        executed_count = 0
        for stmt in statements:
            try:
                cursor.execute(stmt)
                executed_count += 1
            except Error as stmt_err:
                print(f"[!] Warning executing statement:\n{stmt[:80]}...\nError: {stmt_err}")

        conn.commit()
        print(f"[OK] Successfully executed {executed_count} statements.")

        # Select database to verify tables
        cursor.execute(f"USE `{Config.MYSQL_DB}`")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        print("\n" + "-" * 65)
        print("  DATABASE VERIFICATION REPORT:")
        print("-" * 65)
        for (table_name,) in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            count = cursor.fetchone()[0]
            print(f"  - Table: {table_name:<25} | Records: {count}")

        cursor.close()
        conn.close()

        print("=" * 65)
        print("  [SUCCESS] FleetSync database created and seeded successfully!")
        print("  Default Login Credentials:")
        print("    Admin Account:")
        print("      Email:    admin@fleetsync.io")
        print("      Password: Admin@123")
        print("    Technician Account:")
        print("      Email:    tech@fleetsync.io")
        print("      Password: Tech@123")
        print("=" * 65)

    except mysql.connector.errors.InterfaceError as e:
        print("\n" + "!" * 65)
        print("  [CONNECTION ERROR] Could not connect to MySQL server!")
        print(f"  Error details: {e}")
        print("\n  TROUBLESHOOTING:")
        print("  1. Open XAMPP Control Panel.")
        print("  2. Click 'Start' next to MySQL service (port 3307).")
        print("  3. Verify port 3307 is not blocked by another service.")
        print("  4. Re-run: python setup_db.py")
        print("!" * 65)
        sys.exit(1)
    except Error as e:
        print(f"\n[ERROR] MySQL Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    init_database()
