#!/usr/bin/env python3
"""
Debug script to see what keywords are in the job content
"""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os

load_dotenv()

async def debug_keywords():
    """Debug what keywords are in the job content"""
    
    test_url = "https://job-boards.greenhouse.io/partnerstack/jobs/4607080005?gh_src=my.greenhouse.search"
    jina_url = f"https://r.jina.ai/{test_url}"
    headers = {'Authorization': f'Bearer {os.getenv("JINAAI_API_KEY")}'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(jina_url, headers=headers) as response:
            if response.status == 200:
                content = await response.text()
                lines = content.split('\n')
                
                print("Looking for job description keywords in content:")
                print("=" * 60)
                
                job_keywords = [
                    'job description', 'about the role', 'what you\'ll do', 
                    'responsibilities', 'requirements', 'qualifications',
                    'what we\'re looking for', 'role overview', 'position overview',
                    'about this role', 'key responsibilities', 'job summary',
                    'role summary', 'position summary', 'we are looking for',
                    'the ideal candidate', 'you will be responsible'
                ]
                
                found_keywords = []
                for i, line in enumerate(lines[:30]):  # Check first 30 lines
                    line_lower = line.lower()
                    for keyword in job_keywords:
                        if keyword in line_lower:
                            found_keywords.append((keyword, i, line.strip()[:100]))
                
                if found_keywords:
                    print("Found keywords:")
                    for keyword, line_num, line_content in found_keywords:
                        print(f"  Line {line_num}: '{keyword}' in '{line_content}...'")
                else:
                    print("No job description keywords found in first 30 lines")
                    print("\nFirst 20 lines of content:")
                    for i, line in enumerate(lines[:20]):
                        print(f"  {i}: {line.strip()[:100]}...")
                
                # Check if there are any job-related terms at all
                job_terms = ['role', 'position', 'job', 'responsibilities', 'requirements', 'qualifications', 'skills', 'experience']
                found_terms = []
                for line in lines[:50]:
                    line_lower = line.lower()
                    for term in job_terms:
                        if term in line_lower and term not in [t[0] for t in found_terms]:
                            found_terms.append((term, line.strip()[:100]))
                
                print(f"\nFound job-related terms:")
                for term, line_content in found_terms[:10]:  # Show first 10
                    print(f"  '{term}' in '{line_content}...'")

if __name__ == "__main__":
    asyncio.run(debug_keywords())
