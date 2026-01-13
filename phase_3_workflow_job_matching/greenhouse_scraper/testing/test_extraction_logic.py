#!/usr/bin/env python3
"""
Test the extraction logic with a failed job URL
"""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os

load_dotenv()

async def test_extraction_logic():
    """Test the extraction logic with a real failed URL"""
    
    # Use one of the failed URLs
    test_url = "https://job-boards.greenhouse.io/celestialai/jobs/4608191005?gh_src=my.greenhouse.search"
    jina_url = f"https://r.jina.ai/{test_url}"
    headers = {'Authorization': f'Bearer {os.getenv("JINAAI_API_KEY")}'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(jina_url, headers=headers) as response:
            if response.status == 200:
                content = await response.text()
                print("Raw content from Jina AI:")
                print("=" * 60)
                print(content[:1000])  # First 1000 characters
                print("=" * 60)
                
                # Test current extraction logic
                lines = content.split('\n')
                description_started = False
                description_lines = []
                
                print("\nTesting current extraction logic:")
                print("Looking for keywords: job description, about the role, what you'll do, responsibilities, requirements, qualifications, what we're looking for, role overview")
                
                for i, line in enumerate(lines[:50]):  # Check first 50 lines
                    line = line.strip()
                    print(f"Line {i}: {line[:100]}...")
                    
                    if not line or line.startswith('#'):
                        if description_started:
                            description_lines.append(line)
                        continue
                    
                    # Look for job description indicators
                    if any(keyword in line.lower() for keyword in [
                        'job description', 'about the role', 'what you\'ll do', 
                        'responsibilities', 'requirements', 'qualifications',
                        'what we\'re looking for', 'role overview'
                    ]):
                        print(f"  ✅ Found keyword in line {i}: {line}")
                        description_started = True
                        description_lines.append(line)
                    elif description_started and not line.startswith('#'):
                        description_lines.append(line)
                
                description = '\n'.join(description_lines).strip()
                print(f"\nExtracted description length: {len(description)}")
                print(f"Description: {description[:500]}...")
                
                if len(description) < 100:
                    print("❌ Description too short - this is why extraction failed!")
                else:
                    print("✅ Description should have been extracted")

if __name__ == "__main__":
    asyncio.run(test_extraction_logic())
