from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sqlite3
import os
from datetime import datetime
from database import create_and_populate_tables

app = FastAPI()

# Initialize database
create_and_populate_tables()

# Sensor types
SENSOR_TYPES = {"temperature", "humidity", "light"}

# Pydantic model for inserting/updating sensor data
class SensorData(BaseModel):
    value: float
    unit: str
    timestamp: str = None

# Function to get database connection
def get_db_connection():
    return sqlite3.connect("sensor_data.db")

@app.get("/api/{sensor_type}")
def get_sensor_data(sensor_type: str, order_by: str = Query(None, alias="order-by"), start_date: str = Query(None, alias="start-date"), end_date: str = Query(None, alias="end-date")):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    query = f"SELECT * FROM {sensor_type}"
    conditions = []
    params = []
    
    if start_date:
        conditions.append("timestamp >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("timestamp <= ?")
        params.append(end_date)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    if order_by in {"value", "timestamp"}:
        query += f" ORDER BY {order_by}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
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
    cursor.execute(f"INSERT INTO {sensor_type} (value, unit, timestamp) VALUES (?, ?, ?)", 
                   (data.value, data.unit, timestamp))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"id": new_id}

@app.get("/api/{sensor_type}/{id}")
def get_sensor_data_by_id(sensor_type: str, id: int):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {sensor_type} WHERE id = ?", (id,))
    data = cursor.fetchone()
    conn.close()
    if not data:
        return JSONResponse(status_code=404, content={"error": "Data not found"})
    return {"data": data}

@app.put("/api/{sensor_type}/{id}")
def update_sensor_data(sensor_type: str, id: int, data: SensorData):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = []
    params = []
    
    if data.value is not None:
        updates.append("value = ?")
        params.append(data.value)
    if data.unit is not None:
        updates.append("unit = ?")
        params.append(data.unit)
    if data.timestamp is not None:
        updates.append("timestamp = ?")
        params.append(data.timestamp)
    
    if not updates:
        return {"message": "No updates provided"}
    
    query = f"UPDATE {sensor_type} SET {', '.join(updates)} WHERE id = ?"
    params.append(id)
    cursor.execute(query, params)
    conn.commit()
    conn.close()
    return {"message": "Data updated successfully"}

@app.delete("/api/{sensor_type}/{id}")
def delete_sensor_data(sensor_type: str, id: int):
    if sensor_type not in SENSOR_TYPES:
        return JSONResponse(status_code=404, content={"error": "Invalid sensor type"})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {sensor_type} WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return {"message": "Data deleted successfully"}

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
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
