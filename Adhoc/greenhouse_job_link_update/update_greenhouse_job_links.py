"""
# Greenhouse Job Link Update Script

This script adds job_link field to all existing documents in the greenhouse_resume_job_matches 
collection by looking up the job_posting_id in the Job_postings_greenhouse collection.

This is a one-time use script to fix existing data that doesn't have job_link field.

## Usage:
python update_greenhouse_job_links.py

## What it does:
1. Connects to MongoDB
2. Finds all documents in greenhouse_resume_job_matches without job_link field
3. Looks up job_link from Job_postings_greenhouse using job_posting_id
4. Updates the documents with the job_link field
5. Also updates greenhouse_unmatched_job_postings collection

## Safety:
- Dry run mode by default - set DRY_RUN = False to actually update
- Logs all operations
- Shows progress and statistics
"""

import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime
from bson import ObjectId

# Add project root to path to import libs
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from libs.mongodb import _get_mongo_client
import logging

def get_logger(name):
    """Simple logger setup for the script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(name)

logger = get_logger(__name__)

# Configuration
DRY_RUN = False  # Set to False to actually update the documents
DB_NAME = "Resume_study"
BATCH_SIZE = 100

class GreenhouseJobLinkUpdater:
    """Updates greenhouse job match documents with job_link field."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[DB_NAME]
        self.greenhouse_jobs_collection = self.db["Job_postings_greenhouse"]
        self.matches_collection = self.db["greenhouse_resume_job_matches"]
        self.unmatched_collection = self.db["greenhouse_unmatched_job_postings"]
        
        logger.info(f"GreenhouseJobLinkUpdater initialized (DRY_RUN={dry_run})")
    
    def get_job_link_mapping(self) -> Dict[str, Optional[str]]:
        """
        Get a mapping of job_posting_id to job_link from Job_postings_greenhouse collection.
        
        Returns:
            Dict[str, Optional[str]]: Mapping of job_posting_id to job_link
        """
        logger.info("Building job_posting_id to job_link mapping...")
        
        try:
            # Get all greenhouse jobs with job_link
            greenhouse_jobs = self.greenhouse_jobs_collection.find(
                {"job_link": {"$exists": True}},
                {"_id": 1, "job_link": 1}
            )
            
            mapping = {}
            for job in greenhouse_jobs:
                job_id = str(job["_id"])
                job_link = job.get("job_link")
                mapping[job_id] = job_link
            
            logger.info(f"Built mapping for {len(mapping)} greenhouse jobs")
            return mapping
            
        except Exception as e:
            logger.error(f"Error building job_link mapping: {e}")
            return {}
    
    def find_documents_without_job_link(self, collection_name: str) -> List[Dict[str, Any]]:
        """
        Find all documents in the collection that don't have job_link field.
        
        Args:
            collection_name: Name of the collection to check
            
        Returns:
            List[Dict[str, Any]]: Documents without job_link field
        """
        collection = self.db[collection_name]
        
        try:
            # Find documents without job_link field
            query = {
                "$or": [
                    {"job_link": {"$exists": False}},
                    {"job_link": None}
                ]
            }
            
            documents = list(collection.find(query, {"job_posting_id": 1}))
            logger.info(f"Found {len(documents)} documents in {collection_name} without job_link")
            return documents
            
        except Exception as e:
            logger.error(f"Error finding documents without job_link in {collection_name}: {e}")
            return []
    
    def update_documents_with_job_link(self, collection_name: str, job_link_mapping: Dict[str, Optional[str]]) -> Dict[str, int]:
        """
        Update documents in the collection with job_link field.
        
        Args:
            collection_name: Name of the collection to update
            job_link_mapping: Mapping of job_posting_id to job_link
            
        Returns:
            Dict[str, int]: Statistics about the update operation
        """
        collection = self.db[collection_name]
        stats = {
            "total_documents": 0,
            "updated_documents": 0,
            "skipped_no_mapping": 0,
            "skipped_null_link": 0,
            "errors": 0
        }
        
        logger.info(f"Starting update for {collection_name} collection...")
        
        # Find documents without job_link
        documents = self.find_documents_without_job_link(collection_name)
        stats["total_documents"] = len(documents)
        
        if not documents:
            logger.info(f"No documents to update in {collection_name}")
            return stats
        
        # Process in batches
        for i in range(0, len(documents), BATCH_SIZE):
            batch = documents[i:i + BATCH_SIZE]
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(documents) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} documents)")
            
            for doc in batch:
                try:
                    doc_id = doc["_id"]
                    job_posting_id = str(doc.get("job_posting_id", ""))
                    
                    if not job_posting_id:
                        logger.warning(f"Document {doc_id} has no job_posting_id")
                        stats["errors"] += 1
                        continue
                    
                    # Look up job_link
                    job_link = job_link_mapping.get(job_posting_id)
                    
                    if job_posting_id not in job_link_mapping:
                        logger.warning(f"No mapping found for job_posting_id: {job_posting_id}")
                        stats["skipped_no_mapping"] += 1
                        continue
                    
                    if job_link is None:
                        logger.warning(f"job_link is None for job_posting_id: {job_posting_id}")
                        stats["skipped_null_link"] += 1
                        # Still update with None to mark it as processed
                    
                    # Update document
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would update document {doc_id} with job_link: {job_link}")
                    else:
                        result = collection.update_one(
                            {"_id": doc_id},
                            {"$set": {"job_link": job_link, "job_link_updated_at": datetime.now()}}
                        )
                        
                        if result.modified_count > 0:
                            logger.info(f"Updated document {doc_id} with job_link: {job_link}")
                        else:
                            logger.warning(f"Failed to update document {doc_id}")
                            stats["errors"] += 1
                            continue
                    
                    stats["updated_documents"] += 1
                    
                except Exception as e:
                    logger.error(f"Error updating document {doc.get('_id', 'unknown')}: {e}")
                    stats["errors"] += 1
        
        return stats
    
    def run_update(self) -> Dict[str, Any]:
        """
        Run the complete update process for both collections.
        
        Returns:
            Dict[str, Any]: Complete statistics for the update operation
        """
        logger.info("Starting greenhouse job link update process...")
        start_time = datetime.now()
        
        # Build job_link mapping
        job_link_mapping = self.get_job_link_mapping()
        if not job_link_mapping:
            logger.error("No job_link mapping available. Aborting update.")
            return {"error": "No job_link mapping available"}
        
        # Update both collections
        results = {}
        
        # Update matches collection
        logger.info("Updating greenhouse_resume_job_matches collection...")
        results["matches"] = self.update_documents_with_job_link("greenhouse_resume_job_matches", job_link_mapping)
        
        # Update unmatched collection
        logger.info("Updating greenhouse_unmatched_job_postings collection...")
        results["unmatched"] = self.update_documents_with_job_link("greenhouse_unmatched_job_postings", job_link_mapping)
        
        # Calculate totals
        total_stats = {
            "total_documents": results["matches"]["total_documents"] + results["unmatched"]["total_documents"],
            "updated_documents": results["matches"]["updated_documents"] + results["unmatched"]["updated_documents"],
            "skipped_no_mapping": results["matches"]["skipped_no_mapping"] + results["unmatched"]["skipped_no_mapping"],
            "skipped_null_link": results["matches"]["skipped_null_link"] + results["unmatched"]["skipped_null_link"],
            "errors": results["matches"]["errors"] + results["unmatched"]["errors"]
        }
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Log summary
        logger.info("=== UPDATE SUMMARY ===")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Total documents processed: {total_stats['total_documents']}")
        logger.info(f"Successfully updated: {total_stats['updated_documents']}")
        logger.info(f"Skipped (no mapping): {total_stats['skipped_no_mapping']}")
        logger.info(f"Skipped (null link): {total_stats['skipped_null_link']}")
        logger.info(f"Errors: {total_stats['errors']}")
        logger.info("======================")
        
        results["totals"] = total_stats
        results["duration"] = str(duration)
        results["dry_run"] = self.dry_run
        
        return results

def main():
    """Main function to run the update script."""
    try:
        logger.info("=== Greenhouse Job Link Update Script ===")
        logger.info(f"DRY_RUN mode: {DRY_RUN}")
        
        if DRY_RUN:
            logger.info("Running in DRY RUN mode - no actual updates will be made")
            input("Press Enter to continue with dry run...")
        else:
            logger.warning("Running in LIVE UPDATE mode - documents will be modified!")
            response = input("Are you sure you want to proceed? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Operation cancelled by user")
                return
        
        # Run the update
        updater = GreenhouseJobLinkUpdater(dry_run=DRY_RUN)
        results = updater.run_update()
        
        if "error" in results:
            logger.error(f"Update failed: {results['error']}")
            return
        
        logger.info("Update process completed successfully!")
        
        # Save results to file
        import json
        results_file = f"update_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to: {results_file}")
        
    except Exception as e:
        logger.error(f"Script failed with error: {e}")
        raise

if __name__ == "__main__":
    main()
