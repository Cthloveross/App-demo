from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import mysql.connector
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
templates = Jinja2Templates(directory=os.path.abspath("app"))

# Sensor types
SENSOR_TYPES = {"temperature", "humidity", "light"}

# Pydantic model for inserting/updating sensor data
class SensorData(BaseModel):
    value: float
    unit: str
    timestamp: str = None

# Function to get MySQL database connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "db"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "mydatabase")
        )
        return conn
    except mysql.connector.Error as e:
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

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

ensure_tables()

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard")
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/{sensor_type}")
def get_sensor_data(sensor_type: str, order_by: str = Query(None, alias="order-by"), start_date: str = Query(None, alias="start-date"), end_date: str = Query(None, alias="end-date")):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    query = f"SELECT * FROM {sensor_type}"
    conditions = []
    params = []

    if start_date:
        conditions.append("timestamp >= %s")
        params.append(start_date)
    if end_date:
        conditions.append("timestamp <= %s")
        params.append(end_date)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if order_by in {"value", "timestamp"}:
        query += f" ORDER BY {order_by}"

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)  # Fix cursor to return a dictionary
    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.close()

    if not data:
        return JSONResponse(status_code=200, content={"data": []})  # Return empty list instead of 500 error

    return {"data": data}

@app.post("/api/{sensor_type}")
def insert_sensor_data(sensor_type: str, data: SensorData):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    timestamp = data.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(f"INSERT INTO {sensor_type} (value, unit, timestamp) VALUES (%s, %s, %s)", 
                    (data.value, data.unit, timestamp))
        conn.commit()
        new_id = cursor.lastrowid
        return {"id": new_id}
    except mysql.connector.Error as e:
        return JSONResponse(status_code=500, content={"error": f"Database insert error: {str(e)}"})
    finally:
        conn.close()

@app.get("/api/{sensor_type}/count")
def get_sensor_count(sensor_type: str):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {sensor_type}")
    count = cursor.fetchone()[0]
    conn.close()
    return {"count": count}

if __name__ == "__main__":
   uvicorn.run(app="app.main:app", host="0.0.0.0", port=6543, reload=True)
