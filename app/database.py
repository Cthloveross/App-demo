import sqlite3
import os
import csv

# Define the SQLite database file path
DB_PATH = "sensor_data.db"
CSV_PATH = "./sample"  # Path to the CSV files

# Define allowed sensor types
SENSOR_TYPES = {"temperature", "humidity", "light"}

def get_db_connection():
    """Establish a persistent SQLite connection."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Allows access by column name
    return conn

def ensure_tables():
    """Ensure all necessary tables exist in the SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for sensor in SENSOR_TYPES:
        print(f"[INFO] Ensuring table '{sensor}' exists...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {sensor} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value REAL NOT NULL,
                unit TEXT NOT NULL DEFAULT 'C',
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.commit()
    cursor.close()
    conn.close()
    print("[INFO] All tables ensured.")

def seed_database():
    """Ensure tables exist and populate them with data from CSV files if empty."""
    ensure_tables()  # First, ensure tables exist
    conn = get_db_connection()
    cursor = conn.cursor()

    for sensor in SENSOR_TYPES:
        cursor.execute(f"SELECT COUNT(*) FROM {sensor}")
        count = cursor.fetchone()[0]
        print(f"[INFO] Table '{sensor}' currently has {count} rows.")

        if count == 0:  # Only insert if the table is empty
            file_path = os.path.join(CSV_PATH, f"{sensor}.csv")
            if os.path.exists(file_path):
                print(f"[INFO] Seeding '{sensor}' data from {file_path}...")

                with open(file_path, newline='') as csvfile:
                    reader = csv.DictReader(csvfile)
                    columns = set(reader.fieldnames)
                    print(f"[DEBUG] Detected CSV columns: {columns}")

                    if not {"value", "unit", "timestamp"}.issubset(columns):
                        print(f"[ERROR] CSV format mismatch in {file_path}. Expected columns: value, unit, timestamp")
                        continue

                    data = []
                    for row in reader:
                        try:
                            data.append((float(row["value"]), row["unit"], row["timestamp"]))
                        except ValueError:
                            print(f"[WARNING] Skipping invalid row: {row}")
                            continue  # Skip invalid rows

                    print(f"[DEBUG] Total rows read from {file_path}: {len(data)}")

                    if data:
                        cursor.executemany(
                            f"INSERT INTO {sensor} (value, unit, timestamp) VALUES (?, ?, ?)",
                            data
                        )
                        conn.commit()
                        print(f"[INFO] '{sensor}' data seeded successfully. {len(data)} rows inserted.")

    cursor.close()
    print("[INFO] Database seeding complete.")
    return conn  # ✅ Return global SQLite connection
