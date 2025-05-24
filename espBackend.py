# Add these imports to your existing FastAPI app
from fastapi import HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import sqlite3
from datetime import datetime
from main import app

# Add these Pydantic models to your existing models
class SensorReading(BaseModel):
    device_id: str
    sensor_type: str
    value: float
    location: Optional[str] = "unknown"

class BatchSensorData(BaseModel):
    readings: List[SensorReading]

class SensorResponse(BaseModel):
    id: int
    device_id: str
    sensor_type: str
    value: float
    timestamp: str
    location: str

class APIResponse(BaseModel):
    status: str
    message: str
    id: Optional[int] = None
    ids: Optional[List[int]] = None

# Database configuration - adjust path as needed
DATABASE = 'penguinco.db'

def init_sensor_db():
    """Initialize the sensor database table"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            sensor_type TEXT NOT NULL,
            value REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            location TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def get_sensor_db_connection():
    """Get sensor database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Add this to your existing startup event or create one if you don't have it
@app.on_event("startup")
async def startup_event():
    """Add this to your existing startup event"""
    init_sensor_db()
    # ... your existing startup code

# Add these route handlers to your existing FastAPI app

@app.post("/api/sensor-data", response_model=APIResponse, tags=["ESP32 Sensors"])
async def receive_sensor_data(reading: SensorReading):
    """Receive sensor data from ESP32"""
    try:
        conn = get_sensor_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO sensor_data (device_id, sensor_type, value, location)
            VALUES (?, ?, ?, ?)
        ''', (
            reading.device_id,
            reading.sensor_type,
            reading.value,
            reading.location
        ))
        
        conn.commit()
        row_id = cursor.lastrowid
        conn.close()
        
        return APIResponse(
            status="success",
            message="Data received and stored",
            id=row_id
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/sensor-data/batch", response_model=APIResponse, tags=["ESP32 Sensors"])
async def receive_batch_data(batch_data: BatchSensorData):
    """Receive multiple sensor readings at once"""
    try:
        if not batch_data.readings:
            raise HTTPException(status_code=400, detail="No readings provided")
        
        conn = get_sensor_db_connection()
        cursor = conn.cursor()
        
        inserted_ids = []
        for reading in batch_data.readings:
            cursor.execute('''
                INSERT INTO sensor_data (device_id, sensor_type, value, location)
                VALUES (?, ?, ?, ?)
            ''', (
                reading.device_id,
                reading.sensor_type,
                reading.value,
                reading.location
            ))
            inserted_ids.append(cursor.lastrowid)
        
        conn.commit()
        conn.close()
        
        return APIResponse(
            status="success",
            message=f"Stored {len(batch_data.readings)} readings",
            ids=inserted_ids
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sensor-data", response_model=List[SensorResponse], tags=["ESP32 Sensors"])
async def get_sensor_data(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_type: Optional[str] = Query(None, description="Filter by sensor type"),
    limit: int = Query(100, description="Maximum number of records to return")
):
    """Get sensor data with optional filtering"""
    try:
        conn = get_sensor_db_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM sensor_data WHERE 1=1'
        params = []
        
        if device_id:
            query += ' AND device_id = ?'
            params.append(device_id)
        
        if sensor_type:
            query += ' AND sensor_type = ?'
            params.append(sensor_type)
        
        query += f' ORDER BY timestamp DESC LIMIT {limit}'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        data = []
        for row in rows:
            data.append(SensorResponse(
                id=row['id'],
                device_id=row['device_id'],
                sensor_type=row['sensor_type'],
                value=row['value'],
                timestamp=row['timestamp'],
                location=row['location']
            ))
        
        return data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sensor-data/latest/{device_id}", response_model=SensorResponse, tags=["ESP32 Sensors"])
async def get_latest_reading(device_id: str, sensor_type: Optional[str] = None):
    """Get the latest reading for a specific device"""
    try:
        conn = get_sensor_db_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM sensor_data WHERE device_id = ?'
        params = [device_id]
        
        if sensor_type:
            query += ' AND sensor_type = ?'
            params.append(sensor_type)
        
        query += ' ORDER BY timestamp DESC LIMIT 1'
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="No data found for this device")
        
        return SensorResponse(
            id=row['id'],
            device_id=row['device_id'],
            sensor_type=row['sensor_type'],
            value=row['value'],
            timestamp=row['timestamp'],
            location=row['location']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/esp32/devices", tags=["ESP32 Sensors"])
async def get_esp32_devices():
    """Get list of all ESP32 devices that have sent data"""
    try:
        conn = get_sensor_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT DISTINCT device_id, location, 
                   COUNT(*) as total_readings,
                   MAX(timestamp) as last_seen
            FROM sensor_data 
            GROUP BY device_id, location
            ORDER BY last_seen DESC
        ''')
        
        rows = cursor.fetchall()
        conn.close()
        
        devices = []
        for row in rows:
            devices.append({
                "device_id": row['device_id'],
                "location": row['location'],
                "total_readings": row['total_readings'],
                "last_seen": row['last_seen']
            })
        
        return devices
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))