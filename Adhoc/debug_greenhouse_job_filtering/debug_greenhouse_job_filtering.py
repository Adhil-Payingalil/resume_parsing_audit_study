"""
Debug script to understand why jobs are being filtered out incorrectly.

This script will:
1. Count jobs matching the filter (with cycle: 6)
2. Count processed job IDs from matches/unmatched collections
3. Check if there's a type mismatch (ObjectId vs string)
4. Show which jobs are being incorrectly excluded
"""

import os
import sys
from bson import ObjectId

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from libs.mongodb import _get_mongo_client

# Import greenhouse_config from the correct path
greenhouse_config_path = os.path.join(project_root, "Phase 3 Workflow - Job Matching", "Resume Job Matching")
if greenhouse_config_path not in sys.path:
    sys.path.insert(0, greenhouse_config_path)

from greenhouse_config import GreenhouseConfig

def main():
    config = GreenhouseConfig()
    mongo_client = _get_mongo_client()
    db = mongo_client[config.db_name]
    
    job_collection = db["Job_postings_greenhouse"]
    matches_collection = db["greenhouse_resume_job_matches"]
    unmatched_collection = db["greenhouse_unmatched_job_postings"]
    
    # Get the filter query
    query = config.get_job_query()
    print("=" * 60)
    print("FILTER QUERY:")
    print(f"  {query}")
    print("=" * 60)
    
    # Count jobs matching the filter
    jobs_matching_filter = list(job_collection.find(query))
    print(f"\nJobs matching filter: {len(jobs_matching_filter)}")
    
    # Get processed job IDs
    processed_job_ids = matches_collection.distinct("job_posting_id")
    unmatched_job_ids = unmatched_collection.distinct("job_posting_id")
    
    print(f"\nProcessed job IDs from matches collection: {len(processed_job_ids)}")
    print(f"Processed job IDs from unmatched collection: {len(unmatched_job_ids)}")
    print(f"Total processed job IDs: {len(processed_job_ids) + len(unmatched_job_ids)}")
    
    # Check types
    if processed_job_ids:
        sample_id = processed_job_ids[0]
        print(f"\nSample processed job ID type: {type(sample_id)}")
        print(f"Sample processed job ID value: {sample_id}")
    
    if jobs_matching_filter:
        sample_job_id = jobs_matching_filter[0]["_id"]
        print(f"\nSample job _id type: {type(sample_job_id)}")
        print(f"Sample job _id value: {sample_job_id}")
    
    # Check for overlap
    matching_job_ids = {str(job["_id"]) for job in jobs_matching_filter}
    processed_job_ids_str = {str(pid) for pid in processed_job_ids}
    unmatched_job_ids_str = {str(uid) for uid in unmatched_job_ids}
    
    overlap_matched = matching_job_ids & processed_job_ids_str
    overlap_unmatched = matching_job_ids & unmatched_job_ids_str
    
    print(f"\n" + "=" * 60)
    print("OVERLAP ANALYSIS:")
    print("=" * 60)
    print(f"Jobs matching filter that are in matches collection: {len(overlap_matched)}")
    print(f"Jobs matching filter that are in unmatched collection: {len(overlap_unmatched)}")
    print(f"Total overlap: {len(overlap_matched | overlap_unmatched)}")
    
    if overlap_matched:
        print(f"\nFirst 5 overlapping matched IDs:")
        for oid in list(overlap_matched)[:5]:
            print(f"  {oid}")
    
    if overlap_unmatched:
        print(f"\nFirst 5 overlapping unmatched IDs:")
        for oid in list(overlap_unmatched)[:5]:
            print(f"  {oid}")
    
    # Check if processed jobs have cycle information
    print(f"\n" + "=" * 60)
    print("CHECKING CYCLE INFORMATION IN PROCESSED JOBS:")
    print("=" * 60)
    
    # Sample a few processed jobs to check their cycle
    sample_matched = list(matches_collection.find({}).limit(5))
    sample_unmatched = list(unmatched_collection.find({}).limit(5))
    
    if sample_matched:
        print(f"\nSample matched jobs cycles:")
        for job in sample_matched:
            cycle = job.get("cycle", "NOT SET")
            job_id = job.get("job_posting_id")
            print(f"  Job ID: {job_id}, Cycle: {cycle}")
    
    if sample_unmatched:
        print(f"\nSample unmatched jobs cycles:")
        for job in sample_unmatched:
            cycle = job.get("cycle", "NOT SET")
            job_id = job.get("job_posting_id")
            print(f"  Job ID: {job_id}, Cycle: {cycle}")
    
    # Count how many processed jobs have cycle 6
    matched_cycle_6 = matches_collection.count_documents({"cycle": 6})
    unmatched_cycle_6 = unmatched_collection.count_documents({"cycle": 6})
    
    print(f"\n" + "=" * 60)
    print("CYCLE 6 ANALYSIS:")
    print("=" * 60)
    print(f"Matched jobs with cycle 6: {matched_cycle_6}")
    print(f"Unmatched jobs with cycle 6: {unmatched_cycle_6}")
    print(f"Total processed jobs with cycle 6: {matched_cycle_6 + unmatched_cycle_6}")
    print(f"Jobs matching filter (cycle 6): {len(jobs_matching_filter)}")
    print(f"Expected to be excluded: {matched_cycle_6 + unmatched_cycle_6}")
    print(f"Should be available: {len(jobs_matching_filter) - (matched_cycle_6 + unmatched_cycle_6)}")
    
    print("\n" + "=" * 60)
    print("CONCLUSION:")
    print("=" * 60)
    print("The issue is that distinct() gets ALL job_posting_ids regardless of cycle.")
    print("We should only exclude jobs that match the current filter (cycle: 6).")
    print("=" * 60)

if __name__ == "__main__":
    main()

