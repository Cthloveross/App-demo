import os
import logging
import sqlite3
import mysql.connector
import csv
import uuid
import json
from typing import Optional, Generator
from dotenv import load_dotenv
from mysql.connector import Error
from bcrypt import hashpw, gensalt, checkpw
from fastapi import Depends, HTTPException

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------- Constants -------------------
SQLITE_DB_PATH = "sensor_data.db"  # Local SQLite DB for sensor data
CSV_PATH = "./sample"  # CSV directory for seeding

MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST"),
    "user": os.getenv("MYSQL_USER"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE"),
    "port": int(os.getenv("MYSQL_PORT", 3306))
}

SENSOR_TYPES = {"temperature", "humidity", "light"}

# ------------------- SQLite Functions -------------------
def get_sqlite_connection():
    """Returns a connection to SQLite for sensor data."""
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_sqlite_tables():
    """Ensures sensor_data table exists in SQLite."""
    conn = get_sqlite_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_type TEXT CHECK(sensor_type IN ('temperature', 'humidity', 'light')),
            value REAL NOT NULL,
            unit VARCHAR(10) DEFAULT 'C',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    logger.info("✅ SQLite sensor_data table ensured.")

# ------------------- MySQL Functions -------------------
def get_mysql_connection():
    """Returns a MySQL database connection."""
    return mysql.connector.connect(**MYSQL_CONFIG)

def get_db() -> Generator:
    """Dependency injection for FastAPI."""
    connection = get_mysql_connection()
    try:
        yield connection
    finally:
        connection.close()

def table_exists(table_name: str) -> bool:
    """Checks if a table exists in MySQL."""
    connection = get_mysql_connection()
    cursor = connection.cursor()
    cursor.execute("SHOW TABLES LIKE %s", (table_name,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()
    return bool(result)

def ensure_mysql_tables():
    """Ensures MySQL tables exist without dropping data."""
    connection = get_mysql_connection()
    cursor = connection.cursor()

        # 🚨 Drop existing tables before recreating them (Be careful with this in production!)
    cursor.execute("DROP TABLE IF EXISTS users, sessions, devices, wardrobe")
    connection.commit()

    table_schemas = {
        "users": """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                password VARCHAR(255) NOT NULL,
                location VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        "sessions": """
            CREATE TABLE IF NOT EXISTS sessions (
                id VARCHAR(36) PRIMARY KEY,
                user_id INT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """,
        "devices": """
            CREATE TABLE IF NOT EXISTS devices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                device_name VARCHAR(255) NOT NULL,
                device_id VARCHAR(255) NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """,
        "wardrobe": """
            CREATE TABLE IF NOT EXISTS wardrobe (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                item_name VARCHAR(255) NOT NULL,
                item_type VARCHAR(255),
                color VARCHAR(50),
                material VARCHAR(100),
                weather_suitability JSON,
                item_image TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """
    }

    for table, query in table_schemas.items():
        if not table_exists(table):
            cursor.execute(query)
            connection.commit()
            logger.info(f"✅ Table {table} ensured.")

    cursor.close()
    connection.close()

# ------------------- User Authentication -------------------
def hash_password(password: str) -> str:
    """Hashes a password before storing it."""
    return hashpw(password.encode(), gensalt()).decode()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies if a password matches the stored hash."""
    return checkpw(plain_password.encode(), hashed_password.encode())



def create_user(username: str, email: str, password: str, location: Optional[str] = None) -> int:
    """Registers a new user in the database and returns the user ID."""
    connection = get_mysql_connection()
    cursor = connection.cursor()
    
    try:
        hashed_password = hash_password(password)  # Ensure password hashing
        cursor.execute(
            "INSERT INTO users (username, email, password, location) VALUES (%s, %s, %s, %s)",
            (username, email, hashed_password, location)
        )
        connection.commit()
        
        return cursor.lastrowid  # ✅ Return the newly inserted user ID
    
    except Error as e:
        logging.error(f"❌ Error creating user {username}: {e}")
        raise HTTPException(status_code=500, detail="User creation failed")
    
    finally:
        cursor.close()
        connection.close()


def get_user_by_username(username: str) -> Optional[dict]:
    """Fetches a user by username."""
    connection = get_mysql_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    return user


def get_user_by_email(email: str) -> Optional[dict]:
    """Fetches a user by username."""
    connection = get_mysql_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    connection.close()
    return user



def create_session(user_id: int) -> str:
    """Creates a new user session with UUID and stores it in MySQL."""
    
    session_id = str(uuid.uuid4())  # Generate a unique session ID
    connection = get_mysql_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute(
            "INSERT INTO sessions (id, user_id) VALUES (%s, %s)", 
            (session_id, user_id)
        )
        connection.commit()
        return session_id  # ✅ Returns session ID correctly
    except Exception as e:
        logging.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail="Session creation failed")
    finally:
        cursor.close()
        connection.close()




def get_session(session_id: str) -> Optional[dict]:
    """Fetches session details from the database."""
    connection = get_mysql_connection()
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    cursor.close()
    connection.close()
    return session

def delete_session(session_id: str) -> bool:
    """Deletes a user session from the database."""
    connection = get_mysql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
        connection.commit()
        return True
    finally:
        cursor.close()
        connection.close()

# ------------------- IoT Device & Wardrobe Management -------------------
def register_device(user_id: int, device_name: str, device_id: str) -> bool:
    """Registers an IoT device for a user."""
    connection = get_mysql_connection()
    cursor = connection.cursor()
    try:
        cursor.execute(
            "INSERT INTO devices (user_id, device_name, device_id) VALUES (%s, %s, %s)",
            (user_id, device_name, device_id)
        )
        connection.commit()
        return True
    except Error as e:
        logger.error(f"❌ Error registering device {device_name}: {e}")
        return False
    finally:
        cursor.close()
        connection.close()


# ------------------- Database Setup Execution -------------------
# if __name__ == "__main__":
#     logger.info("🔧 Setting up databases...")
#     ensure_sqlite_tables()  # Ensures sensor data table exists
#     ensure_mysql_tables()  # Ensures user, session, device, wardrobe tables exist
#     logger.info("✅ Database setup complete.")
