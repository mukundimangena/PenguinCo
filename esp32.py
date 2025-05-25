# routers/esp32.py
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from models import (
    SensorData, SensorReading, BatchSensorData, 
    SensorResponse, APIResponse, DeviceInfo
)
from database import SessionLocal
import threading

db_lock = threading.Lock()

router = APIRouter(prefix="/api")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/sensor-data", response_model=APIResponse, tags=["ESP32 Sensors"])
async def receive_sensor_data(reading: SensorReading, db: Session = Depends(get_db)):
    """Receive sensor data from ESP32"""
    try:
        # Create SQLAlchemy model instance
        db_reading = SensorData(
            device_id=reading.device_id,
            sensor_type=reading.sensor_type,
            value=reading.value,
            location=reading.location,
            timestamp=datetime.utcnow()
        )
        
        with db_lock:
            db.add(db_reading)
            db.commit()
            db.refresh(db_reading)

        
        return APIResponse(
            status="success",
            message="Data received and stored",
            id=db_reading.id
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sensor-data/batch", response_model=APIResponse, tags=["ESP32 Sensors"])
async def receive_batch_data(batch_data: BatchSensorData, db: Session = Depends(get_db)):
    """Receive multiple sensor readings at once"""
    try:
        if not batch_data.readings:
            raise HTTPException(status_code=400, detail="No readings provided")
        
        inserted_ids = []
        
        for reading in batch_data.readings:
            db_reading = SensorData(
                device_id=reading.device_id,
                sensor_type=reading.sensor_type,
                value=reading.value,
                location=reading.location,
                timestamp=datetime.utcnow()
            )
            db.add(db_reading)
            db.flush()  # Flush to get the ID without committing
            inserted_ids.append(db_reading.id)
        with db_lock:
            db.commit()
        
        return APIResponse(
            status="success",
            message=f"Stored {len(batch_data.readings)} readings",
            ids=inserted_ids
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensor-data", response_model=List[SensorResponse], tags=["ESP32 Sensors"])
async def get_sensor_data(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    sensor_type: Optional[str] = Query(None, description="Filter by sensor type"),
    limit: int = Query(100, description="Maximum number of records to return"),
    db: Session = Depends(get_db)
):
    """Get sensor data with optional filtering"""
    try:
        query = db.query(SensorData)
        
        if device_id:
            query = query.filter(SensorData.device_id == device_id)
        
        if sensor_type:
            query = query.filter(SensorData.sensor_type == sensor_type)
        
        readings = query.order_by(SensorData.timestamp.desc()).limit(limit).all()
        
        # Convert SQLAlchemy models to Pydantic models
        return [
            SensorResponse(
                id=reading.id,
                device_id=reading.device_id,
                sensor_type=reading.sensor_type,
                value=reading.value,
                timestamp=reading.timestamp.isoformat(),
                location=reading.location or "unknown"
            )
            for reading in readings
        ]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensor-data/latest/{device_id}", response_model=SensorResponse, tags=["ESP32 Sensors"])
async def get_latest_reading(
    device_id: str, 
    sensor_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get the latest reading for a specific device"""
    try:
        query = db.query(SensorData).filter(SensorData.device_id == device_id)
        
        if sensor_type:
            query = query.filter(SensorData.sensor_type == sensor_type)
        
        reading = query.order_by(SensorData.timestamp.desc()).first()
        
        if not reading:
            raise HTTPException(status_code=404, detail="No data found for this device")
        
        return SensorResponse(
            id=reading.id,
            device_id=reading.device_id,
            sensor_type=reading.sensor_type,
            value=reading.value,
            timestamp=reading.timestamp.isoformat(),
            location=reading.location or "unknown"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/esp32/devices", response_model=List[DeviceInfo], tags=["ESP32 Sensors"])
async def get_esp32_devices(db: Session = Depends(get_db)):
    """Get list of all ESP32 devices that have sent data"""
    try:
        # Using raw SQL for aggregation (you could also use SQLAlchemy's func)
        from sqlalchemy import text
        
        query = text("""
            SELECT device_id, location, 
                   COUNT(*) as total_readings,
                   MAX(timestamp) as last_seen
            FROM sensor_data 
            GROUP BY device_id, location
            ORDER BY last_seen DESC
        """)
        
        result = db.execute(query).fetchall()
        
        devices = []
        for row in result:
            devices.append(DeviceInfo(
                device_id=row.device_id,
                location=row.location or "unknown",
                total_readings=row.total_readings,
                last_seen=str(row.last_seen)
            ))
        
        return devices
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))