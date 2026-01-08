"""
Update Job_postings_greenhouse with processing status

This script updates documents in Job_postings_greenhouse with their processing status:
- "matched": Job ID is present in greenhouse_resume_job_matches (job has been processed and has a match)
- "unmatched": Job ID is present in greenhouse_unmatched_job_postings (job has been processed but no match found)
- Also adds a timestamp field for reference

Usage:
    python update_greenhouse_job_status.py
"""

import os
import sys
from typing import Dict, Any, Set
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from libs.mongodb import _get_mongo_client
import logging
import json

def get_logger(name):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(name)

logger = get_logger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Set to False to actually update the database
DRY_RUN = True

# Database configuration
DB_NAME = "Resume_study"
BATCH_SIZE = 100

# ============================================================================
# END CONFIGURATION
# ============================================================================

class GreenhouseJobStatusUpdater:
    """Updates Job_postings_greenhouse with processing status based on matches and unmatched collections."""
    
    def __init__(self, dry_run: bool = True):
        """
        Initialize the updater.
        
        Args:
            dry_run: If True, only log what would be updated without making changes
        """
        self.dry_run = dry_run
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[DB_NAME]
        self.job_collection = self.db["Job_postings_greenhouse"]
        self.matches_collection = self.db["greenhouse_resume_job_matches"]
        self.unmatched_collection = self.db["greenhouse_unmatched_job_postings"]
        
        logger.info(f"GreenhouseJobStatusUpdater initialized (DRY_RUN={dry_run})")
    
    def get_processed_job_ids(self) -> Dict[str, Set[str]]:
        """
        Get sets of job IDs from matches and unmatched collections.
        
        Returns:
            Dictionary with 'matched' and 'unmatched' sets of job IDs (as strings)
        """
        logger.info("Collecting processed job IDs from matches and unmatched collections...")
        
        matched_ids = set()
        unmatched_ids = set()
        
        try:
            # Get all job_posting_id values from matches collection
            matched_cursor = self.matches_collection.find(
                {"job_posting_id": {"$exists": True, "$ne": None}},
                {"job_posting_id": 1}
            )
            
            for doc in matched_cursor:
                job_id = doc.get("job_posting_id")
                if job_id:
                    # Convert ObjectId to string if needed
                    matched_ids.add(str(job_id))
            
            logger.info(f"Found {len(matched_ids)} job IDs in greenhouse_resume_job_matches")
            
            # Get all job_posting_id values from unmatched collection
            unmatched_cursor = self.unmatched_collection.find(
                {"job_posting_id": {"$exists": True, "$ne": None}},
                {"job_posting_id": 1}
            )
            
            for doc in unmatched_cursor:
                job_id = doc.get("job_posting_id")
                if job_id:
                    # Convert ObjectId to string if needed
                    unmatched_ids.add(str(job_id))
            
            logger.info(f"Found {len(unmatched_ids)} job IDs in greenhouse_unmatched_job_postings")
            
            # Check for overlap (shouldn't happen, but log if it does)
            overlap = matched_ids & unmatched_ids
            if overlap:
                logger.warning(f"Found {len(overlap)} job IDs present in both collections! "
                             f"This shouldn't happen. Overlapping IDs: {list(overlap)[:10]}")
            
            return {
                "matched": matched_ids,
                "unmatched": unmatched_ids
            }
            
        except Exception as e:
            logger.error(f"Error collecting processed job IDs: {e}")
            return {"matched": set(), "unmatched": set()}
    
    def update_job_statuses(self, processed_ids: Dict[str, Set[str]]) -> Dict[str, Any]:
        """
        Update Job_postings_greenhouse documents with processing status.
        
        Args:
            processed_ids: Dictionary with 'matched' and 'unmatched' sets of job IDs
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_jobs": 0,
            "updated_matched": 0,
            "updated_unmatched": 0,
            "skipped_no_status": 0,
            "skipped_already_updated": 0,
            "errors": 0
        }
        
        logger.info("Starting job status updates...")
        
        try:
            # Get all jobs from Job_postings_greenhouse
            all_jobs = list(self.job_collection.find({}))
            stats["total_jobs"] = len(all_jobs)
            logger.info(f"Found {len(all_jobs)} documents in Job_postings_greenhouse")
            
            if not all_jobs:
                logger.warning("No documents found in Job_postings_greenhouse!")
                return stats
            
            matched_ids = processed_ids["matched"]
            unmatched_ids = processed_ids["unmatched"]
            
            # Process in batches
            total_batches = (len(all_jobs) + BATCH_SIZE - 1) // BATCH_SIZE
            for i in range(0, len(all_jobs), BATCH_SIZE):
                batch = all_jobs[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                logger.info(f"Processing batch {batch_num}/{total_batches}")
                
                for job in batch:
                    try:
                        job_id = job["_id"]
                        job_id_str = str(job_id)
                        
                        # Determine status
                        status = None
                        if job_id_str in matched_ids:
                            status = "matched"
                        elif job_id_str in unmatched_ids:
                            status = "unmatched"
                        else:
                            # Job not processed yet - skip
                            stats["skipped_no_status"] += 1
                            continue
                        
                        # Check if status already exists and matches
                        current_status = job.get("processing_status")
                        if current_status == status:
                            stats["skipped_already_updated"] += 1
                            logger.debug(f"Job {job_id_str} already has status '{status}', skipping")
                            continue
                        
                        # Prepare update
                        update_fields = {
                            "processing_status": status,
                            "processing_status_updated_at": datetime.now()
                        }
                        
                        # Update document
                        if self.dry_run:
                            logger.info(f"[DRY RUN] Would update job {job_id_str} with status: {status}")
                        else:
                            result = self.job_collection.update_one(
                                {"_id": job_id},
                                {"$set": update_fields}
                            )
                            
                            if result.modified_count > 0:
                                logger.debug(f"Updated job {job_id_str} with status: {status}")
                            else:
                                logger.warning(f"Failed to update job {job_id_str}")
                                stats["errors"] += 1
                                continue
                        
                        # Update stats
                        if status == "matched":
                            stats["updated_matched"] += 1
                        elif status == "unmatched":
                            stats["updated_unmatched"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing job {job.get('_id')}: {e}")
                        stats["errors"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in update_job_statuses: {e}")
            return stats
    
    def run(self) -> Dict[str, Any]:
        """Run the complete update process."""
        logger.info("Starting greenhouse job status update process...")
        start_time = datetime.now()
        
        # Get processed job IDs
        processed_ids = self.get_processed_job_ids()
        
        # Check if we have any processed jobs
        total_processed = len(processed_ids["matched"]) + len(processed_ids["unmatched"])
        if total_processed == 0:
            logger.warning("No processed job IDs found. Nothing to update.")
            return {
                "error": "No processed job IDs found",
                "duration": str(datetime.now() - start_time)
            }
        
        # Update job statuses
        stats = self.update_job_statuses(processed_ids)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Log summary
        logger.info("=== UPDATE SUMMARY ===")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Total jobs in collection: {stats['total_jobs']}")
        logger.info(f"Matched jobs found: {len(processed_ids['matched'])}")
        logger.info(f"Unmatched jobs found: {len(processed_ids['unmatched'])}")
        logger.info(f"Updated with 'matched' status: {stats['updated_matched']}")
        logger.info(f"Updated with 'unmatched' status: {stats['updated_unmatched']}")
        logger.info(f"Skipped (not processed): {stats['skipped_no_status']}")
        logger.info(f"Skipped (already updated): {stats['skipped_already_updated']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("======================")
        
        return {
            **stats,
            "duration": str(duration),
            "dry_run": self.dry_run,
            "processed_ids_count": {
                "matched": len(processed_ids["matched"]),
                "unmatched": len(processed_ids["unmatched"]),
                "total": total_processed
            }
        }

def main():
    """Main function."""
    try:
        logger.info("=== Greenhouse Job Status Update Script ===")
        logger.info(f"DRY_RUN mode: {DRY_RUN}")
        
        if not DRY_RUN:
            logger.warning("Running in LIVE UPDATE mode!")
            response = input("Proceed? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Cancelled")
                return
        else:
            logger.info("Running in DRY RUN mode - no actual updates")
        
        updater = GreenhouseJobStatusUpdater(dry_run=DRY_RUN)
        results = updater.run()
        
        if "error" in results:
            logger.error(f"Update failed: {results['error']}")
            return
        
        logger.info("Update completed!")
        
        # Save results
        results_file = f"update_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        results_path = os.path.join(os.path.dirname(__file__), results_file)
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to: {results_path}")
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        raise

if __name__ == "__main__":
    main()

