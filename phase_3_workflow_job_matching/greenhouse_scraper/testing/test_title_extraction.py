#!/usr/bin/env python3
"""
Test the new title extraction functionality
"""

import asyncio
from job_description_extractor import JobDescriptionExtractor

async def test_title_extraction():
    """Test the title extraction functionality"""
    print("Testing Title Extraction in Job Descriptions")
    print("=" * 60)
    
    extractor = JobDescriptionExtractor()
    
    try:
        # Setup connections
        await extractor.setup_mongodb_connection()
        await extractor.setup_http_session()
        
        # Test with a job that should have clean extraction
        test_url = "https://job-boards.greenhouse.io/partnerstack/jobs/4607080005?gh_src=my.greenhouse.search"
        test_title = "Product Designer"
        print(f"Testing with URL: {test_url}")
        print(f"Job Title: {test_title}")
        
        job_id, result = await extractor.fetch_job_description(test_url, "test_job", test_title)
        
        if result:
            description, jd_extraction_success = result
            print(f"✅ Extraction successful!")
            print(f"Description length: {len(description)} characters")
            print(f"JD Extraction Success: {jd_extraction_success}")
            print(f"First 300 chars: {description[:300]}...")
            
            if jd_extraction_success:
                print("🎯 Clean job description with title extracted!")
                if description.startswith(f"# {test_title}"):
                    print("✅ Title correctly added to clean extraction!")
                else:
                    print("❌ Title not found at start of description")
            else:
                print("📄 Using full Jina AI content (extraction failed)")
                if test_title in description:
                    print("ℹ️ Title found in full content (expected)")
                else:
                    print("ℹ️ Title not in full content (expected for Jina AI response)")
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
    asyncio.run(test_title_extraction())
