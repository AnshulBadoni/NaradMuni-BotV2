# src/config.py
import os

class Config:
    # Database (Aiven MySQL)
    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    
    # Gmail
    GMAIL_CREDENTIALS = os.environ.get("GMAIL_CREDENTIALS", "")  # JSON string
    GMAIL_TOKEN = os.environ.get("GMAIL_TOKEN", "")  # JSON string
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
    
    # Pollination AI (optional)
    POLLINATION_API_KEY = os.environ.get("POLLINATION_API_KEY", "")
    
    # Processing
    MAX_EMAILS_PER_RUN = int(os.environ.get("MAX_EMAILS_PER_RUN", "20"))

config = Config()