# src/telegram_notifier.py
import re
import logging
import requests
from .config import config

logger = logging.getLogger(__name__)

def send_telegram(email_data: dict) -> bool:
    """Send beautiful notification to Telegram"""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        logger.error("Telegram credentials not configured")
        return False

    try:
        message = format_message(email_data)
        
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info("📱 Notification sent!")
            return True
        else:
            logger.error(f"Telegram error: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Notification failed: {e}")
        return False

def format_message(email_data: dict) -> str:
    classification = email_data.get('classification', 'JOB')
    source = email_data.get('source', 'RULES')
    confidence = email_data.get('confidence', 0.0)
    matches = email_data.get('matches', [])
    
    if classification == "HR":
        header = "🔥 <b>HIGH PRIORITY — HR Contact!</b>"
        priority_bar = "🟢🟢🟢🟢🟢"
        type_emoji = "👔"
    else:
        header = "💼 <b>New Job Alert</b>"
        priority_bar = "🟡🟡🟡⚪⚪"
        type_emoji = "📋"
    
    source_badge = "🤖 AI" if source == "AI" else "⚡ Rules"
    conf_percent = int(confidence * 100)
    conf_bar = "▓" * int(confidence * 10) + "░" * (10 - int(confidence * 10))
    
    subject = escape_html(email_data.get('subject', 'No Subject'))
    sender = escape_html(email_data.get('from', 'Unknown'))
    date = email_data.get('date', 'Unknown')
    
    snippet = email_data.get('snippet', '')
    snippet = re.sub(r'https?://\S+', '[link]', snippet)
    snippet = re.sub(r'\s+', ' ', snippet)
    snippet = escape_html(snippet[:250])
    
    matches_text = ""
    if matches:
        matches_text = f"\n🏷️ <b>Matched:</b> " + ", ".join([f"<code>{m}</code>" for m in matches[:4]])
    
    return f"""
{header}
{priority_bar}

{type_emoji} <b>Type:</b> {classification}
{source_badge} • {conf_percent}% confident
{conf_bar}

━━━━━━━━━━━━━━━━━━━━

📧 <b>From:</b>
{sender}

📌 <b>Subject:</b>
{subject}

📝 <b>Preview:</b>
<i>{snippet}...</i>
{matches_text}

━━━━━━━━━━━━━━━━━━━━

🕐 {date}
    """.strip()

def escape_html(text: str) -> str:
    if not text:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')