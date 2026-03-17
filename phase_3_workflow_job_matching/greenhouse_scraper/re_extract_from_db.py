import os
import asyncio
from pymongo import MongoClient
from dotenv import load_dotenv
import logging

# Re-use the exact same logic from your latest optimized extractor
from description_extractor_optimized import JobDescriptionExtractor
from config import MONGODB_URI, MONGODB_DATABASE, MONGODB_COLLECTION

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def run_backfill(cycle):
    """
    Reruns the clean extraction logic on jobs that already have `jina_raw_content`
    without making any new web requests to the Jina API.
    """
    
    if not MONGODB_URI:
        logger.error("MONGODB_URI not found.")
        return
        
    client = MongoClient(MONGODB_URI)
    db = client[MONGODB_DATABASE]
    collection = db[MONGODB_COLLECTION]
    
    # Initialize the extractor just to use its text processing method
    extractor = JobDescriptionExtractor(cycle=cycle)
    
    # Find all jobs in the specified cycle that already have raw content
    query = {
        'cycle': cycle,
        'jina_raw_content': {'$exists': True, '$ne': None},
        'jina_raw_content': {'$ne': ''}
    }
    
    jobs = list(collection.find(query, {
        '_id': 1, 
        'title': 1, 
        'jina_raw_content': 1, 
        'jd_extraction_method': 1
    }))
    
    logger.info(f"Found {len(jobs)} jobs in cycle {cycle} with raw Jina content to re-process.")
    if len(jobs) == 0:
        return
        
    updated_count = 0
    improved_count = 0
    
    for job in jobs:
        job_id = job['_id']
        title = job.get('title', '')
        raw_content = job.get('jina_raw_content', '')
        old_method = job.get('jd_extraction_method', '')
        
        # Run the updated local extraction logic
        description, new_method = extractor.extract_description_from_content(raw_content, title)
        
        jd_extraction_success = (new_method == "clean")
        
        if new_method == "clean" and old_method != "clean":
            improved_count += 1
            
        # Safely update the DB with the new cleaned text
        update_data = {
            'job_description': description,
            'jd_extraction': jd_extraction_success,
            'jd_extraction_method': new_method
        }
        
        collection.update_one({'_id': job_id}, {'$set': update_data})
        updated_count += 1
        
    logger.info("-" * 40)
    logger.info(f"Finished! Reprocessed {updated_count} jobs.")
    logger.info(f"Successfully upgraded {improved_count} jobs to 'clean' extraction that were previously failing or fallback.")
    logger.info("-" * 40)

if __name__ == "__main__":
    print("Local database offline re-extractor")
    cycle_str = input("Enter cycle number to re-process (e.g., 19): ")
    try:
        cycle_val = float(cycle_str)
        if cycle_val.is_integer():
            cycle_val = int(cycle_val)
        run_backfill(cycle_val)
    except ValueError:
        print("Invalid cycle number.")
