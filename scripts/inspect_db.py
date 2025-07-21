#!/usr/bin/env python
"""Inspect database tables."""

import sqlite3

db_path = "/tmp/leadfactory.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
tables = cursor.fetchall()

print(f"Tables in {db_path}:")
for table in tables:
    print(f"  - {table[0]}")

# Check alembic_version
cursor.execute("SELECT * FROM alembic_version;")
version = cursor.fetchone()
print(f"\nCurrent alembic version: {version[0] if version else 'None'}")

conn.close()
