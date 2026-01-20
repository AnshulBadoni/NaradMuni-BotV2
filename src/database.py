# src/database.py
import ssl
import logging
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import declarative_base, sessionmaker
from contextlib import contextmanager
import enum
from .config import config

logger = logging.getLogger(__name__)

Base = declarative_base()

class EmailStatus(enum.Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    DONE = "DONE"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"

class Email(Base):
    __tablename__ = "emails"
    
    message_id = Column(String(255), primary_key=True)
    thread_id = Column(String(255), nullable=True)
    subject = Column(Text, nullable=True)
    sender = Column(String(500), nullable=True)
    snippet = Column(Text, nullable=True)
    received_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    status = Column(SQLEnum(EmailStatus), default=EmailStatus.RECEIVED)
    classification = Column(String(50), nullable=True)
    error_message = Column(Text, nullable=True)

# Create engine with SSL
def get_engine():
    if not config.DATABASE_URL:
        raise ValueError("DATABASE_URL not set")
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    engine = create_engine(
        config.DATABASE_URL,
        connect_args={"ssl": ssl_context},
        pool_pre_ping=True,
        pool_recycle=3600
    )
    return engine

engine = None
SessionLocal = None

def init_db():
    global engine, SessionLocal
    engine = get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database initialized")

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def email_exists(message_id: str) -> bool:
    with get_db() as db:
        return db.query(Email).filter(Email.message_id == message_id).first() is not None

def save_email(message_id: str, thread_id: str, subject: str, sender: str, snippet: str):
    with get_db() as db:
        email = Email(
            message_id=message_id,
            thread_id=thread_id,
            subject=subject,
            sender=sender,
            snippet=snippet,
            status=EmailStatus.PROCESSING,
            received_at=datetime.utcnow()
        )
        db.add(email)

def update_email_status(message_id: str, status: EmailStatus, classification: str = None, error: str = None):
    with get_db() as db:
        email = db.query(Email).filter(Email.message_id == message_id).first()
        if email:
            email.status = status
            email.processed_at = datetime.utcnow()
            if classification:
                email.classification = classification
            if error:
                email.error_message = error