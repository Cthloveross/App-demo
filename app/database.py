import os
import csv
import mysql.connector
from dotenv import load_dotenv
import time

# Load environment variables from .env
load_dotenv()

# Define sensor types and CSV paths
SENSOR_TYPES = {"temperature", "humidity", "light"}
CSV_PATH = "./sample"

def get_db_connection(retries=5, delay=5):
    """Establish a connection to MySQL with a retry mechanism."""
    for i in range(retries):
        try:
            conn = mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "tech-assignment-final-project-cth-db-1"),  # MySQL container name
                user=os.getenv("MYSQL_USER", "myuser"),
                password=os.getenv("MYSQL_PASSWORD", "123456"),
                database=os.getenv("MYSQL_DATABASE", "mydatabase")
            )
            print("[INFO] Successfully connected to MySQL.")
            return conn
        except mysql.connector.Error as e:
            print(f"[ERROR] Database connection failed ({e}). Retrying {i+1}/{retries} in {delay}s...")
            time.sleep(delay)
    raise RuntimeError("Cannot connect to MySQL after multiple attempts.")

def ensure_tables():
    """Create the required tables if they do not exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for sensor in SENSOR_TYPES:
        print(f"[INFO] Ensuring table {sensor} exists...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {sensor} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                value FLOAT NOT NULL,
                unit VARCHAR(10) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("[INFO] Tables ensured.")

def seed_database():
    """Load data from CSV files into the corresponding tables."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for sensor in SENSOR_TYPES:
        cursor.execute(f"SELECT COUNT(*) FROM {sensor}")
        count = cursor.fetchone()[0]
        print(f"[INFO] Table {sensor} currently has {count} rows.")

        if count == 0:  # Insert only if the table is empty
            file_path = os.path.join(CSV_PATH, f"{sensor}.csv")
            if os.path.exists(file_path):
                print(f"[INFO] Seeding {sensor} data from {file_path}...")

                with open(file_path, newline='') as csvfile:
                    reader = csv.DictReader(csvfile)
                    print(f"[DEBUG] Detected CSV columns: {reader.fieldnames}")

                    if set(reader.fieldnames) != {"value", "unit", "timestamp"} and set(reader.fieldnames) != {"timestamp", "value", "unit"}:
                        print(f"[ERROR] CSV format mismatch in {file_path}. Expected columns: value, unit, timestamp OR timestamp, value, unit")
                        continue

                    data = []
                    for row in reader:
                        if reader.fieldnames == ["timestamp", "value", "unit"]:
                            data.append((float(row["value"]), row["unit"], row["timestamp"]))  # ✅ Correct order
                        elif reader.fieldnames == ["value", "unit", "timestamp"]:
                            data.append((float(row["value"]), row["unit"], row["timestamp"]))  # ✅ Already correct
                        else:
                            print(f"[ERROR] Unexpected column order: {reader.fieldnames}")
                            continue  # Skip if format is incorrect

                    print(f"[DEBUG] Total rows read from {file_path}: {len(data)}")

                    if data:
                        cursor.executemany(
                            f"INSERT INTO {sensor} (value, unit, timestamp) VALUES (%s, %s, %s)",
                            data
                        )
                        conn.commit()
                        print(f"[INFO] {sensor} data seeded successfully. {len(data)} rows inserted.")

    cursor.close()
    conn.close()
    print("[INFO] Database seeding complete.")

