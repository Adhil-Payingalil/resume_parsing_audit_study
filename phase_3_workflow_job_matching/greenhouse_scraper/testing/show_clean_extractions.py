#!/usr/bin/env python3
"""
Show sample clean extractions with titles
"""

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

def show_clean_extractions():
    """Show sample clean extractions with titles"""
    try:
        client = MongoClient(os.getenv('MONGODB_URI'))
        db = client['Resume_study']
        collection = db['Job_postings_greenhouse']
        
        # Get jobs with clean extractions
        clean_jobs = list(collection.find(
            {'jd_extraction': True}, 
            {'title': 1, 'company': 1, 'job_description': 1}
        ).limit(3))
        
        print("Sample Clean Extractions with Titles:")
        print("=" * 60)
        
        for i, job in enumerate(clean_jobs, 1):
            title = job.get('title', 'Unknown')
            company = job.get('company', 'Unknown')
            description = job.get('job_description', '')
            
            print(f"\n{i}. {title} | {company}")
            print(f"Description length: {len(description)} characters")
            print("First 400 characters:")
            print("-" * 40)
            print(description[:400])
            print("-" * 40)
            
            # Check if title is at the start
            if description.startswith(f"# {title}"):
                print("✅ Title correctly added at start")
            else:
                print("❌ Title not found at start")
        
        client.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_clean_extractions()
