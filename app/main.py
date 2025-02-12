import time
import mysql.connector
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
from datetime import datetime
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import uvicorn

# Load environment variables from .env
load_dotenv()

app = FastAPI()

# Fix static file serving
app.mount("/static", StaticFiles(directory=os.path.abspath("app/static")), name="static")

# Ensure templates directory exists
# New (Correct)
templates = Jinja2Templates(directory=os.path.abspath("app/templates"))

# Sensor types
SENSOR_TYPES = {"temperature", "humidity", "light"}

# Pydantic model for inserting/updating sensor data
class SensorData(BaseModel):
    value: float
    unit: str
    timestamp: str = None

@app.get("/dashboard")
def dashboard(request: Request):
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Template error: {str(e)}"})

# Function to get MySQL database connection with retries
def get_db_connection(retries=5, delay=5):
    for i in range(retries):
        try:
            conn = mysql.connector.connect(
                host=os.getenv("MYSQL_HOST", "db"),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "mydatabase")
            )
            return conn
        except mysql.connector.Error as e:
            print(f"Database connection failed. Retrying {i+1}/{retries} in {delay}s...")
            time.sleep(delay)
    raise HTTPException(status_code=500, detail="Cannot connect to MySQL database after multiple attempts.")

# Ensure tables exist
def ensure_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    for sensor in SENSOR_TYPES:
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {sensor} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                value FLOAT NOT NULL,
                unit VARCHAR(10) NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/{sensor_type}")
def get_sensor_data(sensor_type: str):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM {sensor_type}")
    data = cursor.fetchall()
    conn.close()

    if not data:
        return JSONResponse(status_code=200, content={"data": []})  # Return empty list instead of 500 error

    return {"data": data}


@app.get("/api/{sensor_type}/count")
def get_sensor_count(sensor_type: str):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT COUNT(*) FROM {sensor_type}")
        count = cursor.fetchone()[0]
        return {"count": count}
    except mysql.connector.Error as e:
        return JSONResponse(status_code=500, content={"error": f"Database query error: {str(e)}"})
    finally:
        cursor.close()
        conn.close()

        

if __name__ == "__main__":
    ensure_tables()  # Ensure tables exist before running
    uvicorn.run(app="app.main:app", host="0.0.0.0", port=6543, reload=True)
