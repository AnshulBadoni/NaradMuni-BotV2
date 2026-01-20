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
        self.critical_phrases = [
            "move forward", "moving forward", "proceed with",
            "schedule a call", "schedule an interview", "schedule interview",
            "next round", "next steps", "final round",
            "shortlisted", "selected for", "qualified for",
            "your availability", "interview availability",
            "regarding your application", "about your application",
            "received your application", "reviewed your application",
            "application status", "application update",
            "hr team", "talent acquisition", "we'd like to",
            "pleased to inform", "congratulations", "offer letter",
            "job offer", "welcome to the team", "you have been selected"
        ]
        
        self.high_value = [
            "hiring", "recruiter", "recruitment", "hr",
            "job opening", "job opportunity", "career opportunity",
            "we are looking", "apply now", "job alert", "new jobs"
        ]
        
        self.context = [
            "python", "java", "javascript", "developer", "engineer",
            "software", "backend", "frontend", "fullstack", "devops",
            "job", "role", "position", "opportunity", "remote", "onsite"
        ]
        
        self.spam = [
            "unsubscribe", "newsletter", "marketing", "promotional",
            "sale", "discount", "limited time", "order now",
            "loan", "credit card", "insurance", "forex"
        ]
        
        self.hr_domains = ["careers@", "hr@", "recruit@", "talent@", "hiring@", "jobs@"]

    def classify(self, subject: str, body: str, sender: str) -> dict:
        subject = normalize(subject)
        body = normalize(body)
        sender = normalize(sender)
        text = f"{subject} {body} {sender}"

        score = 0
        matches = []

        for phrase in self.critical_phrases:
            if phrase in text:
                matches.append(phrase)
                score += 40

        for kw in self.high_value:
            if kw in text:
                matches.append(kw)
                score += 15

        for kw in self.context:
            if kw in text:
                score += 5

        for domain in self.hr_domains:
            if domain in sender:
                matches.append(domain)
                score += 25

        spam_count = sum(1 for kw in self.spam if kw in text)
        score -= spam_count * 30

        confidence = min(max(score / 50, 0), 1.0)

        if confidence >= 0.85:
            label = "HR"
        elif confidence >= 0.6:
            label = "JOB"
        elif confidence <= 0.25:
            label = "OTHER"
        else:
            label = "UNCERTAIN"

        return {
            "label": label,
            "confidence": confidence,
            "matches": matches[:5],
            "source": "RULES"
        }

fast_classifier = FastClassifier()

def classify_with_llm(subject: str, body: str, sender: str) -> dict:
    if not config.POLLINATION_API_KEY:
        return {"label": "JOB", "confidence": 0.5, "source": "FALLBACK"}

    try:
        prompt = f"""Classify this email:
HR = Human recruiter wants to talk/interview
JOB = Automated job alert
OTHER = Spam/newsletter

Respond ONLY: {{"category": "HR" or "JOB" or "OTHER"}}

Subject: {normalize(subject)}
From: {normalize(sender)}
Body: {normalize(body)[:1000]}

JSON:"""

        response = requests.post(
            "https://text.pollinations.ai/",
            headers={"Content-Type": "application/json"},
            json={
                "messages": [{"role": "user", "content": prompt}],
                "model": "openai",
                "seed": 42
            },
            timeout=15
        )

        if response.status_code != 200:
            return {"label": "JOB", "confidence": 0.5, "source": "FALLBACK"}

        content = response.text.strip()
        
        try:
            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                result = data.get("category", "OTHER").upper()
            else:
                content_upper = content.upper()
                if "HR" in content_upper:
                    result = "HR"
                elif "JOB" in content_upper:
                    result = "JOB"
                else:
                    result = "OTHER"
        except:
            result = "JOB"

        return {"label": result, "confidence": 0.85, "source": "AI"}

    except Exception as e:
        logger.error(f"LLM failed: {e}")
        return {"label": "JOB", "confidence": 0.5, "source": "FALLBACK"}

def classify_email(subject: str, body: str, sender: str) -> dict:
    result = fast_classifier.classify(subject, body, sender)

    if result["confidence"] >= 0.85:
        result["is_job"] = True
        return result
    
    if result["confidence"] <= 0.25:
        result["is_job"] = False
        return result

    logger.info(f"🤔 Uncertain ({result['confidence']:.0%}) → asking AI...")
    llm_result = classify_with_llm(subject, body, sender)
    llm_result["matches"] = result.get("matches", [])
    llm_result["is_job"] = llm_result["label"] in ["HR", "JOB"]
    
    return llm_result