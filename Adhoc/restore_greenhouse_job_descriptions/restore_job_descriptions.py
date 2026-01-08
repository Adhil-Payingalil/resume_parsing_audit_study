"""
# Greenhouse Job Description Restoration Script

This script restores job_description field to Job_postings_greenhouse collection by looking up
descriptions from greenhouse_resume_job_matches and greenhouse_unmatched_job_postings collections.

## Problem:
The job_description field was accidentally deleted from Job_postings_greenhouse collection.

## Solution:
1. Look up job descriptions from greenhouse match collections using job_posting_id
2. Update Job_postings_greenhouse documents with the found descriptions
3. Leave blank if no description is found (likely jd_extraction=false documents)

## Usage:
python restore_job_descriptions.py

## Safety:
- Dry run mode by default - set DRY_RUN = False to actually update
- Logs all operations and shows statistics
- Only updates documents that are missing job_description field
"""

import os
import sys
from typing import Dict, Any, List, Optional, Set
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

class JobDescriptionRestorer:
    """Restores job_description field to Job_postings_greenhouse collection."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[DB_NAME]
        self.greenhouse_jobs_collection = self.db["Job_postings_greenhouse"]
        self.matches_collection = self.db["greenhouse_resume_job_matches"]
        self.unmatched_collection = self.db["greenhouse_unmatched_job_postings"]
        
        logger.info(f"JobDescriptionRestorer initialized (DRY_RUN={dry_run})")
    
    def get_job_description_mapping(self) -> Dict[str, str]:
        """
        Build a mapping of job_posting_id to job_description from both match collections.
        
        Returns:
            Dict[str, str]: Mapping of job_posting_id to job_description
        """
        logger.info("Building job_posting_id to job_description mapping...")
        mapping = {}
        
        try:
            # Get descriptions from matches collection
            logger.info("Fetching job descriptions from greenhouse_resume_job_matches...")
            matches_cursor = self.matches_collection.find(
                {"job_description": {"$exists": True, "$ne": "", "$ne": None}},
                {"job_posting_id": 1, "job_description": 1}
            )
            
            matches_count = 0
            for match in matches_cursor:
                job_id = str(match.get("job_posting_id", ""))
                job_description = match.get("job_description", "")
                if job_id and job_description:
                    mapping[job_id] = job_description
                    matches_count += 1
            
            logger.info(f"Found {matches_count} job descriptions from matches collection")
            
            # Get descriptions from unmatched collection (only if not already in mapping)
            logger.info("Fetching job descriptions from greenhouse_unmatched_job_postings...")
            unmatched_cursor = self.unmatched_collection.find(
                {"job_description": {"$exists": True, "$ne": "", "$ne": None}},
                {"job_posting_id": 1, "job_description": 1}
            )
            
            unmatched_count = 0
            for unmatched in unmatched_cursor:
                job_id = str(unmatched.get("job_posting_id", ""))
                job_description = unmatched.get("job_description", "")
                if job_id and job_description and job_id not in mapping:
                    mapping[job_id] = job_description
                    unmatched_count += 1
            
            logger.info(f"Found {unmatched_count} additional job descriptions from unmatched collection")
            logger.info(f"Total unique job descriptions found: {len(mapping)}")
            
            return mapping
            
        except Exception as e:
            logger.error(f"Error building job_description mapping: {e}")
            return {}
    
    def find_jobs_without_description(self) -> List[Dict[str, Any]]:
        """
        Find all Job_postings_greenhouse documents that don't have job_description field.
        
        Returns:
            List[Dict[str, Any]]: Documents without job_description field
        """
        try:
            # Find documents without job_description field or with empty/null values
            query = {
                "$or": [
                    {"job_description": {"$exists": False}},
                    {"job_description": None},
                    {"job_description": ""},
                    {"job_description": {"$eq": ""}}
                ]
            }
            
            documents = list(self.greenhouse_jobs_collection.find(query, {"_id": 1}))
            logger.info(f"Found {len(documents)} Job_postings_greenhouse documents without job_description")
            return documents
            
        except Exception as e:
            logger.error(f"Error finding documents without job_description: {e}")
            return []
    
    def restore_job_descriptions(self, description_mapping: Dict[str, str]) -> Dict[str, int]:
        """
        Restore job_description field to Job_postings_greenhouse documents.
        
        Args:
            description_mapping: Mapping of job_posting_id to job_description
            
        Returns:
            Dict[str, int]: Statistics about the restoration operation
        """
        stats = {
            "total_documents": 0,
            "updated_documents": 0,
            "skipped_no_mapping": 0,
            "skipped_already_has_description": 0,
            "errors": 0
        }
        
        logger.info("Starting job description restoration...")
        
        # Find documents without job_description
        documents = self.find_jobs_without_description()
        stats["total_documents"] = len(documents)
        
        if not documents:
            logger.info("No documents need job_description restoration")
            return stats
        
        # Process in batches
        for i in range(0, len(documents), BATCH_SIZE):
            batch = documents[i:i + BATCH_SIZE]
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(documents) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} documents)")
            
            for doc in batch:
                try:
                    doc_id = doc["_id"]
                    job_posting_id = str(doc_id)  # The _id IS the job_posting_id
                    
                    # Look up job_description
                    job_description = description_mapping.get(job_posting_id)
                    
                    if job_description is None:
                        logger.debug(f"No job description found for job_posting_id: {job_posting_id}")
                        stats["skipped_no_mapping"] += 1
                        continue
                    
                    # Update document
                    if self.dry_run:
                        logger.info(f"[DRY RUN] Would update document {doc_id} with job_description (length: {len(job_description)} chars)")
                    else:
                        result = self.greenhouse_jobs_collection.update_one(
                            {"_id": doc_id},
                            {
                                "$set": {
                                    "job_description": job_description,
                                    "job_description_restored_at": datetime.now()
                                }
                            }
                        )
                        
                        if result.modified_count > 0:
                            logger.info(f"Restored job_description for document {doc_id} (length: {len(job_description)} chars)")
                        else:
                            logger.warning(f"Failed to update document {doc_id}")
                            stats["errors"] += 1
                            continue
                    
                    stats["updated_documents"] += 1
                    
                except Exception as e:
                    logger.error(f"Error processing document {doc.get('_id', 'unknown')}: {e}")
                    stats["errors"] += 1
        
        return stats
    
    def run_restoration(self) -> Dict[str, Any]:
        """
        Run the complete job description restoration process.
        
        Returns:
            Dict[str, Any]: Complete statistics for the restoration operation
        """
        logger.info("Starting greenhouse job description restoration process...")
        start_time = datetime.now()
        
        # Build job_description mapping
        description_mapping = self.get_job_description_mapping()
        if not description_mapping:
            logger.error("No job descriptions found in match collections. Aborting restoration.")
            return {"error": "No job descriptions found in match collections"}
        
        # Restore job descriptions
        stats = self.restore_job_descriptions(description_mapping)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Log summary
        logger.info("=== RESTORATION SUMMARY ===")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Total documents processed: {stats['total_documents']}")
        logger.info(f"Successfully updated: {stats['updated_documents']}")
        logger.info(f"Skipped (no mapping): {stats['skipped_no_mapping']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Available descriptions in mapping: {len(description_mapping)}")
        logger.info("============================")
        
        results = {
            **stats,
            "duration": str(duration),
            "dry_run": self.dry_run,
            "available_descriptions": len(description_mapping)
        }
        
        return results

def main():
    """Main function to run the restoration script."""
    try:
        logger.info("=== Greenhouse Job Description Restoration Script ===")
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
        
        # Run the restoration
        restorer = JobDescriptionRestorer(dry_run=DRY_RUN)
        results = restorer.run_restoration()
        
        if "error" in results:
            logger.error(f"Restoration failed: {results['error']}")
            return
        
        logger.info("Restoration process completed successfully!")
        
        # Save results to file
        import json
        results_file = f"restoration_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to: {results_file}")
        
    except Exception as e:
        logger.error(f"Script failed with error: {e}")
        raise

if __name__ == "__main__":
    main()
