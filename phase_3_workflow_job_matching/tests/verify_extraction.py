import sys
import os
import asyncio

# Add project root to path
import pathlib
project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from phase_3_workflow_job_matching.src.embeddings.greenhouse_job_embedder import GreenhouseJobEmbeddingProcessor
from libs.mongodb import _get_mongo_client

async def verify():
    print("Verifying new extraction logic...")
    
    # Initialize processor
    # We can pass cycle=14 since we know there are jobs there
    processor = GreenhouseJobEmbeddingProcessor(cycle=14)
    
    # Fetch a few jobs manually to test the extraction function
    client = _get_mongo_client()
    db = client["Resume_study"]
    collection = db["Job_postings_greenhouse"]
    
    jobs = list(collection.find({"cycle": 14, "jd_extraction": True}).limit(3))
    
    for i, job in enumerate(jobs):
        print(f"\n--- Job {i+1}: {job.get('title')} ---")
        
        # Run extraction
        content = processor.extract_greenhouse_job_content(job)
        
        print(f"Extracted Length: {len(content)}")
        print("First 200 chars:")
        print(content[:200])
        print("..." if len(content) > 400 else "")
        print("Last 200 chars:")
        print(content[-200:])
        
        # Basic assertions
        if len(content) > 8000:
            print("[FAIL] Test Failed: Content > 8000 chars")
        else:
            print("[PASS] Length Check Passed")
            
        if "Requirements" in content or "qualifications" in content.lower():
             print("[PASS] Content Check: Likely contains requirements")
        else:
             print("[WARN] Warning: 'Requirements' keyword not found (might be valid depending on job)")

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(verify())
