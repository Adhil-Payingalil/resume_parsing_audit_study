"""
Email Classification Script

This script classifies emails scraped from Gmail accounts into categories,
with a focus on identifying job application updates (rejections, interview invites, next steps).

Classification Categories:
1. application_update - Updates on application status (rejections, interview invites, next steps)
2. application_submission - Confirmation of application submission
3. security_code - Security code notifications (not application updates)
4. google_notification - Google account security/verification emails
5. other - Other emails not related to job applications
"""

import sys
import os
import re
from typing import Dict, List, Optional, Any
from collections import Counter
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.mongodb import _get_mongo_client
from utils import get_logger
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

# Classification categories
CATEGORY_APPLICATION_UPDATE = "application_update"
CATEGORY_APPLICATION_SUBMISSION = "application_submission"
CATEGORY_SECURITY_CODE = "security_code"
CATEGORY_GOOGLE_NOTIFICATION = "google_notification"
CATEGORY_OTHER = "other"

# Keywords and patterns for classification
APPLICATION_UPDATE_KEYWORDS = [
    # Rejection keywords
    "unfortunately", "not moving forward", "not selected", "decided to pursue",
    "other candidates", "better fit", "not a match", "not proceed", "not advance",
    "not chosen", "not proceed", "we've decided", "we have decided",
    "not the right fit", "not move forward", "not selected for",
    
    # Interview/Next steps keywords
    "interview", "phone screen", "next step", "next steps", "schedule",
    "would like to", "interested in", "move forward", "advance to",
    "next round", "next phase", "screening", "assessment", "technical interview",
    "behavioral interview", "final round", "on-site", "virtual interview",
    
    # Positive updates
    "congratulations", "excited to", "pleased to", "happy to", "offer",
    "selected for", "chosen for", "proceed to", "advance to",
    
    # Status updates
    "status update", "update on", "update regarding", "update about",
    "application status", "position status", "candidate status"
]

APPLICATION_SUBMISSION_KEYWORDS = [
    "thank you for applying", "thank you for your application",
    "application received", "application submitted", "received your application",
    "submitted your application", "application confirmation", "confirming receipt"
]

SECURITY_CODE_KEYWORDS = [
    "security code", "verification code", "access code", "login code"
]

GOOGLE_NOTIFICATION_KEYWORDS = [
    "security alert", "2-step verification", "google account", "account security",
    "sign-in attempt", "new device", "unusual activity"
]

# Sender domain patterns
GREENHOUSE_DOMAINS = ["greenhouse-mail.io", "greenhouse.io", "us.greenhouse-mail.io"]
GOOGLE_DOMAINS = ["accounts.google.com", "google.com", "gmail.com"]


def extract_domain(email_address: str) -> str:
    """Extract domain from email address."""
    if not email_address:
        return ""
    match = re.search(r'@([\w\.-]+)', email_address.lower())
    return match.group(1) if match else ""


def classify_email(email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify a single email into categories.
    
    Args:
        email: Email dictionary from MongoDB
        
    Returns:
        Dictionary with classification results
    """
    subject = (email.get("subject", "") or "").lower()
    from_addr = (email.get("from", "") or "").lower()
    body_text = (email.get("body_text", "") or "").lower()
    body_html = (email.get("body_html", "") or "").lower()
    
    # Combine body text for analysis
    full_body = (body_text + " " + body_html).lower()
    
    # Extract sender domain
    sender_domain = extract_domain(from_addr)
    
    # Initialize classification
    classification = {
        "category": CATEGORY_OTHER,
        "subcategory": None,
        "confidence": 0.0,
        "reasoning": [],
        "is_application_related": False,
        "is_application_update": False
    }
    
    # Check if from Greenhouse
    is_greenhouse = any(domain in sender_domain for domain in GREENHOUSE_DOMAINS)
    is_google = any(domain in sender_domain for domain in GOOGLE_DOMAINS)
    
    # 1. Check for Google notifications (highest priority to exclude)
    if is_google or any(keyword in subject for keyword in GOOGLE_NOTIFICATION_KEYWORDS):
        classification["category"] = CATEGORY_GOOGLE_NOTIFICATION
        classification["confidence"] = 0.95
        classification["reasoning"].append("Google notification email")
        return classification
    
    # 2. Check for security code notifications
    if (is_greenhouse and "security code" in subject) or \
       any(keyword in subject for keyword in SECURITY_CODE_KEYWORDS):
        classification["category"] = CATEGORY_SECURITY_CODE
        classification["confidence"] = 0.95
        classification["reasoning"].append("Security code notification")
        classification["is_application_related"] = True
        return classification
    
    # 3. Check for application submission confirmations
    if any(keyword in subject for keyword in APPLICATION_SUBMISSION_KEYWORDS) or \
       any(keyword in full_body[:500] for keyword in APPLICATION_SUBMISSION_KEYWORDS):
        classification["category"] = CATEGORY_APPLICATION_SUBMISSION
        classification["confidence"] = 0.90
        classification["reasoning"].append("Application submission confirmation")
        classification["is_application_related"] = True
        return classification
    
    # 4. Check for application updates (rejections, interviews, next steps)
    update_keywords_found = []
    confidence_score = 0.0
    
    # Check subject line
    for keyword in APPLICATION_UPDATE_KEYWORDS:
        if keyword in subject:
            update_keywords_found.append(keyword)
            confidence_score += 0.3
    
    # Check body (first 1000 chars for performance)
    body_sample = full_body[:1000]
    for keyword in APPLICATION_UPDATE_KEYWORDS:
        if keyword in body_sample:
            if keyword not in update_keywords_found:
                update_keywords_found.append(keyword)
            confidence_score += 0.2
    
    # Determine subcategory
    subcategory = None
    if update_keywords_found:
        # Check for rejection
        rejection_keywords = ["unfortunately", "not moving forward", "not selected", 
                            "not a match", "not proceed", "not advance", "not chosen",
                            "we've decided", "we have decided", "not the right fit"]
        if any(kw in update_keywords_found for kw in rejection_keywords) or \
           any(kw in subject for kw in rejection_keywords):
            subcategory = "rejection"
            confidence_score = min(confidence_score + 0.2, 1.0)
        
        # Check for interview invitation
        elif any(kw in update_keywords_found for kw in ["interview", "phone screen", "schedule"]):
            subcategory = "interview_invitation"
            confidence_score = min(confidence_score + 0.2, 1.0)
        
        # Check for next steps
        elif any(kw in update_keywords_found for kw in ["next step", "next steps", "move forward", "advance"]):
            subcategory = "next_steps"
            confidence_score = min(confidence_score + 0.2, 1.0)
        
        # Check for offer
        elif any(kw in update_keywords_found for kw in ["offer", "congratulations", "excited to", "pleased to"]):
            subcategory = "offer"
            confidence_score = min(confidence_score + 0.2, 1.0)
        
        else:
            subcategory = "status_update"
    
    # If we found update keywords, classify as application update
    if update_keywords_found:
        classification["category"] = CATEGORY_APPLICATION_UPDATE
        classification["subcategory"] = subcategory
        classification["confidence"] = min(confidence_score, 1.0)
        classification["reasoning"].append(f"Found update keywords: {', '.join(update_keywords_found[:5])}")
        classification["is_application_related"] = True
        classification["is_application_update"] = True
        return classification
    
    # 5. Check if from Greenhouse or other ATS (likely application-related but not classified)
    if is_greenhouse:
        classification["category"] = CATEGORY_APPLICATION_SUBMISSION  # Default to submission
        classification["confidence"] = 0.60
        classification["reasoning"].append("From Greenhouse but no clear update keywords")
        classification["is_application_related"] = True
        return classification
    
    # 6. Default to other
    classification["category"] = CATEGORY_OTHER
    classification["confidence"] = 0.50
    classification["reasoning"].append("No matching patterns found")
    return classification


def classify_all_emails(
    collection_name: str = "email_scrapping_test",
    update_mongodb: bool = True
) -> Dict[str, Any]:
    """
    Classify all emails in MongoDB collection and update them with classification fields.
    
    Args:
        collection_name: MongoDB collection name to update
        update_mongodb: If True, update emails in the collection with classification fields
        
    Returns:
        Dictionary with classification statistics
    """
    mongo_client = _get_mongo_client()
    if not mongo_client:
        logger.error("Failed to connect to MongoDB")
        return {}
    
    stats = {
        "total_emails": 0,
        "classified": 0,
        "updated": 0,
        "categories": Counter(),
        "subcategories": Counter(),
        "application_related": 0,
        "application_updates": 0,
        "errors": 0
    }
    
    try:
        db = mongo_client["Resume_study"]
        collection = db[collection_name]
        
        # Get all emails
        emails = list(collection.find())
        stats["total_emails"] = len(emails)
        
        logger.info(f"Classifying {stats['total_emails']} emails...")
        
        for idx, email in enumerate(emails, 1):
            try:
                # Classify email
                classification = classify_email(email)
                
                # Prepare update fields
                update_fields = {
                    "email_category": classification["category"]
                }
                
                # Add subcategory only for application_update emails
                if classification["category"] == CATEGORY_APPLICATION_UPDATE and classification.get("subcategory"):
                    update_fields["email_subcategory"] = classification["subcategory"]
                
                # Update statistics
                stats["categories"][classification["category"]] += 1
                if classification.get("subcategory"):
                    stats["subcategories"][classification["subcategory"]] += 1
                if classification["is_application_related"]:
                    stats["application_related"] += 1
                if classification["is_application_update"]:
                    stats["application_updates"] += 1
                
                stats["classified"] += 1
                
                # Update email in MongoDB
                if update_mongodb:
                    email_id = email.get("_id")
                    if email_id:
                        # Remove subcategory field if not application_update
                        if classification["category"] != CATEGORY_APPLICATION_UPDATE:
                            collection.update_one(
                                {"_id": email_id},
                                {
                                    "$set": update_fields,
                                    "$unset": {"email_subcategory": ""}
                                }
                            )
                        else:
                            collection.update_one(
                                {"_id": email_id},
                                {"$set": update_fields}
                            )
                        stats["updated"] += 1
                
                if idx % 100 == 0:
                    logger.info(f"Classified {idx}/{stats['total_emails']} emails...")
                    
            except Exception as e:
                logger.error(f"Error classifying email {email.get('_id', 'unknown')}: {e}")
                stats["errors"] += 1
                continue
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("CLASSIFICATION SUMMARY")
        logger.info("="*60)
        logger.info(f"Total emails: {stats['total_emails']}")
        logger.info(f"Successfully classified: {stats['classified']}")
        if update_mongodb:
            logger.info(f"Updated in MongoDB: {stats['updated']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"\nApplication-related emails: {stats['application_related']}")
        logger.info(f"Application updates: {stats['application_updates']}")
        logger.info(f"\nCategories:")
        for category, count in stats['categories'].most_common():
            logger.info(f"  {category}: {count}")
        logger.info(f"\nSubcategories (application updates):")
        for subcategory, count in stats['subcategories'].most_common():
            logger.info(f"  {subcategory}: {count}")
        logger.info("="*60)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error classifying emails: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return stats
    finally:
        mongo_client.close()


def get_application_updates(
    collection_name: str = "email_scrapping_test",
    subcategory: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Get all application update emails from collection.
    
    Args:
        collection_name: MongoDB collection name
        subcategory: Optional subcategory filter (rejection, interview_invitation, next_steps, offer, status_update)
        
    Returns:
        List of application update emails
    """
    mongo_client = _get_mongo_client()
    if not mongo_client:
        logger.error("Failed to connect to MongoDB")
        return []
    
    try:
        db = mongo_client["Resume_study"]
        collection = db[collection_name]
        
        query = {
            "email_category": CATEGORY_APPLICATION_UPDATE
        }
        
        if subcategory:
            query["email_subcategory"] = subcategory
        
        emails = list(collection.find(query).sort("date", -1))
        
        logger.info(f"Found {len(emails)} application update emails" + 
                   (f" (subcategory: {subcategory})" if subcategory else ""))
        
        return emails
        
    except Exception as e:
        logger.error(f"Error getting application updates: {e}")
        return []
    finally:
        mongo_client.close()


def view_sample_classifications(
    collection_name: str = "email_scrapping_test",
    limit: int = 20,
    category: Optional[str] = None
):
    """
    View sample classified emails for verification.
    
    Args:
        collection_name: MongoDB collection name
        limit: Number of samples to show
        category: Optional category filter
    """
    mongo_client = _get_mongo_client()
    if not mongo_client:
        logger.error("Failed to connect to MongoDB")
        return
    
    try:
        db = mongo_client["Resume_study"]
        collection = db[collection_name]
        
        query = {}
        if category:
            query["email_category"] = category
        
        emails = list(collection.find(query).limit(limit))
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SAMPLE CLASSIFICATIONS ({len(emails)} emails)")
        logger.info("="*60)
        
        for i, email in enumerate(emails, 1):
            logger.info(f"\n{i}. From: {email.get('from', 'N/A')[:60]}")
            logger.info(f"   Subject: {email.get('subject', 'N/A')[:80]}")
            logger.info(f"   Category: {email.get('email_category', 'N/A')}")
            logger.info(f"   Subcategory: {email.get('email_subcategory', 'N/A')}")
        
    except Exception as e:
        logger.error(f"Error viewing sample classifications: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
        mongo_client.close()


def main():
    """Main entry point for classification."""
    # Classify all emails and update MongoDB collection
    stats = classify_all_emails(
        collection_name="email_scrapping_test",
        update_mongodb=True
    )
    
    # View sample classifications
    logger.info("\n" + "="*60)
    logger.info("SAMPLE APPLICATION UPDATE EMAILS")
    logger.info("="*60)
    view_sample_classifications(category=CATEGORY_APPLICATION_UPDATE, limit=10)
    
    # Get application updates
    logger.info("\n" + "="*60)
    logger.info("APPLICATION UPDATES BREAKDOWN")
    logger.info("="*60)
    
    for subcategory in ["rejection", "interview_invitation", "next_steps", "offer", "status_update"]:
        updates = get_application_updates(subcategory=subcategory)
        logger.info(f"{subcategory}: {len(updates)} emails")
    
    # Get all application updates
    all_updates = get_application_updates()
    logger.info(f"\nTotal application updates: {len(all_updates)}")


if __name__ == "__main__":
    main()

