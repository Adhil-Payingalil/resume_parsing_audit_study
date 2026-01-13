#!/usr/bin/env python3
"""
Test the improved extraction logic
"""

import asyncio
import aiohttp
from dotenv import load_dotenv
import os

load_dotenv()

def extract_description_from_content(content: str):
    """Improved extraction logic"""
    try:
        # Check for common non-job content patterns
        content_lower = content.lower()
        non_job_patterns = [
            'equal employment opportunity',
            'government reporting purposes',
            'self-identification survey',
            'veterans readjustment assistance',
            'federal contractor',
            'omb control number',
            'expires 04/30/2026',
            'form cc-305',
            'page 1 of 1'
        ]
        
        # If content contains non-job patterns, it's likely a form or redirect
        if any(pattern in content_lower for pattern in non_job_patterns):
            print("⚠️ Content appears to be a form or redirect, not a job description")
            return None
        
        # Jina AI returns markdown content, we need to extract the job description part
        lines = content.split('\n')
        
        # Look for common job description patterns
        description_started = False
        description_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and headers
            if not line or line.startswith('#'):
                if description_started:
                    description_lines.append(line)
                continue
            
            # Look for job description indicators
            if any(keyword in line.lower() for keyword in [
                'job description', 'about the role', 'what you\'ll do', 
                'responsibilities', 'requirements', 'qualifications',
                'what we\'re looking for', 'role overview', 'position overview',
                'about this role', 'key responsibilities', 'job summary',
                'role summary', 'position summary', 'we are looking for',
                'the ideal candidate', 'you will be responsible'
            ]):
                description_started = True
                description_lines.append(line)
            elif description_started and not line.startswith('#'):
                description_lines.append(line)
        
        # Clean up the description
        description = '\n'.join(description_lines).strip()
        
        # Filter out very short descriptions (likely not job descriptions)
        if len(description) < 100:
            return None
            
        return description
        
    except Exception as e:
        print(f"Error extracting description from content: {e}")
        return None

async def test_improved_extraction():
    """Test the improved extraction logic"""
    
    # Test with the failed URL
    test_url = "https://job-boards.greenhouse.io/celestialai/jobs/4608191005?gh_src=my.greenhouse.search"
    jina_url = f"https://r.jina.ai/{test_url}"
    headers = {'Authorization': f'Bearer {os.getenv("JINAAI_API_KEY")}'}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(jina_url, headers=headers) as response:
            if response.status == 200:
                content = await response.text()
                print("Testing improved extraction logic:")
                print("=" * 50)
                
                description = extract_description_from_content(content)
                
                if description:
                    print(f"✅ Success! Extracted {len(description)} characters")
                    print(f"Description: {description[:300]}...")
                else:
                    print("❌ No description extracted (correctly identified as non-job content)")
                    
                # Test with a working URL
                print("\n" + "=" * 50)
                print("Testing with a working URL:")
                
                working_url = "https://job-boards.eu.greenhouse.io/valtech/jobs/4672705101?gh_src=my.greenhouse.search"
                working_jina_url = f"https://r.jina.ai/{working_url}"
                
                async with session.get(working_jina_url, headers=headers) as response2:
                    if response2.status == 200:
                        content2 = await response2.text()
                        description2 = extract_description_from_content(content2)
                        
                        if description2:
                            print(f"✅ Success! Extracted {len(description2)} characters")
                            print(f"Description: {description2[:300]}...")
                        else:
                            print("❌ No description extracted")

if __name__ == "__main__":
    asyncio.run(test_improved_extraction())
