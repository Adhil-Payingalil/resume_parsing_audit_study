#!/usr/bin/env python3
"""
Test script for job_description_dynamic_extractor.py
This script helps test the dynamic extractor with a small sample of failed jobs.
"""

import asyncio
import os
from dotenv import load_dotenv
from job_description_dynamic_extractor import JobDescriptionDynamicExtractor

# Load environment variables
load_dotenv()

def test_dynamic_extractor():
    """Test the dynamic extractor with a small sample"""
    print("Testing Job Description Dynamic Extractor")
    print("=" * 50)
    
    # Check environment variables
    if not os.getenv("AGENTQL_API_KEY"):
        print("❌ AGENTQL_API_KEY not found in environment variables")
        return
    
    if not os.getenv("MONGODB_URI"):
        print("❌ MONGODB_URI not found in environment variables")
        return
    
    extractor = JobDescriptionDynamicExtractor()
    
    try:
        # Setup MongoDB connection
        asyncio.run(extractor.setup_mongodb_connection())
        
        # Get a small sample of failed jobs (limit to 3 for testing)
        failed_jobs = asyncio.run(extractor.get_failed_jobs(limit=3))
        
        if not failed_jobs:
            print("✅ No failed jobs found - all jobs have been processed!")
            return
        
        print(f"Found {len(failed_jobs)} failed jobs to test:")
        for i, job in enumerate(failed_jobs, 1):
            print(f"  {i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
            print(f"     URL: {job.get('job_link', 'No URL')}")
            if job.get('api_error'):
                print(f"     Previous error: {job.get('api_error')}")
            print()
        
        # Ask user if they want to proceed with test
        proceed = input("Do you want to proceed with testing these jobs? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Test cancelled.")
            return
        
        # Run the dynamic extraction with the test jobs
        print("\nStarting test extraction...")
        extractor.run_retry_extraction(limit=3, batch_size=1)  # Small batch for testing
        
        print("\n✅ Test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_dynamic_extractor()
