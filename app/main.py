import logging
import os
import uuid
import secrets
import uvicorn
import paho.mqtt.client as mqtt
from datetime import datetime
import sqlite3
from dotenv import load_dotenv
from typing import Optional, Generator
import requests
from fastapi import (
    FastAPI, HTTPException, Query, Depends, Request, Form, Response, Cookie
)
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from app.database import (
    get_db, get_mysql_connection, get_user_by_username, create_user, create_session,
    get_session, delete_session, register_device, verify_password, ensure_mysql_tables,
    ensure_sqlite_tables, get_user_by_email
)

# from fastapi.middleware.cors import CORSMiddleware

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # Allow all origins (you can restrict this)
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Load environment variables
load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🌱 Initialize database tables
logger.info("🔧 Setting up MySQL and SQLite databases...")
ensure_mysql_tables()
ensure_sqlite_tables()
logger.info("✅ Database setup complete.")

# ------------------- FastAPI Setup -------------------
app = FastAPI()

# Session management middleware
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))

# Static & Template Setup
static_path = os.path.abspath("app/static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

templates = Jinja2Templates(directory=os.path.abspath("app/templates"))

# ------------------- Allowed Sensor Types -------------------
SENSOR_TYPES = {"temperature", "humidity", "light"}

# ------------------- Pydantic Models -------------------
class SensorData(BaseModel):
    """Schema for inserting/updating sensor data"""
    value: float
    unit: str = "C"
    timestamp: Optional[str] = None

class UserAuth(BaseModel):
    """Schema for user authentication"""
    username: str
    password: str

class DeviceRegistration(BaseModel):
    """Schema for registering an IoT device"""
    device_name: str
    device_id: str

# ------------------- Routes for Rendering HTML Pages -------------------
@app.get("/")
def read_root(request: Request):
    """Render the home page"""
    return templates.TemplateResponse("index.html", {"request": request})



@app.get("/dashboard")
def dashboard(request: Request, sessionId: Optional[str] = Cookie(None)):
    """Render the dashboard template if the user is logged in and has registered a device."""
    print(f"DEBUG: sessionId from Cookie (Dashboard): {sessionId}")  # ✅ Debugging
    if not sessionId:
        return RedirectResponse(url="/login", status_code=303)

    session = get_session(sessionId)

    # print(f"DEBUG: Session from DB (Dashboard): {session}")  # ✅ Debugging
    if not session:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session["user_id"]

    # ✅ Check if the user has a registered device
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS device_count FROM devices WHERE user_id = %s", (user_id,))
    device_data = cursor.fetchone()
    cursor.close()
    conn.close()

    if device_data["device_count"] == 0:
        # print("DEBUG: User has no registered devices, redirecting to /register_device")
        return RedirectResponse(url="/register_device", status_code=302)

    return templates.TemplateResponse("dashboard.html", {"request": request})



@app.get("/profile")
def profile_page(request: Request, sessionId: Optional[str] = Cookie(None)):
    """Displays the profile page with user-specific devices."""
    print(f"DEBUG: sessionId from Cookie (Profile): {sessionId}")  # ✅ Debugging

    if not sessionId:
        print("DEBUG: No sessionId found, redirecting to /login")  
        return RedirectResponse(url="/login", status_code=303)

    # Check session in DB
    session = get_session(sessionId)
    print(f"DEBUG: Session from DB (Profile): {session}")  

    if not session:
        print("DEBUG: No valid session found, redirecting to /login")
        return RedirectResponse(url="/login", status_code=303)

    user_id = session["user_id"]

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM devices WHERE user_id = %s", (user_id,))
    devices = cursor.fetchall()

    cursor.close()
    conn.close()

    return templates.TemplateResponse("profile.html", {"request": request, "devices": devices})


API_URL = "https://ece140-wi25-api.frosty-sky-f43d.workers.dev/api/v1/ai/complete"
HEADERS = {
    "accept": "application/json",
    "email": "tic001@ucsd.edu",  # Replace with your email
    "pid": "A16875083",          # Replace with your PID
    "Content-Type": "application/json"
}

DATABASE_PATH = "sensor_data.db"

def get_past_temperature_data():
    """Fetches past temperature data from the SQLite database."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        
        # Get the last 5 temperature records
        cursor.execute("SELECT value, timestamp FROM sensor_data WHERE sensor_type = 'temperature' ORDER BY timestamp DESC LIMIT 5")
        rows = cursor.fetchall()
        conn.close()

        # Format the temperature history as text
        history = "\n".join([f"{timestamp}: {value}°C" for value, timestamp in rows])
        return history if history else "No temperature data available."

    except Exception as e:
        return f"Error retrieving past temperature data: {str(e)}"

@app.get("/api/recommendation")
def get_ai_recommendation(prompt: str = Query("What should I eat tonight?")):
    """Fetches temperature history and sends it along with the user's prompt to the AI API."""
    try:
        temperature_history = get_past_temperature_data()  # Get past temperature readings

        full_prompt = f"{prompt}\n\nRecent Temperature Data:\n{temperature_history}"
        print(f"[DEBUG] Sending to AI API:\n{full_prompt}")

        payload = {"prompt": full_prompt}
        response = requests.post(API_URL, json=payload, headers=HEADERS)

        if response.status_code == 200:
            data = response.json()
            ai_response = data["result"]["response"]
            return {"recommendation": ai_response}
        else:
            return {"error": f"API request failed with status {response.status_code}"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calling AI API: {str(e)}")

# ------------------- User Authentication (MySQL) -------------------
@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})



@app.post("/auth/signup")
async def signup(
    request: Request, 
    response: Response, 
    username: str = Form(...), 
    email: str = Form(...), 
    password: str = Form(...), 
    location: Optional[str] = Form(None)
):
    """Handles user registration, starts a session, and redirects to dashboard."""
    
    existing_user = get_user_by_username(username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    # ✅ Ensure user_id is an integer, not a boolean
    user_id = create_user(username, email, password, location)
    if not user_id:
        raise HTTPException(status_code=500, detail="User creation failed")

    # ✅ Create a session with the actual user ID
    session_id = create_session(user_id)

    # ✅ Set session cookie
    response = RedirectResponse(url="/dashboard", status_code=302)  # Redirect to dashboard
    response.set_cookie(key="sessionId", value=session_id, httponly=True)

    return response

@app.post("/auth/login")
async def login(
    request: Request, 
    response: Response, 
    email: str = Form(...), 
    password: str = Form(...)
):
    """Validates user login, starts a session, and redirects based on device registration."""
    
    user = get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not verify_password(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # ✅ Create a session
    session_id = create_session(user["id"])
    response.set_cookie(key="sessionId", value=session_id, httponly=True)

    # ✅ Check if the user has registered a device
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS device_count FROM devices WHERE user_id = %s", (user["id"],))
    device_data = cursor.fetchone()
    cursor.close()
    conn.close()

    device_count = device_data["device_count"]

    print(f"DEBUG: User {email} has {device_count} devices registered.")

    if device_count == 0:
        # 🚀 Redirect to register device page if no devices are registered
        print("DEBUG: Redirecting to /register_device")
        return RedirectResponse(url="/register_device", status_code=302)

    # ✅ Redirect to dashboard if user has at least one device
    return RedirectResponse(url="/dashboard", status_code=302)




@app.post("/auth/logout")
async def logout(response: Response, sessionId: Optional[str] = Cookie(None)):
    """Logs out the user by deleting the session."""
    if sessionId:
        delete_session(sessionId)
        response.delete_cookie("sessionId")
    return RedirectResponse(url="/login", status_code=302)

# ------------------- IoT Device Management -------------------

@app.get("/register_device")
def register_device_page(request: Request, sessionId: Optional[str] = Cookie(None)):
    """Render the device registration page if logged in"""
    print(f"DEBUG: sessionId from Cookie (Register Device): {sessionId}")  # ✅ Debugging

    if not sessionId:
        return RedirectResponse(url="/login", status_code=303)

    # ✅ Retrieve user_id from session
    session = get_session(sessionId)
    if not session:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session["user_id"]

    print(f"DEBUG: Extracted user_id from session (Register Device): {user_id}")

    return templates.TemplateResponse("register_device.html", {"request": request, "user_id": user_id})



@app.post("/register_device")
def register_device(
    request: Request,
    response: Response,
    device_name: str = Form(...),
    device_id: str = Form(...),
    sessionId: Optional[str] = Cookie(None)  # ✅ Use sessionId from cookies
):
    """Registers a new IoT device for the logged-in user."""
    print(f"DEBUG: sessionId from Cookie (Register Device POST): {sessionId}")  # ✅ Debugging

    if not sessionId:
        print("DEBUG: No sessionId found, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    # ✅ Retrieve user_id from session
    session = get_session(sessionId)
    if not session:
        print("DEBUG: Invalid session, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    user_id = session["user_id"]
    print(f"DEBUG: Registering device for user_id: {user_id}")

    conn = get_mysql_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO devices (user_id, device_name, device_id) VALUES (%s, %s, %s)",
            (user_id, device_name, device_id)
        )
        conn.commit()
    except Exception as e:
        print(f"DEBUG: Device registration error: {e}")
        raise HTTPException(status_code=400, detail=f"Device registration failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

    print("DEBUG: Device registered successfully")
    return RedirectResponse(url="/dashboard", status_code=303)

@app.delete("/delete_device/{device_id}")
def delete_device(device_id: str, sessionId: Optional[str] = Cookie(None)):
    """Deletes a device if it belongs to the logged-in user."""
    print(f"DEBUG: sessionId from Cookie (Delete Device): {sessionId}")  

    if not sessionId:
        print("DEBUG: No sessionId found, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    session = get_session(sessionId)
    if not session:
        print("DEBUG: Invalid session, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    user_id = session["user_id"]
    print(f"DEBUG: Deleting device {device_id} for user_id {user_id}")

    conn = get_mysql_connection()
    cursor = conn.cursor()

    # Ensure the device belongs to the logged-in user
    cursor.execute("SELECT * FROM devices WHERE device_id = %s AND user_id = %s", (device_id, user_id))
    device = cursor.fetchone()

    if not device:
        print("DEBUG: Device not found or does not belong to user.")
        raise HTTPException(status_code=403, detail="Unauthorized to delete this device")

    try:
        cursor.execute("DELETE FROM devices WHERE device_id = %s AND user_id = %s", (device_id, user_id))
        conn.commit()
        print(f"DEBUG: Device {device_id} deleted successfully")
    except Exception as e:
        print(f"DEBUG: Error deleting device: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete device")
    finally:
        cursor.close()
        conn.close()

    return Response(status_code=200)



# ------------------- Clothes Management -------------------

@app.delete("/delete_clothes/{item_id}")
def delete_clothes(item_id: str, sessionId: Optional[str] = Cookie(None)):
    """Deletes a clothing item if it belongs to the logged-in user."""
    print(f"DEBUG: sessionId from Cookie (Delete Clothes): {sessionId}")

    if not sessionId:
        print("DEBUG: No sessionId found, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    session = get_session(sessionId)
    if not session:
        print("DEBUG: Invalid session, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    user_id = session["user_id"]
    print(f"DEBUG: Deleting clothes {item_id} for user_id {user_id}")

    conn = get_mysql_connection()
    cursor = conn.cursor()

    # Ensure the clothing item belongs to the logged-in user
    cursor.execute("SELECT * FROM wardrobe WHERE item_id = %s AND user_id = %s", (item_id, user_id))
    clothes = cursor.fetchone()

    if not clothes:
        print("DEBUG: Clothes not found or do not belong to user.")
        raise HTTPException(status_code=403, detail="Unauthorized to delete this clothing item")

    try:
        cursor.execute("DELETE FROM wardrobe WHERE item_id = %s AND user_id = %s", (item_id, user_id))
        conn.commit()
        print(f"DEBUG: Clothes {item_id} deleted successfully")
    except Exception as e:
        print(f"DEBUG: Error deleting clothes: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete clothes")
    finally:
        cursor.close()
        conn.close()

    return Response(status_code=200)



@app.get("/wardrobe")
def wardrobe_page(request: Request, sessionId: Optional[str] = Cookie(None)):
    """Displays the wardrobe page with user-specific clothes."""
    print(f"DEBUG: sessionId from Cookie (Wardrobe): {sessionId}")

    if not sessionId:
        return RedirectResponse(url="/login", status_code=303)

    session = get_session(sessionId)
    if not session:
        return RedirectResponse(url="/login", status_code=303)

    user_id = session["user_id"]

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT id, item_name, item_id, color, created_at FROM wardrobe WHERE user_id = %s", (user_id,))
    wardrobe = cursor.fetchall()

    cursor.close()
    conn.close()

    print(f"DEBUG: Fetched wardrobe items: {wardrobe}")

    return templates.TemplateResponse("wardrobe.html", {"request": request, "wardrobe": wardrobe})


@app.get("/add_clothes")
def add_clothes_page(request: Request, sessionId: Optional[str] = Cookie(None)):
    """Render the clothes registration page if logged in."""
    print(f"DEBUG: sessionId from Cookie (Add Clothes Page): {sessionId}")

    if not sessionId:
        return RedirectResponse(url="/login", status_code=303)

    # ✅ Retrieve user_id from session
    session = get_session(sessionId)
    if not session:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse("add_clothes.html", {"request": request})


@app.post("/add_clothes")
def add_clothes(
    request: Request,
    response: Response,
    item_name: str = Form(...),
    item_id: str = Form(...),  # ✅ Ensure item_id is captured
    color: str = Form(...),
    sessionId: Optional[str] = Cookie(None)
):
    """Registers a new clothing item for the logged-in user."""
    print(f"DEBUG: sessionId from Cookie (Register Clothes POST): {sessionId}")

    if not sessionId:
        print("DEBUG: No sessionId found, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    session = get_session(sessionId)
    if not session:
        print("DEBUG: Invalid session, returning 401 Unauthorized")
        raise HTTPException(status_code=401, detail="Not logged in")

    user_id = session["user_id"]
    print(f"DEBUG: Registering clothes for user_id: {user_id}")

    conn = get_mysql_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO wardrobe (user_id, item_name, item_id, color) VALUES (%s, %s, %s, %s)",
            (user_id, item_name, item_id, color)
        )
        conn.commit()
    except Exception as e:
        print(f"DEBUG: Clothes registration error: {e}")
        raise HTTPException(status_code=400, detail=f"Clothes registration failed: {str(e)}")
    finally:
        cursor.close()
        conn.close()

    print("DEBUG: Clothes registered successfully")
    return RedirectResponse(url="/wardrobe", status_code=303)


# ------------------- Sensor Data Endpoints (SQLite) -------------------
@app.get("/api/{sensor_type}/count")
def get_sensor_count(sensor_type: str):
    """Get the count of rows for a given sensor type."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM sensor_data WHERE sensor_type = ?", (sensor_type,))
    count = cursor.fetchone()[0]
    return {"count": count}




@app.get("/api/{sensor_type}")
def get_sensor_data(sensor_type: str):
    """Fetch all sensor data"""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    conn = get_db()  # ✅ Get fresh connection
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM sensor_data WHERE sensor_type = ?", (sensor_type,))
        data = cursor.fetchall()
        return [dict(row) for row in data]  # ✅ Ensures dictionary response
    except Exception as e:
        print(f"Database error: {e}")  # ✅ Debugging step
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        conn.close()  # ✅ Always close the connection




@app.post("/api/{sensor_type}")
def insert_sensor_data(sensor_type: str, data: SensorData):
    """Insert new sensor data."""
    if sensor_type not in SENSOR_TYPES:
        raise HTTPException(status_code=404, detail="Invalid sensor type")

    timestamp = data.timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sensor_data (sensor_type, value, unit, timestamp) VALUES (?, ?, ?, ?)",
        (sensor_type, data.value, data.unit, timestamp)
    )
    conn.commit()
    return {"message": "Data inserted successfully"}

# ------------------- Run FastAPI Server -------------------
if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=6543, reload=True)
