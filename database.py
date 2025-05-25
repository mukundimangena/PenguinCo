# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


DATABASE_URL = "sqlite:///./penguinco.db"

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False, "timeout": 30}  # Wait up to 30 seconds for the lock
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
