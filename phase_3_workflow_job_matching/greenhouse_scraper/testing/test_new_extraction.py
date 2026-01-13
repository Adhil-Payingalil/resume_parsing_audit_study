#!/usr/bin/env python3
"""
Test the new extraction logic with jd_extraction flag
"""

import asyncio
from job_description_extractor import JobDescriptionExtractor

async def test_new_extraction():
    """Test the new extraction logic"""
    print("Testing New Job Description Extraction Logic")
    print("=" * 60)
    
    extractor = JobDescriptionExtractor()
    
    try:
        # Setup connections
        await extractor.setup_mongodb_connection()
        await extractor.setup_http_session()
        
        # Test with a job that should have clean extraction
        test_url = "https://job-boards.greenhouse.io/partnerstack/jobs/4607080005?gh_src=my.greenhouse.search"
        print(f"Testing with URL: {test_url}")
        
        job_id, result = await extractor.fetch_job_description(test_url, "test_job")
        
        if result:
            description, jd_extraction_success = result
            print(f"✅ Extraction successful!")
            print(f"Description length: {len(description)} characters")
            print(f"JD Extraction Success: {jd_extraction_success}")
            print(f"First 200 chars: {description[:200]}...")
            
            if jd_extraction_success:
                print("🎯 Clean job description extracted!")
            else:
                print("📄 Using full Jina AI content (extraction failed)")
        else:
            print("❌ Extraction failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if extractor.session:
            await extractor.session.close()
        if extractor.mongo_client:
            extractor.mongo_client.close()

if __name__ == "__main__":
    asyncio.run(test_new_extraction())
