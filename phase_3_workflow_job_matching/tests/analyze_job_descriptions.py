import os
import sys
from typing import Dict, Any, List

# Add project root to path
import pathlib
project_root = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from libs.mongodb import _get_mongo_client

def analyze_job_descriptions(cycle: float = 14, limit: int = 5):
    """
    Fetch and display job descriptions from the specified cycle.
    """
    client = _get_mongo_client()
    if not client:
        print("Failed to connect to MongoDB")
        return

    db = client["Resume_study"]
    collection = db["Job_postings_greenhouse"]

    print(f"Fetching {limit} jobs for cycle {cycle}...")
    
    query = {"cycle": cycle, "jd_extraction": True}
    cursor = collection.find(query).limit(limit)
    
    jobs = list(cursor)
    
    if not jobs:
        print(f"No jobs found for cycle {cycle}")
        # Try finding ANY job to see if cycle is the issue
        print("Checking available cycles...")
        cycles = collection.distinct("cycle")
        print(f"Available cycles: {cycles}")
        return

    print(f"Found {len(jobs)} jobs. Analyzing content...\n")
    
    for i, job in enumerate(jobs):
        title = job.get("title", "Unknown Title")
        desc = job.get("job_description", "")
        
        print(f"--- Job {i+1}: {title} ---")
        print(f"Total Length: {len(desc)} characters")
        print("First 500 chars:")
        print(desc[:500])
        print("\nLast 500 chars:")
        print(desc[-500:] if len(desc) > 500 else desc)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    analyze_job_descriptions(cycle=14, limit=3)
