# src/gmail_client.py
import os
import json
import base64
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from .config import config

logger = logging.getLogger(__name__)

class GmailClient:
    def __init__(self):
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate using credentials from environment variables"""
        creds = None
        
        # Load token from environment (JSON string)
        if config.GMAIL_TOKEN:
            try:
                token_data = json.loads(config.GMAIL_TOKEN)
                creds = Credentials.from_authorized_user_info(token_data)
            except Exception as e:
                logger.error(f"Failed to load token: {e}")
        
        # Refresh if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("🔄 Token refreshed")
                # Log new token (you may want to update the secret)
                new_token = creds.to_json()
                logger.info(f"📝 New token (update GMAIL_TOKEN secret): {new_token[:100]}...")
            except Exception as e:
                logger.error(f"Failed to refresh token: {e}")
                raise
        
        if not creds or not creds.valid:
            raise ValueError("Invalid Gmail credentials. Run setup_token.py locally first.")
        
        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("✅ Gmail authenticated")
    
    def get_unread_messages(self, max_results: int = 20) -> list:
        """Fetch unread messages from inbox"""
        try:
            results = self.service.users().messages().list(
                userId='me',
                labelIds=['INBOX', 'UNREAD'],
                maxResults=max_results
            ).execute()
            
            return results.get('messages', [])
        except Exception as e:
            logger.error(f"Error fetching messages: {e}")
            return []
    
    def get_message_details(self, message_id: str) -> dict:
        """Get full message details"""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message.get('payload', {}).get('headers', [])
            header_dict = {h['name'].lower(): h['value'] for h in headers}
            
            body = self._get_body(message.get('payload', {}))
            
            return {
                'id': message['id'],
                'thread_id': message.get('threadId'),
                'subject': header_dict.get('subject', 'No Subject'),
                'from': header_dict.get('from', 'Unknown'),
                'date': header_dict.get('date'),
                'snippet': message.get('snippet', ''),
                'body': body,
                'labels': message.get('labelIds', [])
            }
        except Exception as e:
            logger.error(f"Error getting message {message_id}: {e}")
            return None
    
    def _get_body(self, payload: dict) -> str:
        """Extract email body from payload"""
        body = ""
        
        if 'body' in payload and payload['body'].get('data'):
            body = base64.urlsafe_b64decode(
                payload['body']['data']
            ).decode('utf-8', errors='ignore')
        elif 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if part['body'].get('data'):
                        body = base64.urlsafe_b64decode(
                            part['body']['data']
                        ).decode('utf-8', errors='ignore')
                        break
                elif 'parts' in part:
                    body = self._get_body(part)
                    if body:
                        break
        
        return body[:5000]