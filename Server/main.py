
import sqlite3
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
# from app.database import seed_database  # Import only the function
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





# Load environment variables from .env
load_dotenv()

BASE_TOPIC = os.getenv("BASE_TOPIC", "Eason/ece140/sensors")
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL", "http://localhost:6543/api/temperature")
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com ")

# Track the last time a request was sent
last_sent_time = 0

def on_connect(client, userdata, flags, rc, properties=None):
    """Callback function when connected to MQTT broker"""
    if rc == 0:
        print(f"[MQTT] Connected successfully! Subscribing to: {BASE_TOPIC}/readings")
        client.subscribe(f"{BASE_TOPIC}/readings")
    else:
        print(f"[MQTT] Connection failed with code {rc}")




def on_message(client, userdata, msg):
    """Handles incoming MQTT messages and sends data to the web server."""
    global last_sent_time
    try:
        payload = msg.payload.decode("utf-8")
        print(f"\n[DEBUG] Raw MQTT message received: {payload}")

        data = json.loads(payload)
        temperature = data.get("temperature")

        if temperature is None:
            print("[ERROR] 'temperature' field missing in MQTT message")
            return

        current_time = time.time()
        if current_time - last_sent_time < 5:  # Enforce 5-second delay
            print("[MQTT] Skipping request to avoid spamming")
            return

        last_sent_time = current_time

        formatted_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        post_data = {
            "value": temperature,
            "unit": "C",
            "timestamp": formatted_timestamp
        }

        print(f"[DEBUG] Sending data to FastAPI: {post_data}")

        response = requests.post(WEB_SERVER_URL, json=post_data, timeout=5)

        print(f"[DEBUG] FastAPI Response Code: {response.status_code}")
        print(f"[DEBUG] FastAPI Response Body: {response.text}")

        if response.status_code == 200:
            print(f"[MQTT] Data sent successfully! Stored value: {temperature}")
        else:
            print(f"[ERROR] POST request failed: {response.status_code} - {response.text}")

    except Exception as e:
        print(f"[ERROR] Error processing MQTT message: {e}")




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

    # Start list