#!/usr/bin/env python3
"""
Non-interactive version of job description extraction
"""

import asyncio
from job_description_extractor import JobDescriptionExtractor

async def main():
    """Run extraction with default settings"""
    print("Starting Job Description Extraction...")
    print("=" * 50)
    
    extractor = JobDescriptionExtractor()
    
    try:
        # Run extraction with default settings (all jobs, batch size 20)
        await extractor.run_extraction(limit=None, batch_size=20)
        
    except Exception as e:
        print(f"Extraction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
