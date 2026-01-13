#!/usr/bin/env python3
"""
Debug script to investigate why some job extractions are failing
"""

import asyncio
import aiohttp
from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

async def debug_failed_extractions():
    """Debug why some extractions are failing"""
    
    # Connect to MongoDB
    client = MongoClient(os.getenv('MONGODB_URI'))
    db = client['Resume_study']
    collection = db['Job_postings_greenhouse']
    
    # Find jobs without descriptions
    jobs_without_descriptions = list(collection.find({
        'job_link': {'$exists': True, '$ne': ''},
        '$or': [
            {'job_description': {'$exists': False}},
            {'job_description': {'$eq': ''}},
            {'job_description': None}
        ]
    }).limit(3))  # Check first 3 failed jobs
    
    print(f"Found {len(jobs_without_descriptions)} jobs without descriptions")
    print("=" * 60)
    
    # Test each failed job
    async with aiohttp.ClientSession() as session:
        for i, job in enumerate(jobs_without_descriptions, 1):
            job_url = job.get('job_link', '')
            job_title = job.get('title', 'Unknown')
            
            print(f"\n{i}. Testing: {job_title}")
            print(f"   URL: {job_url}")
            
            if not job_url:
                print("   ❌ No URL found")
                continue
                
            # Test Jina AI API call
            jina_url = f"https://r.jina.ai/{job_url}"
            headers = {'Authorization': f'Bearer {os.getenv("JINAAI_API_KEY")}'}
            
            try:
                async with session.get(jina_url, headers=headers) as response:
                    print(f"   HTTP Status: {response.status}")
                    
                    if response.status == 200:
                        content = await response.text()
                        print(f"   Content length: {len(content)} characters")
                        
                        # Check if content contains job-related keywords
                        content_lower = content.lower()
                        job_keywords = ['job', 'position', 'role', 'responsibilities', 'requirements', 'qualifications']
                        found_keywords = [kw for kw in job_keywords if kw in content_lower]
                        print(f"   Job keywords found: {found_keywords}")
                        
                        # Show first 300 characters
                        print(f"   First 300 chars: {content[:300]}...")
                        
                        # Check for common issues
                        if len(content) < 100:
                            print("   ⚠️ Content too short - might be blocked or empty")
                        elif 'access denied' in content_lower or 'forbidden' in content_lower:
                            print("   ⚠️ Access denied - job posting might be private")
                        elif 'not found' in content_lower or '404' in content_lower:
                            print("   ⚠️ Page not found - URL might be invalid")
                        elif 'login' in content_lower and 'required' in content_lower:
                            print("   ⚠️ Login required - job posting might be behind authentication")
                        else:
                            print("   ✅ Content looks good - extraction should work")
                            
                    else:
                        print(f"   ❌ HTTP Error: {response.status}")
                        
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(debug_failed_extractions())
