"""
Email Data Analysis Script

This script analyzes the scraped email data in MongoDB to understand patterns
and develop a classification framework for job application-related emails.
"""

import sys
import os
from collections import Counter, defaultdict
from datetime import datetime
import re

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.mongodb import _get_mongo_client
from utils import get_logger
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)


def analyze_email_data(collection_name: str = "email_scrapping_test", sample_size: int = 100):
    """
    Analyze email data to understand patterns for classification.
    
    Args:
        collection_name: MongoDB collection name
        sample_size: Number of emails to sample for analysis
    """
    mongo_client = _get_mongo_client()
    if not mongo_client:
        logger.error("Failed to connect to MongoDB")
        return
    
    try:
        db = mongo_client["Resume_study"]
        collection = db[collection_name]
        
        # Get total count
        total_count = collection.count_documents({})
        logger.info(f"Total emails in collection: {total_count}")
        
        # Get sample emails
        sample_emails = list(collection.find().limit(sample_size))
        logger.info(f"Analyzing {len(sample_emails)} sample emails")
        
        # Analyze senders
        senders = Counter()
        sender_domains = Counter()
        subjects = []
        subjects_lower = []
        
        for email in sample_emails:
            from_addr = email.get("from", "")
            subject = email.get("subject", "")
            
            if from_addr:
                senders[from_addr] += 1
                # Extract domain
                domain_match = re.search(r'@([\w\.-]+)', from_addr)
                if domain_match:
                    sender_domains[domain_match.group(1)] += 1
            
            if subject:
                subjects.append(subject)
                subjects_lower.append(subject.lower())
        
        # Print sender analysis
        logger.info("\n" + "="*60)
        logger.info("TOP SENDERS (by domain):")
        logger.info("="*60)
        for domain, count in sender_domains.most_common(20):
            logger.info(f"  {domain}: {count}")
        
        # Analyze subject patterns
        logger.info("\n" + "="*60)
        logger.info("SAMPLE SUBJECTS:")
        logger.info("="*60)
        for i, subject in enumerate(subjects[:30], 1):
            logger.info(f"{i}. {subject}")
        
        # Look for keywords in subjects
        keywords = [
            "application", "reject", "interview", "thank you", "next step",
            "greenhouse", "position", "job", "resume", "candidate",
            "security", "verification", "code", "notification"
        ]
        
        keyword_counts = Counter()
        for subject_lower in subjects_lower:
            for keyword in keywords:
                if keyword in subject_lower:
                    keyword_counts[keyword] += 1
        
        logger.info("\n" + "="*60)
        logger.info("KEYWORD FREQUENCY IN SUBJECTS:")
        logger.info("="*60)
        for keyword, count in keyword_counts.most_common():
            logger.info(f"  '{keyword}': {count}")
        
        # Analyze email body content (first 500 chars)
        logger.info("\n" + "="*60)
        logger.info("SAMPLE EMAIL BODIES (first 200 chars):")
        logger.info("="*60)
        for i, email in enumerate(sample_emails[:10], 1):
            body = email.get("body_text", "") or email.get("body_html", "")
            body_preview = body[:200].replace("\n", " ").strip()
            logger.info(f"\n{i}. From: {email.get('from', 'N/A')}")
            logger.info(f"   Subject: {email.get('subject', 'N/A')}")
            logger.info(f"   Body: {body_preview}...")
        
        # Analyze by gmail account
        accounts = Counter()
        for email in sample_emails:
            account = email.get("gmail_account", "unknown")
            accounts[account] += 1
        
        logger.info("\n" + "="*60)
        logger.info("EMAILS BY ACCOUNT:")
        logger.info("="*60)
        for account, count in accounts.most_common(10):
            logger.info(f"  {account}: {count}")
        
        # Look for Greenhouse-specific patterns
        greenhouse_emails = []
        application_emails = []
        security_emails = []
        google_emails = []
        
        for email in sample_emails:
            from_addr = email.get("from", "").lower()
            subject = email.get("subject", "").lower()
            body = (email.get("body_text", "") or email.get("body_html", "")).lower()
            
            if "greenhouse" in from_addr or "greenhouse" in subject:
                greenhouse_emails.append(email)
            if any(word in subject for word in ["application", "position", "candidate", "interview"]):
                application_emails.append(email)
            if any(word in subject for word in ["security", "verification", "code"]):
                security_emails.append(email)
            if "google" in from_addr or "noreply@accounts.google.com" in from_addr:
                google_emails.append(email)
        
        logger.info("\n" + "="*60)
        logger.info("EMAIL CATEGORIES (from sample):")
        logger.info("="*60)
        logger.info(f"  Greenhouse emails: {len(greenhouse_emails)}")
        logger.info(f"  Application-related: {len(application_emails)}")
        logger.info(f"  Security/Verification: {len(security_emails)}")
        logger.info(f"  Google notifications: {len(google_emails)}")
        
        # Show examples of each category
        logger.info("\n" + "="*60)
        logger.info("GREENHOUSE EMAIL EXAMPLES:")
        logger.info("="*60)
        for i, email in enumerate(greenhouse_emails[:5], 1):
            logger.info(f"{i}. From: {email.get('from', 'N/A')}")
            logger.info(f"   Subject: {email.get('subject', 'N/A')}")
        
        logger.info("\n" + "="*60)
        logger.info("APPLICATION EMAIL EXAMPLES:")
        logger.info("="*60)
        for i, email in enumerate(application_emails[:5], 1):
            logger.info(f"{i}. From: {email.get('from', 'N/A')}")
            logger.info(f"   Subject: {email.get('subject', 'N/A')}")
        
    except Exception as e:
        logger.error(f"Error analyzing email data: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
        mongo_client.close()


if __name__ == "__main__":
    analyze_email_data(sample_size=200)








