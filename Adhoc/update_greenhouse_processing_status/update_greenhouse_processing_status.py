"""
Update Job_postings_greenhouse with processing_status field

This script updates documents in Job_postings_greenhouse with their processing status:
- "matched": Job ID is present in greenhouse_resume_job_matches (job has been processed and has a match)
- "unmatched": Job ID is present in greenhouse_unmatched_job_postings (job has been processed but no match found)
- "not processed": Job matches the filter but hasn't been processed yet

Usage:
    python update_greenhouse_processing_status.py [--dry-run] [--force]
"""

import os
import sys
from typing import Dict, Any, Set
from datetime import datetime
import logging
import json
import argparse

# ============================================================================
# CONFIGURATION - Edit these values as needed
# ============================================================================

# Dry run mode: Set to True to preview changes without updating the database
# Set to False to actually update the database
DRY_RUN = False

# Database configuration
DB_NAME = "Resume_study"
BATCH_SIZE = 100

# Job filter configuration
# These filters determine which jobs will be updated with processing_status
JOB_FILTER = {
    "jd_extraction": True,  # Only jobs with successful extraction
    "jd_embedding": {"$exists": True, "$ne": None}  # Only jobs with embeddings
}

# ============================================================================
# END CONFIGURATION
# ============================================================================

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from libs.mongodb import _get_mongo_client

# Initialize basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def get_logger(name):
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(name)

logger = get_logger(__name__)

class GreenhouseProcessingStatusUpdater:
    """Updates Job_postings_greenhouse with processing_status based on matches and unmatched collections."""
    
    def __init__(self, dry_run: bool = True, job_filter: Dict[str, Any] = None):
        """
        Initialize the updater.
        
        Args:
            dry_run: If True, only log what would be updated without making changes
            job_filter: MongoDB query filter for jobs. Uses JOB_FILTER from config if not provided.
        """
        self.dry_run = dry_run
        self.job_filter = job_filter or JOB_FILTER
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[DB_NAME]
        self.job_collection = self.db["Job_postings_greenhouse"]
        self.matches_collection = self.db["greenhouse_resume_job_matches"]
        self.unmatched_collection = self.db["greenhouse_unmatched_job_postings"]
        
        logger.info(f"GreenhouseProcessingStatusUpdater initialized (DRY_RUN={dry_run})")
        logger.info(f"Using filter: {self.job_filter}")
    
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
    
    def get_filtered_jobs(self):
        """
        Get jobs matching the configured filter.
        
        Returns:
            List of job documents matching the filter
        """
        try:
            logger.info(f"Querying jobs with filter: {self.job_filter}")
            
            jobs = list(self.job_collection.find(self.job_filter))
            logger.info(f"Found {len(jobs)} jobs matching the filter")
            
            return jobs
            
        except Exception as e:
            logger.error(f"Error getting filtered jobs: {e}")
            return []
    
    def update_job_statuses(self, processed_ids: Dict[str, Set[str]], jobs: list) -> Dict[str, Any]:
        """
        Update Job_postings_greenhouse documents with processing status.
        
        Args:
            processed_ids: Dictionary with 'matched' and 'unmatched' sets of job IDs
            jobs: List of job documents to update
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_jobs": len(jobs),
            "updated_matched": 0,
            "updated_unmatched": 0,
            "updated_not_processed": 0,
            "skipped_already_updated": 0,
            "errors": 0
        }
        
        logger.info(f"Starting job status updates for {len(jobs)} jobs...")
        
        try:
            matched_ids = processed_ids["matched"]
            unmatched_ids = processed_ids["unmatched"]
            
            # Process in batches
            total_batches = (len(jobs) + BATCH_SIZE - 1) // BATCH_SIZE
            for i in range(0, len(jobs), BATCH_SIZE):
                batch = jobs[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)")
                
                for job in batch:
                    try:
                        job_id = job["_id"]
                        job_id_str = str(job_id)
                        
                        # Determine status
                        if job_id_str in matched_ids:
                            status = "matched"
                        elif job_id_str in unmatched_ids:
                            status = "unmatched"
                        else:
                            status = "not processed"
                        
                        # Check if status already exists and matches
                        current_status = job.get("processing_status")
                        if current_status == status:
                            stats["skipped_already_updated"] += 1
                            continue
                        
                        # Prepare update
                        update_fields = {
                            "processing_status": status,
                            "processing_status_updated_at": datetime.now()
                        }
                        
                        # Update document
                        if self.dry_run:
                            logger.debug(f"[DRY RUN] Would update job {job_id_str} ({job.get('title', 'Unknown')}) with status: {status}")
                        else:
                            result = self.job_collection.update_one(
                                {"_id": job_id},
                                {"$set": update_fields}
                            )
                            
                            if result.modified_count > 0:
                                logger.debug(f"Updated job {job_id_str} ({job.get('title', 'Unknown')}) with status: {status}")
                            elif result.matched_count > 0:
                                # Document matched but wasn't modified (status already correct)
                                stats["skipped_already_updated"] += 1
                                continue
                            else:
                                logger.warning(f"Failed to update job {job_id_str} - document not found")
                                stats["errors"] += 1
                                continue
                        
                        # Update stats
                        if status == "matched":
                            stats["updated_matched"] += 1
                        elif status == "unmatched":
                            stats["updated_unmatched"] += 1
                        elif status == "not processed":
                            stats["updated_not_processed"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing job {job.get('_id')}: {e}")
                        stats["errors"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in update_job_statuses: {e}")
            return stats
    
    def run(self) -> Dict[str, Any]:
        """Run the complete update process."""
        logger.info("Starting greenhouse processing status update process...")
        start_time = datetime.now()
        
        # Get processed job IDs
        processed_ids = self.get_processed_job_ids()
        
        # Get jobs matching the filter
        jobs = self.get_filtered_jobs()
        
        if not jobs:
            logger.warning("No jobs found matching the filter. Nothing to update.")
            return {
                "error": "No jobs found matching the filter",
                "duration": str(datetime.now() - start_time)
            }
        
        # Update job statuses
        stats = self.update_job_statuses(processed_ids, jobs)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Log summary
        logger.info("=" * 60)
        logger.info("=== UPDATE SUMMARY ===")
        logger.info("=" * 60)
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Filter used: {self.job_filter}")
        logger.info(f"Total jobs matching filter: {stats['total_jobs']}")
        logger.info(f"Matched jobs found in collections: {len(processed_ids['matched'])}")
        logger.info(f"Unmatched jobs found in collections: {len(processed_ids['unmatched'])}")
        logger.info(f"Updated with 'matched' status: {stats['updated_matched']}")
        logger.info(f"Updated with 'unmatched' status: {stats['updated_unmatched']}")
        logger.info(f"Updated with 'not processed' status: {stats['updated_not_processed']}")
        logger.info(f"Skipped (already updated): {stats['skipped_already_updated']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("=" * 60)
        
        return {
            **stats,
            "duration": str(duration),
            "dry_run": self.dry_run,
            "filter": self.job_filter,
            "processed_ids_count": {
                "matched": len(processed_ids["matched"]),
                "unmatched": len(processed_ids["unmatched"]),
                "total": len(processed_ids["matched"]) + len(processed_ids["unmatched"])
            }
        }

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Update Greenhouse job postings with processing_status field"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=None,
        help="Run in dry-run mode (overrides DRY_RUN config at top of script)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Actually update the database (disables dry-run mode, overrides DRY_RUN config)"
    )
    
    args = parser.parse_args()
    
    # Determine dry_run mode: command-line args override config
    if args.force:
        dry_run = False
    elif args.dry_run is not None:
        dry_run = args.dry_run
    else:
        # Use the DRY_RUN value from the top of the script
        dry_run = DRY_RUN
    
    try:
        logger.info("=" * 60)
        logger.info("=== Greenhouse Processing Status Update Script ===")
        logger.info("=" * 60)
        logger.info(f"DRY_RUN mode: {dry_run} (from {'command-line' if args.force or args.dry_run is not None else 'script config'})")
        
        if not dry_run:
            logger.warning("Running in LIVE UPDATE mode!")
            response = input("Proceed with database updates? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Cancelled by user")
                return
        else:
            logger.info("Running in DRY RUN mode - no actual updates will be made")
            logger.info("Change DRY_RUN = False at the top of the script or use --force to actually update the database")
        
        logger.info(f"Using filter: {JOB_FILTER}")
        
        updater = GreenhouseProcessingStatusUpdater(dry_run=dry_run, job_filter=JOB_FILTER)
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

