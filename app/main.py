import sqlite3
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.database import seed_database  # Import only the function
import uvicorn
from fastapi import Request
from fastapi.templating import Jinja2Templates
import os
from fastapi.staticfiles import StaticFiles
import os
import os
import json
import time
import requests
import paho.mqtt.client as mqtt
from dotenv import load_dotenv



# 🌱 Seed the database and establish global SQLite connection
db: sqlite3.Connection = seed_database()
db.row_factory = sqlite3.Row  # Allows access by column name


# Ensure the correct path
static_path = os.path.abspath("app/static")


# Initialize FastAPI app
app = FastAPI()

# Mount the static directory
app.mount("/static", StaticFiles(directory=static_path), name="static")

# Allowed sensor types
SENSOR_TYPES = {"temperature", "humidity", "light"}

# Load environment variables from .env
load_dotenv()

BASE_TOPIC = os.getenv("BASE_TOPIC", "Eason/ece140/sensors")
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL", "http://localhost:5000/api/temperature")
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")

# Track the last time a request was sent
last_sent_time = 0

def on_connect(client, userdata, flags, rc):
    """Callback function when connected to MQTT broker"""
    if rc == 0:
        print(f"[MQTT] Connected successfully! Subscribing to: {BASE_TOPIC}/readings")
        client.subscribe(f"{BASE_TOPIC}/readings")
    else:
        print(f"[MQTT] Connection failed with code {rc}")

def on_message(client, userdata, msg):
    """Handles incoming MQTT messages"""
    global last_sent_time
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        temperature = payload.get("temperature")

        # Ensure valid temperature value
        if temperature is None:
            print("[MQTT] Received invalid message:", payload)
            return

        current_time = time.time()
        if current_time - last_sent_time < 5:  # Enforce 5-second delay
            print("[MQTT] Skipping request to avoid spamming")
            return

        last_sent_time = current_time

        # Send POST request to web server
        data = {"value": temperature, "unit": "C", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
        response = requests.post(WEB_SERVER_URL, json=data)

        if response.status_code == 200:
            print("[MQTT] Data sent successfully to web server!")
        else:
            print(f"[MQTT] Error sending data: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")







# Pydantic model for inserting/updating sensor data
class SensorData(BaseModel):
    value: float
    unit: str = "C"
    timestamp: Optional[str] = None

# Ensure templates directory exists
templates = Jinja2Templates(directory=os.path.abspath("app/templates"))

@app.get("/dashboard")
def dashboard(request: Request):
    """Render the dashboard template."""
    try:
        return templates.TemplateResponse("dashboard.html", {"request": request})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template error: {str(e)}")
    

@app.get("/")
def read_root(request: Request):
    """Render index.html instead of returning JSON."""
    return templates.TemplateResponse("index.html", {"request": request})

# 🟢 **Get Count of Sensor Data**
@app.get("/api/{sensor_type}/count")
def get_sensor_count(sensor_type: str):
    """Get the count of rows for a given sensor type."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    cursor = db.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM {sensor_type}")
    count = cursor.fetchone()[0]
    return count

# 🟢 **Get All Sensor Data**
@app.get("/api/{sensor_type}")
def get_sensor_data(
    sensor_type: str,
    order_by: str = Query(None, alias="order-by"),
    start_date: str = Query(None, alias="start-date"),
    end_date: str = Query(None, alias="end-date"),
):
    """Fetch all sensor data with optional filtering and ordering."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    query = f"SELECT * FROM {sensor_type} WHERE 1=1"
    params = []

    if start_date:
        query += " AND timestamp >= ?"
        params.append(start_date)
    if end_date:
        query += " AND timestamp <= ?"
        params.append(end_date)
    if order_by in {"value", "timestamp"}:
        query += f" ORDER BY {order_by} ASC"

    cursor = db.cursor()
    cursor.execute(query, params)
    data = cursor.fetchall()
    return [dict(row) for row in data]  # ✅ Return as list of dictionaries

# 🟢 **Get Sensor Data by ID**
@app.get("/api/{sensor_type}/{id}")
def get_sensor_data_by_id(sensor_type: str, id: int):
    """Fetch sensor data by ID."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    cursor = db.cursor()
    cursor.execute(f"SELECT * FROM {sensor_type} WHERE id = ?", (id,))
    data = cursor.fetchone()
    
    if not data:
        raise HTTPException(status_code=404, detail="Data not found")
    
    return dict(data)  # ✅ Return raw JSON

# 🟢 **Insert New Sensor Data**
@app.post("/api/{sensor_type}")
def insert_sensor_data(sensor_type: str, data: SensorData):
    """Insert new sensor data."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    timestamp = data.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor = db.cursor()
    cursor.execute(
        f"INSERT INTO {sensor_type} (value, unit, timestamp) VALUES (?, ?, ?)",
        (data.value, data.unit, timestamp)
    )
    db.commit()
    new_id = cursor.lastrowid

    return {"id": new_id, "value": data.value, "unit": data.unit, "timestamp": timestamp}

# 🟢 **Update Sensor Data by ID**
@app.put("/api/{sensor_type}/{id}")
def update_sensor_data(sensor_type: str, id: int, data: SensorData):
    """Update sensor data by ID."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

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
        raise HTTPException(status_code=400, detail="No updates provided")

    query = f"UPDATE {sensor_type} SET {', '.join(updates)} WHERE id = ?"
    params.append(id)

    cursor = db.cursor()
    cursor.execute(query, params)
    db.commit()

    # Fetch the updated row
    cursor.execute(f"SELECT * FROM {sensor_type} WHERE id = ?", (id,))
    updated_data = cursor.fetchone()

    if not updated_data:
        raise HTTPException(status_code=404, detail="Data not found")

    return {"updated_data": dict(updated_data)}  # ✅ Return updated row

# 🟢 **Delete Sensor Data by ID**
@app.delete("/api/{sensor_type}/{id}")
def delete_sensor_data(sensor_type: str, id: int):
    """Delete sensor data by ID."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    cursor = db.cursor()

    # Check if the record exists before attempting deletion
    cursor.execute(f"SELECT COUNT(*) FROM {sensor_type} WHERE id = ?", (id,))
    count = cursor.fetchone()[0]
    
    if count == 0:
        raise HTTPException(status_code=404, detail="Data not found")

    # Delete the record
    cursor.execute(f"DELETE FROM {sensor_type} WHERE id = ?", (id,))
    db.commit()

    return {"message": "Data deleted successfully"}

# 🟢 **Run FastAPI Server**
if __name__ == "__main__":
    # Initialize MQTT client


    # Initialize MQTT Client with latest API version
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message


    # Connect to MQTT broker
    print(f"[MQTT] Connecting to broker at {MQTT_BROKER}...")
    client.connect(MQTT_BROKER, 1883, 60)

    # Start listening for messages
    client.loop_forever()

    uvicorn.run(app="app.main:app", host="0.0.0.0", port=6543, reload=True)
