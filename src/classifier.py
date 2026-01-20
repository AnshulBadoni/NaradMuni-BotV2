# src/classifier.py
import os
import re
import json
import logging
import requests
from urllib.parse import unquote
import html
from .config import config

logger = logging.getLogger(__name__)

def normalize(text: str) -> str:
    if not text:
        return ""
    text = unquote(str(text))
    text = html.unescape(text)
    text = re.sub(r'\s+', ' ', text)
    return text.lower().strip()

class FastClassifier:
    def __init__(self):
        # ══════════════════════════════════════════════════════════
        # BLOCKLIST - Immediately reject these (score = -1000)
        # ══════════════════════════════════════════════════════════
        
        # Sender domains/emails to ALWAYS block
        self.blocked_senders = [
            # Shopping & E-commerce
            "amazon", "flipkart", "myntra", "ajio", "meesho", "snapdeal",
            "ebay", "alibaba", "aliexpress", "shopify", "etsy",
            "store-news@", "deals@", "offers@", "promo@", "marketing@",
            "noreply@amazon", "newsletter@",
            
            # Social Media (non-job)
            "invitations@linkedin.com",  # Connection requests, NOT job alerts
            "messages-noreply@linkedin.com",
            "notifications-noreply@linkedin.com",
            "@facebookmail.com", "@instagram.com", "@twitter.com",
            "@pinterest.com", "@quora.com", "@reddit.com",
            
            # Entertainment & Media
            "spotify", "netflix", "youtube", "twitch", "discord",
            "medium.com", "substack", "hashnode",
            
            # Finance & Banking (non-job)
            "hdfc", "icici", "sbi", "axis", "kotak", "paytm", "phonepe",
            "gpay", "amazonpay", "razorpay", "creditcard", "loan",
            
            # Food & Delivery
            "zomato", "swiggy", "uber", "ola", "dunzo",
            
            # Travel
            "makemytrip", "goibibo", "booking.com", "airbnb", "trivago",
            
            # Newsletters & Marketing
            "mailchimp", "sendinblue", "hubspot", "mailgun",
            "no-reply@", "noreply@", "donotreply@",
            "news@", "info@", "hello@", "team@", "support@",
        ]
        
        # Subjects to ALWAYS block
        self.blocked_subjects = [
            # Shopping
            "we found something", "you might like", "keep shopping",
            "your order", "order confirmed", "order shipped", "order delivered",
            "track your", "shipping update", "delivery update",
            "cart reminder", "items in your cart", "price drop",
            "sale", "discount", "% off", "coupon", "cashback", "reward points",
            "deal of the day", "flash sale", "limited time",
            
            # Social (non-job)
            "i want to connect", "wants to connect", "connect with",
            "accepted your invitation", "connection request",
            "mentioned you", "tagged you", "commented on", "liked your",
            "new follower", "started following", "viewed your profile",
            "birthday", "anniversary", "congratulate",
            
            # Notifications
            "your weekly", "weekly digest", "daily digest", "monthly report",
            "newsletter", "subscription", "unsubscribe",
            
            # Finance
            "transaction", "payment", "credited", "debited", "statement",
            "otp", "verification code", "security alert",
            
            # Misc spam
            "verify your email", "confirm your email", "activate your account",
        ]
        
        # Body phrases to block
        self.blocked_body_phrases = [
            "keep shopping", "continue shopping", "shop now", "buy now",
            "add to cart", "checkout", "your cart",
            "unsubscribe from", "email preferences", "opt out",
            "view in browser", "trouble viewing",
        ]
        
        # ══════════════════════════════════════════════════════════
        # ALLOWLIST - Only these senders are trusted for jobs
        # ══════════════════════════════════════════════════════════
        
        # Trusted job-related senders
        self.trusted_job_senders = [
            "jobalerts-noreply@linkedin.com",  # LinkedIn JOB alerts only
            "jobs-noreply@linkedin.com",
            "@indeed.com", "@naukri.com", "@glassdoor.com",
            "@monster.com", "@shine.com", "@foundit.in",
            "@hirist.com", "@instahyre.com", "@cutshort.io",
            "@angel.co", "@wellfound.com", "@ycombinator.com",
            "careers@", "hr@", "recruit@", "talent@", "hiring@", "jobs@",
        ]
        
        # ══════════════════════════════════════════════════════════
        # POSITIVE SIGNALS - Job-related phrases
        # ══════════════════════════════════════════════════════════
        
        # Critical HR phrases (high confidence)
        self.critical_phrases = [
            "move forward", "moving forward", "proceed with your",
            "schedule a call", "schedule an interview", "interview scheduled",
            "next round", "next steps", "final round",
            "shortlisted", "selected for", "qualified for",
            "your availability", "interview availability", "available for a call",
            "regarding your application", "about your application",
            "received your application", "reviewed your application", "reviewed your resume",
            "application status", "application update",
            "we'd like to", "we would like to", "pleased to inform",
            "congratulations on", "offer letter", "job offer",
            "welcome to the team", "you have been selected",
            "your candidature", "your profile matches",
        ]
        
        # Job-related keywords (medium confidence)
        self.job_keywords = [
            "hiring", "job opening", "job opportunity", "career opportunity",
            "open position", "open role", "new jobs matching",
            "apply now", "job alert", "jobs for you",
            "python developer", "software engineer", "backend developer",
            "frontend developer", "fullstack developer", "data scientist",
        ]

    def classify(self, subject: str, body: str, sender: str) -> dict:
        """
        Classify email with strict filtering.
        Returns: {label, confidence, matches, source, is_job}
        """
        # Normalize all inputs
        subject_norm = normalize(subject)
        body_norm = normalize(body)
        sender_norm = normalize(sender)
        text = f"{subject_norm} {body_norm}"
        
        matches = []
        
        # ══════════════════════════════════════════════════════════
        # STEP 1: BLOCKLIST CHECK (Instant reject)
        # ══════════════════════════════════════════════════════════
        
        # Check blocked senders
        for blocked in self.blocked_senders:
            if blocked in sender_norm:
                logger.info(f"🚫 Blocked sender: {blocked}")
                return {
                    "label": "OTHER",
                    "confidence": 0.99,
                    "matches": [f"blocked_sender:{blocked}"],
                    "source": "RULES",
                    "is_job": False
                }
        
        # Check blocked subjects
        for blocked in self.blocked_subjects:
            if blocked in subject_norm:
                logger.info(f"🚫 Blocked subject: {blocked}")
                return {
                    "label": "OTHER",
                    "confidence": 0.99,
                    "matches": [f"blocked_subject:{blocked}"],
                    "source": "RULES",
                    "is_job": False
                }
        
        # Check blocked body phrases
        for blocked in self.blocked_body_phrases:
            if blocked in body_norm[:500]:  # Check first 500 chars
                logger.info(f"🚫 Blocked body phrase: {blocked}")
                return {
                    "label": "OTHER",
                    "confidence": 0.95,
                    "matches": [f"blocked_body:{blocked}"],
                    "source": "RULES",
                    "is_job": False
                }
        
        # ══════════════════════════════════════════════════════════
        # STEP 2: TRUSTED SENDER BONUS
        # ══════════════════════════════════════════════════════════
        
        score = 0
        is_trusted_sender = False
        
        for trusted in self.trusted_job_senders:
            if trusted in sender_norm:
                is_trusted_sender = True
                score += 30
                matches.append(f"trusted:{trusted}")
                break
        
        # ══════════════════════════════════════════════════════════
        # STEP 3: POSITIVE SIGNAL SCORING
        # ══════════════════════════════════════════════════════════
        
        # Critical phrases (+50 each)
        for phrase in self.critical_phrases:
            if phrase in text:
                score += 50
                matches.append(phrase)
        
        # Job keywords (+15 each)
        for kw in self.job_keywords:
            if kw in text:
                score += 15
                matches.append(kw)
        
        # ══════════════════════════════════════════════════════════
        # STEP 4: CALCULATE CONFIDENCE & DECIDE
        # ══════════════════════════════════════════════════════════
        
        confidence = min(max(score / 60, 0), 1.0)
        
        # Decision thresholds
        if confidence >= 0.85:
            label = "HR"
            is_job = True
        elif confidence >= 0.5:
            label = "JOB"
            is_job = True
        elif confidence >= 0.3:
            # Borderline - only pass if from trusted sender
            if is_trusted_sender:
                label = "JOB"
                is_job = True
            else:
                label = "UNCERTAIN"
                is_job = False  # Will go to LLM
        else:
            label = "OTHER"
            is_job = False
        
        logger.info(f"📊 Score: {score}, Confidence: {confidence:.0%}, Label: {label}")
        if matches:
            logger.info(f"   Matches: {matches[:5]}")
        
        return {
            "label": label,
            "confidence": confidence,
            "matches": matches[:5],
            "source": "RULES",
            "is_job": is_job
        }

fast_classifier = FastClassifier()

def classify_with_llm(subject: str, body: str, sender: str) -> dict:
    """Use Pollination AI for uncertain emails"""
    if not config.POLLINATION_API_KEY:
        logger.warning("No Pollination API key - defaulting to skip")
        return {"label": "OTHER", "confidence": 0.5, "source": "FALLBACK", "is_job": False}

    try:
        prompt = f"""You are a strict job email classifier. 

ONLY classify as HR or JOB if it's DIRECTLY about:
- A real job opportunity
- Interview invitation
- Application status from a company
- Recruiter reaching out about a specific role

Classify as OTHER for:
- Shopping/marketing emails
- LinkedIn connection requests (NOT job alerts)
- Newsletters
- Social media notifications
- Banking/finance emails
- Any promotional content

Categories:
- HR = Human recruiter directly reaching out about YOUR job application
- JOB = Job alert from job board (LinkedIn Jobs, Indeed, Naukri)
- OTHER = Everything else (when in doubt, say OTHER)

Respond with ONLY: {{"category": "HR" or "JOB" or "OTHER"}}

Subject: {normalize(subject)}
From: {normalize(sender)}
Body: {normalize(body)[:800]}

JSON:"""

        response = requests.post(
            "https://text.pollinations.ai/",
            headers={"Content-Type": "application/json"},
            json={"messages": [{"role": "user", "content": prompt}], "model": "openai", "seed": 42},
            timeout=15
        )

        if response.status_code != 200:
            return {"label": "OTHER", "confidence": 0.5, "source": "FALLBACK", "is_job": False}

        content = response.text.strip()
        logger.info(f"🤖 LLM response: {content[:100]}")
        
        try:
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                result = data.get("category", "OTHER").upper()
            else:
                content_upper = content.upper()
                if "\"HR\"" in content_upper or ": HR" in content_upper:
                    result = "HR"
                elif "\"JOB\"" in content_upper or ": JOB" in content_upper:
                    result = "JOB"
                else:
                    result = "OTHER"
        except:
            result = "OTHER"

        is_job = result in ["HR", "JOB"]
        logger.info(f"🤖 LLM decision: {result}")
        
        return {"label": result, "confidence": 0.85, "source": "AI", "is_job": is_job}

    except Exception as e:
        logger.error(f"LLM failed: {e}")
        return {"label": "OTHER", "confidence": 0.5, "source": "FALLBACK", "is_job": False}

def classify_email(subject: str, body: str, sender: str) -> dict:
    """
    Main classification function with strict filtering.
    """
    result = fast_classifier.classify(subject, body, sender)
    
    # If rules are confident, use that
    if result["confidence"] >= 0.5 or result["confidence"] <= 0.1:
        return result
    
    # Borderline cases → ask LLM (but be conservative)
    if result["label"] == "UNCERTAIN":
        logger.info(f"🤔 Uncertain ({result['confidence']:.0%}) → asking AI...")
        llm_result = classify_with_llm(subject, body, sender)
        llm_result["matches"] = result.get("matches", [])
        return llm_result
    
    return result