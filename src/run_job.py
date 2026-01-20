# src/run_job.py
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 50)
    logger.info("📧 JOB EMAIL NOTIFIER")
    logger.info(f"⏰ Run started at {datetime.utcnow().isoformat()}")
    logger.info("=" * 50)
    
    # Import here to ensure env vars are loaded
    from .config import config
    from .database import init_db, email_exists, save_email, update_email_status, EmailStatus
    from .gmail_client import GmailClient
    from .classifier import classify_email
    from .telegram_notifier import send_telegram
    
    stats = {"processed": 0, "notified": 0, "skipped": 0, "failed": 0}
    
    try:
        # Initialize
        init_db()
        gmail = GmailClient()
        
        # Fetch unread emails
        messages = gmail.get_unread_messages(config.MAX_EMAILS_PER_RUN)
        logger.info(f"📬 Found {len(messages)} unread emails")
        
        if not messages:
            logger.info("✅ No new emails to process")
            return 0
        
        # Process each email
        for msg in messages:
            message_id = msg['id']
            
            # Skip if already processed
            if email_exists(message_id):
                logger.info(f"⏭️  Already processed: {message_id[:12]}...")
                continue
            
            # Get full details
            details = gmail.get_message_details(message_id)
            if not details:
                logger.error(f"❌ Failed to fetch: {message_id}")
                stats["failed"] += 1
                continue
            
            subject = details.get('subject', 'No Subject')
            logger.info(f"\n📨 Processing: {subject[:50]}...")
            
            # Save to database
            save_email(
                message_id=message_id,
                thread_id=details.get('thread_id'),
                subject=subject,
                sender=details.get('from'),
                snippet=details.get('snippet')
            )
            
            # Classify
            result = classify_email(
                subject=subject,
                body=details.get('body', ''),
                sender=details.get('from', '')
            )
            
            label = result["label"]
            source = result["source"]
            confidence = result["confidence"]
            is_job = result["is_job"]
            
            source_icon = "🤖" if source == "AI" else "⚡"
            logger.info(f"   {source_icon} {label} ({confidence:.0%})")
            
            if is_job:
                # Prepare notification data
                details['classification'] = label
                details['source'] = source
                details['confidence'] = confidence
                details['matches'] = result.get('matches', [])
                
                # Send Telegram
                if send_telegram(details):
                    update_email_status(message_id, EmailStatus.DONE, label)
                    stats["notified"] += 1
                    logger.info(f"   ✅ Notification sent!")
                else:
                    update_email_status(message_id, EmailStatus.FAILED, label, "Telegram failed")
                    stats["failed"] += 1
            else:
                update_email_status(message_id, EmailStatus.SKIPPED, "OTHER")
                stats["skipped"] += 1
                logger.info(f"   ⏭️  Skipped (not job-related)")
            
            stats["processed"] += 1
        
        # Summary
        logger.info("")
        logger.info("=" * 50)
        logger.info("📊 RUN SUMMARY")
        logger.info("=" * 50)
        logger.info(f"   📨 Processed: {stats['processed']}")
        logger.info(f"   ✅ Notified:  {stats['notified']}")
        logger.info(f"   ⏭️  Skipped:   {stats['skipped']}")
        logger.info(f"   ❌ Failed:    {stats['failed']}")
        logger.info("=" * 50)
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())