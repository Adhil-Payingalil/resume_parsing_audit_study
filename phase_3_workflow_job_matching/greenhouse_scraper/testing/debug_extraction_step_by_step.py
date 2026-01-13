#!/usr/bin/env python3
"""
Debug the extraction logic step by step
"""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os

load_dotenv()

async def debug_extraction():
    """Debug the extraction logic step by step"""
    
    test_url = "https://job-boards.greenhouse.io/partnerstack/jobs/4607080005?gh_src=my.greenhouse.search"
    jina_url = f"https://r.jina.ai/{test_url}"
    headers = {'Authorization': f'Bearer {os.getenv("JINAAI_API_KEY")}'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(jina_url, headers=headers) as response:
            if response.status == 200:
                content = await response.text()
                lines = content.split('\n')
                
                print("Step-by-step extraction debug:")
                print("=" * 60)
                
                # Simulate the extraction logic
                description_started = False
                description_lines = []
                
                job_keywords = [
                    'job description', 'about the role', 'what you\'ll do', 
                    'responsibilities', 'requirements', 'qualifications',
                    'what we\'re looking for', 'role overview', 'position overview',
                    'about this role', 'key responsibilities', 'job summary',
                    'role summary', 'position summary', 'we are looking for',
                    'the ideal candidate', 'you will be responsible',
                    'about you and the role', 'about the position', 'about this position',
                    'the role', 'this role', 'position details', 'job details',
                    'what you\'ll be doing', 'what you will do', 'key duties',
                    'main responsibilities', 'primary responsibilities'
                ]
                
                for i, line in enumerate(lines[:50]):  # Check first 50 lines
                    line_stripped = line.strip()
                    line_lower = line_stripped.lower()
                    
                    print(f"Line {i}: {line_stripped[:80]}...")
                    
                    # Skip empty lines and headers
                    if not line_stripped or line_stripped.startswith('#'):
                        if description_started:
                            description_lines.append(line_stripped)
                            print(f"  -> Added to description (continued)")
                        else:
                            print(f"  -> Skipped (empty/header, not started)")
                        continue
                    
                    # Look for job description indicators
                    found_keyword = None
                    for keyword in job_keywords:
                        if keyword in line_lower:
                            found_keyword = keyword
                            break
                    
                    if found_keyword:
                        description_started = True
                        description_lines.append(line_stripped)
                        print(f"  -> ✅ FOUND KEYWORD: '{found_keyword}' - Started extraction!")
                    elif description_started and not line_stripped.startswith('#'):
                        description_lines.append(line_stripped)
                        print(f"  -> Added to description (continued)")
                    else:
                        print(f"  -> Skipped (no keyword, not started)")
                
                # Clean up the description
                extracted_description = '\n'.join(description_lines).strip()
                
                print(f"\nExtraction result:")
                print(f"Description started: {description_started}")
                print(f"Description lines: {len(description_lines)}")
                print(f"Extracted length: {len(extracted_description)}")
                print(f"First 300 chars: {extracted_description[:300]}...")
                
                if len(extracted_description) >= 100:
                    print("✅ Extraction should succeed!")
                else:
                    print("❌ Extraction failed - too short")

if __name__ == "__main__":
    asyncio.run(debug_extraction())
