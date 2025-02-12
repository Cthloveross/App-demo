from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import mysql.connector
import os
from datetime import datetime
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import pandas as pd
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

# Function to get MySQL database connection using mysql-connector-python
def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv("MYSQL_HOST", "db"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "mydatabase")
    )

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
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.close()
    
    return {"data": data}

@app.post("/api/{sensor_type}")
def insert_sensor_data(sensor_type: str, data: SensorData):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    timestamp = data.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"INSERT INTO {sensor_type} (value, unit, timestamp) VALUES (%s, %s, %s)", 
                   (data.value, data.unit, timestamp))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id}

if __name__ == "__main__":
   uvicorn.run(app="app.main:app", host="0.0.0.0", port=6543, reload=True)
