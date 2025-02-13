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

    # Fetch valid column names to verify order_by
    cursor.execute(f"DESCRIBE {sensor_type}")
    valid_columns = {row["Field"] for row in cursor.fetchall()}

    if order_by and order_by not in valid_columns:
        conn.close()
        return JSONResponse(status_code=400, content={"error": f"Invalid order-by column: {order_by}"})

    query = f"SELECT * FROM {sensor_type} WHERE 1=1"
    params = []

    # Filtering by start and end date
    if start_date:
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S")
            query += " AND timestamp >= %s"
            params.append(start_date)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid start-date format. Use YYYY-MM-DD HH:MM:SS"})

    if end_date:
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S")
            query += " AND timestamp <= %s"
            params.append(end_date)
        except ValueError:
            return JSONResponse(status_code=400, content={"error": "Invalid end-date format. Use YYYY-MM-DD HH:MM:SS"})

    # Sorting by 'value' or 'timestamp'
    if order_by:
        query += f" ORDER BY `{order_by}` ASC"  # Using backticks to prevent SQL errors

    # Debug: Print the query before executing
    print(f"Executing SQL: {query} with params {params}")

    try:
        cursor.execute(query, params)
        data = cursor.fetchall()
        conn.close()
        return JSONResponse(status_code=200, content={"data": data})
    except Exception as e:
        conn.close()
        print("SQL Execution Error:", str(e))  # Debugging
        return JSONResponse(status_code=500, content={"error": f"Query execution failed: {str(e)}"})







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




@app.get("/api/{sensor_type}/{id}")
def get_sensor_data_by_id(sensor_type: str, id: int):
    """Fetch sensor data by ID."""
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(f"SELECT * FROM {sensor_type} WHERE id = %s", (id,))
    data = cursor.fetchone()
    conn.close()
    
    if not data:
        return JSONResponse(status_code=404, content={"error": "Data not found"})
    
    return data  # ✅ Fix: Return raw JSON instead of wrapping it in {"data": ...}



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