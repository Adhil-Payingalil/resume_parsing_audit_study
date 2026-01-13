#!/usr/bin/env python3
"""
Check the jd_extraction status in MongoDB
"""

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

def check_jd_extraction_status():
    """Check the jd_extraction status in MongoDB"""
    try:
        client = MongoClient(os.getenv('MONGODB_URI'))
        db = client['Resume_study']
        collection = db['Job_postings_greenhouse']
        
        # Count total jobs
        total = collection.count_documents({})
        print(f"Total jobs: {total}")
        
        # Count jobs with descriptions
        with_descriptions = collection.count_documents({'job_description': {'$exists': True, '$ne': ''}})
        print(f"Jobs with descriptions: {with_descriptions}")
        
        # Count jobs with jd_extraction flag
        with_jd_flag = collection.count_documents({'jd_extraction': {'$exists': True}})
        print(f"Jobs with jd_extraction flag: {with_jd_flag}")
        
        # Count successful extractions
        successful_extractions = collection.count_documents({'jd_extraction': True})
        print(f"Jobs with successful JD extraction: {successful_extractions}")
        
        # Count failed extractions
        failed_extractions = collection.count_documents({'jd_extraction': False})
        print(f"Jobs with failed JD extraction: {failed_extractions}")
        
        # Show sample jobs
        print("\nSample jobs with jd_extraction status:")
        sample_jobs = list(collection.find(
            {'jd_extraction': {'$exists': True}}, 
            {'title': 1, 'company': 1, 'jd_extraction': 1, 'job_description': 1}
        ).limit(5))
        
        for i, job in enumerate(sample_jobs, 1):
            title = job.get('title', 'Unknown')[:50]
            company = job.get('company', 'Unknown')[:30]
            jd_extraction = job.get('jd_extraction', 'N/A')
            desc_length = len(job.get('job_description', ''))
            status = "✅ Clean" if jd_extraction else "📄 Full Content"
            print(f"  {i}. {title} | {company} | {status} | {desc_length} chars")
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_jd_extraction_status()
