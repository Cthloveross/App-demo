
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





# Load environment variables from .env
load_dotenv()

BASE_TOPIC = os.getenv("BASE_TOPIC", "Eason/ece140/sensors")
WEB_SERVER_URL = os.getenv("WEB_SERVER_URL", "http://localhost:6543/api/temperature")
MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")

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