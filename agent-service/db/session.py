"""
SQLAlchemy engine + session setup. Reads DATABASE_URL from .env —
never hardcode a connection string here (guardrail #7 from the README).
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set — copy .env.example to .env first.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_session():
    """FastAPI dependency — yields a session, always closes it after."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
