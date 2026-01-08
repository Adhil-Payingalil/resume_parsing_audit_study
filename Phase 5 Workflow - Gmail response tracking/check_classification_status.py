"""
Quick script to check if emails have been classified in MongoDB.
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.mongodb import _get_mongo_client
from utils import get_logger
from dotenv import load_dotenv

load_dotenv()
logger = get_logger(__name__)

def check_classification_status(collection_name: str = "email_scrapping_test"):
    """Check if emails have classification fields."""
    mongo_client = _get_mongo_client()
    if not mongo_client:
        logger.error("Failed to connect to MongoDB")
        return
    
    try:
        db = mongo_client["Resume_study"]
        collection = db[collection_name]
        
        total_count = collection.count_documents({})
        classified_count = collection.count_documents({"email_category": {"$exists": True}})
        
        logger.info(f"\n{'='*60}")
        logger.info("CLASSIFICATION STATUS CHECK")
        logger.info("="*60)
        logger.info(f"Total emails in collection: {total_count}")
        logger.info(f"Emails with 'email_category' field: {classified_count}")
        
        if classified_count == 0:
            logger.info("\n❌ Emails have NOT been classified yet.")
            logger.info("   Run: python 'Phase 5 Workflow - Gmail response tracking/classify_emails.py'")
        elif classified_count < total_count:
            logger.info(f"\n⚠️  Partial classification: {classified_count}/{total_count} emails classified")
            logger.info("   Run classifier again to update remaining emails")
        else:
            logger.info("\n✅ All emails have been classified!")
            
            # Check categories
            from collections import Counter
            categories = Counter()
            subcategories = Counter()
            
            for email in collection.find({"email_category": {"$exists": True}}):
                cat = email.get("email_category")
                if cat:
                    categories[cat] += 1
                    
                    if cat == "application_update":
                        subcat = email.get("email_subcategory")
                        if subcat:
                            subcategories[subcat] += 1
            
            logger.info(f"\nCategories found:")
            for cat, count in categories.most_common():
                logger.info(f"  {cat}: {count}")
            
            if subcategories:
                logger.info(f"\nApplication Update Subcategories:")
                for subcat, count in subcategories.most_common():
                    logger.info(f"  {subcat}: {count}")
        
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"Error checking status: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    finally:
        mongo_client.close()

if __name__ == "__main__":
    check_classification_status()








