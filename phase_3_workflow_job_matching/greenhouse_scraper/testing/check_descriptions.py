#!/usr/bin/env python3
"""
Check job descriptions in MongoDB
"""

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

def check_descriptions():
    try:
        client = MongoClient(os.getenv('MONGODB_URI'))
        db = client['Resume_study']
        collection = db['Job_postings_greenhouse']
        
        # Find a job with description
        job_with_desc = collection.find_one({'job_description': {'$exists': True, '$ne': ''}})
        if job_with_desc:
            print('✅ Found job with description!')
            print(f'Title: {job_with_desc.get("title", "N/A")}')
            print(f'Company: {job_with_desc.get("company", "N/A")}')
            print(f'Description length: {len(job_with_desc.get("job_description", ""))} characters')
            print(f'First 200 chars: {job_with_desc.get("job_description", "")[:200]}...')
        else:
            print('❌ No jobs with descriptions found')
            
        # Count jobs with descriptions
        count = collection.count_documents({'job_description': {'$exists': True, '$ne': ''}})
        print(f'\nTotal jobs with descriptions: {count}')
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_descriptions()
