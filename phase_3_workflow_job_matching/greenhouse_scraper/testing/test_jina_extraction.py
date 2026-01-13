#!/usr/bin/env python3
"""
Test script for Jina AI job description extraction
This script tests the extraction with a single job URL to verify the setup
"""

import asyncio
import os
from dotenv import load_dotenv
from job_description_extractor import JobDescriptionExtractor

load_dotenv()

async def test_single_extraction():
    """Test extraction with a single job URL"""
    print("Testing Jina AI Job Description Extraction")
    print("=" * 50)
    
    # Test URL (you can replace this with an actual job URL from your database)
    test_url = "https://job-boards.greenhouse.io/partnerstack/jobs/4607080005?gh_src=my.greenhouse.search"
    
    extractor = JobDescriptionExtractor()
    
    try:
        # Setup connections
        await extractor.setup_mongodb_connection()
        await extractor.setup_http_session()
        
        print(f"Testing extraction for URL: {test_url}")
        
        # Test single extraction
        job_id, description = await extractor.fetch_job_description(test_url, "test_job")
        
        if description:
            print("✅ Extraction successful!")
            print(f"Description length: {len(description)} characters")
            print(f"First 200 characters: {description[:200]}...")
        else:
            print("❌ Extraction failed")
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
    finally:
        if extractor.session:
            await extractor.session.close()
        if extractor.mongo_client:
            extractor.mongo_client.close()

async def test_mongodb_connection():
    """Test MongoDB connection and count jobs without descriptions"""
    print("\nTesting MongoDB Connection")
    print("=" * 30)
    
    extractor = JobDescriptionExtractor()
    
    try:
        await extractor.setup_mongodb_connection()
        
        # Count total jobs
        total_jobs = extractor.collection.count_documents({})
        print(f"Total jobs in database: {total_jobs}")
        
        # Count jobs without descriptions
        jobs_without_descriptions = await extractor.get_jobs_without_descriptions(limit=5)
        print(f"Jobs without descriptions (sample of 5): {len(jobs_without_descriptions)}")
        
        if jobs_without_descriptions:
            print("Sample job URLs:")
            for i, job in enumerate(jobs_without_descriptions[:3], 1):
                print(f"  {i}. {job.get('title', 'No title')} - {job.get('job_link', 'No URL')}")
        
    except Exception as e:
        print(f"❌ MongoDB test failed: {e}")
    finally:
        if extractor.mongo_client:
            extractor.mongo_client.close()

async def main():
    """Run all tests"""
    print("Jina AI Job Description Extractor - Test Suite")
    print("=" * 60)
    
    # Check environment variables
    if not os.getenv("JINAAI_API_KEY"):
        print("❌ JINAAI_API_KEY not found in environment variables")
        return
    
    if not os.getenv("MONGODB_URI"):
        print("❌ MONGODB_URI not found in environment variables")
        return
    
    print("✅ Environment variables found")
    
    # Test MongoDB connection
    await test_mongodb_connection()
    
    # Test single extraction
    await test_single_extraction()
    
    print("\n" + "=" * 60)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(main())
