#!/usr/bin/env python3
"""
Simple script to check MongoDB status and job descriptions
"""

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

def check_mongodb():
    try:
        client = MongoClient(os.getenv('MONGODB_URI'))
        db = client['Resume_study']
        collection = db['Job_postings_greenhouse']
        
        # Check total jobs
        total = collection.count_documents({})
        print(f"Total jobs: {total}")
        
        # Check jobs with descriptions
        with_descriptions = collection.count_documents({'job_description': {'$exists': True, '$ne': ''}})
        print(f"Jobs with descriptions: {with_descriptions}")
        
        # Check jobs without descriptions
        without_descriptions = collection.count_documents({
            'job_link': {'$exists': True, '$ne': ''},
            '$or': [
                {'job_description': {'$exists': False}},
                {'job_description': {'$eq': ''}},
                {'job_description': None}
            ]
        })
        print(f"Jobs without descriptions: {without_descriptions}")
        
        # Show a sample job
        sample = collection.find_one({})
        if sample:
            print(f"Sample job fields: {list(sample.keys())}")
            if 'job_description' in sample:
                desc = sample.get('job_description', '')
                print(f"Has job_description field: {bool(desc)}")
                if desc:
                    print(f"Description length: {len(desc)} characters")
            else:
                print("No job_description field found")
        else:
            print("No jobs found in database")
            
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_mongodb()
