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

from app.database import ensure_tables, seed_database, get_db_connection

# Load environment variables from .env
load_dotenv()

app = FastAPI()

# Fix static file serving
app.mount("/static", StaticFiles(directory=os.path.abspath("app/static")), name="static")

# Ensure templates directory exists
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
    """Render the dashboard template."""
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Template error: {str(e)}"})

@app.get("/")
def read_root(request: Request):
    """Render index page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/{sensor_type}")
def get_sensor_data(
    sensor_type: str,
    order_by: str = Query(None, alias="order-by"),
    start_date: str = Query(None, alias="start-date"),
    end_date: str = Query(None, alias="end-date"),
):
    """Fetch all sensor data with optional filtering and ordering."""
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = f"SELECT * FROM {sensor_type} WHERE 1=1"
    params = []

    if start_date:
        query += " AND timestamp >= %s"
        params.append(start_date)

    if end_date:
        query += " AND timestamp <= %s"
        params.append(end_date)

    if order_by in {"value", "timestamp"}:
        query += f" ORDER BY {order_by}"

    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.close()

    return {"data": data}

@app.get("/api/{sensor_type}/count")
def get_sensor_count(sensor_type: str):
    """Get count of rows for the given sensor type."""
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(f"SELECT COUNT(*) FROM {sensor_type}")
    count = cursor.fetchone()[0]
    conn.close()

    return  count






@app.post("/api/{sensor_type}")
def insert_sensor_data(sensor_type: str, data: SensorData):
    """Insert new sensor data."""
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    timestamp = data.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO {sensor_type} (value, unit, timestamp) VALUES (%s, %s, %s)", 
        (data.value, data.unit, timestamp)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return {"id": new_id}  # ✅ Fix: Return JSON response






@app.get("/api/{sensor_type}")
def get_sensor_data(
    sensor_type: str,
    order_by: str = Query(None, alias="order-by"),
    start_date: str = Query(None, alias="start-date"),
    end_date: str = Query(None, alias="end-date"),
):
    """Fetch all sensor data with optional filtering and ordering."""
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = f"SELECT id, value, unit, timestamp FROM {sensor_type} WHERE 1=1"
    params = []

    if start_date:
        query += " AND timestamp >= %s"
        params.append(start_date)

    if end_date:
        query += " AND timestamp <= %s"
        params.append(end_date)

    if order_by in {"value", "timestamp"}:
        query += f" ORDER BY {order_by} ASC"  # ✅ Ensure correct ordering

    cursor.execute(query, params)
    data = cursor.fetchall()
    conn.close()

    return {"data": data}




@app.put("/api/{sensor_type}/{id}")
def update_sensor_data(sensor_type: str, id: int, data: SensorData):
    """Update sensor data by ID."""
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    
    if data.value is not None:
        updates.append("value = %s")
        params.append(data.value)
    if data.unit is not None:
        updates.append("unit = %s")
        params.append(data.unit)
    if data.timestamp is not None:
        updates.append("timestamp = %s")
        params.append(data.timestamp)
    
    if not updates:
        return {"message": "No updates provided"}
    
    query = f"UPDATE {sensor_type} SET {', '.join(updates)} WHERE id = %s"
    params.append(id)
    
    cursor.execute(query, params)
    conn.commit()

    # Fetch the updated row
    cursor.execute(f"SELECT * FROM {sensor_type} WHERE id = %s", (id,))
    updated_data = cursor.fetchone()
    conn.close()
    
    return {"updated_data": updated_data}  # ✅ Fix: Return updated row





@app.delete("/api/{sensor_type}/{id}")
def delete_sensor_data(sensor_type: str, id: int):
    """Delete sensor data by ID."""
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if the record exists before attempting deletion
    cursor.execute(f"SELECT COUNT(*) FROM {sensor_type} WHERE id = %s", (id,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        conn.close()
        return JSONResponse(status_code=404, content={"error": "Data not found"})

    # Delete the record
    cursor.execute(f"DELETE FROM {sensor_type} WHERE id = %s", (id,))
    conn.commit()
    conn.close()

    return JSONResponse(status_code=200, content={"message": "Data deleted successfully"})




if __name__ == "__main__":
    ensure_tables()
    seed_database()
    uvicorn.run(app="app.main:app", host="0.0.0.0", port=6543, reload=True)
