# setup_token.py
"""
Run this LOCALLY to authenticate Gmail and get the token.
Then copy the token to GitHub Secrets.
"""
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def main():
    print("=" * 50)
    print("GMAIL TOKEN SETUP")
    print("=" * 50)
    
    creds = None
    
    # Check existing token
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing token...")
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"❌ {CREDENTIALS_FILE} not found!")
                print("   Download it from Google Cloud Console")
                return
            
            print("🌐 Opening browser for authentication...")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save token
        with open(TOKEN_FILE, 'w') as f:
            f.write(creds.to_json())
        print(f"✅ Token saved to {TOKEN_FILE}")
    
    # Read files for secrets
    print("\n" + "=" * 50)
    print("📋 COPY THESE TO GITHUB SECRETS")
    print("=" * 50)
    
    # GMAIL_CREDENTIALS
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_content = f.read()
    print("\n🔑 GMAIL_CREDENTIALS:")
    print("-" * 40)
    print(creds_content)
    
    # GMAIL_TOKEN
    with open(TOKEN_FILE, 'r') as f:
        token_content = f.read()
    print("\n🔑 GMAIL_TOKEN:")
    print("-" * 40)
    print(token_content)
    
    print("\n" + "=" * 50)
    print("✅ Setup complete!")
    print("=" * 50)
    print("\nNext steps:")
    print("1. Go to GitHub → Settings → Secrets → Actions")
    print("2. Add these secrets:")
    print("   - GMAIL_CREDENTIALS (paste the JSON above)")
    print("   - GMAIL_TOKEN (paste the JSON above)")
    print("   - DATABASE_URL (your MySQL connection string)")
    print("   - TELEGRAM_BOT_TOKEN")
    print("   - TELEGRAM_CHAT_ID")
    print("   - POLLINATION_API_KEY (optional)")

if __name__ == "__main__":
    main()