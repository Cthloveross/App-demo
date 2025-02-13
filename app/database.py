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
    """Ensure the required tables exist with the correct structure."""
    conn = get_db_connection()
    cursor = conn.cursor()

    for sensor in SENSOR_TYPES:
        print(f"[INFO] Ensuring table {sensor} exists...")
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {sensor} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                value FLOAT NOT NULL,
                unit VARCHAR(10) NOT NULL DEFAULT 'C',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Ensure `unit` column exists
        cursor.execute(f"SHOW COLUMNS FROM {sensor} LIKE 'unit'")
        if not cursor.fetchone():
            print(f"[WARNING] Missing 'unit' column in {sensor}. Adding it...")
            cursor.execute(f"ALTER TABLE {sensor} ADD COLUMN unit VARCHAR(10) NOT NULL DEFAULT 'C';")

        # Ensure `timestamp` is `DATETIME`
        cursor.execute(f"SHOW COLUMNS FROM {sensor} WHERE Field = 'timestamp'")
        result = cursor.fetchone()
        if result and "timestamp" in result and "timestamp" in result[1]:
            print(f"[INFO] Converting 'timestamp' column in {sensor} to DATETIME...")
            cursor.execute(f"ALTER TABLE {sensor} MODIFY COLUMN timestamp DATETIME DEFAULT CURRENT_TIMESTAMP;")

    conn.commit()
    cursor.close()
    conn.close()
    print("[INFO] Table structure ensured.")

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
                    columns = set(reader.fieldnames)
                    print(f"[DEBUG] Detected CSV columns: {columns}")

                    if not {"value", "unit", "timestamp"}.issubset(columns):
                        print(f"[ERROR] CSV format mismatch in {file_path}. Expected columns: value, unit, timestamp")
                        continue

                    data = []
                    for row in reader:
                        try:
                            data.append((float(row["value"]), row["unit"], row["timestamp"]))  # ✅ Convert `value` to float
                        except ValueError:
                            print(f"[WARNING] Skipping invalid row: {row}")
                            continue  # Skip invalid rows

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


