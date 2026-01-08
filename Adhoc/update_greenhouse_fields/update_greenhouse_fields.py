"""
Update greenhouse_resume_job_matches with fields from Job_postings_greenhouse

This script dynamically updates fields in greenhouse_resume_job_matches by looking up 
values from Job_postings_greenhouse using job_posting_id.

Configuration:
    - FIELDS_TO_UPDATE: List of field names to lookup and update
    - BASE_QUERY_FILTER: MongoDB query filter to select documents to update
    - DRY_RUN: Set to False to actually update the database

Usage:
    python update_greenhouse_fields.py
"""

import os
import sys
from typing import Dict, Any, List
from datetime import datetime

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from libs.mongodb import _get_mongo_client
import logging

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
DRY_RUN = False

# Database configuration
DB_NAME = "Resume_study"
BATCH_SIZE = 100

# Fields to lookup from Job_postings_greenhouse and update in greenhouse_resume_job_matches
# Add or remove fields as needed
FIELDS_TO_UPDATE = [
    "unsupported_input_fields",
    "unsupported_input_field_labels",
    "link_status"
]

# Base query filter for greenhouse_resume_job_matches
# Only documents matching this filter will be processed
# Set to {} to process all documents
BASE_QUERY_FILTER = {
    "cycle": 3
}

# ============================================================================
# END CONFIGURATION
# ============================================================================

class GreenhouseFieldsUpdater:
    """Dynamically updates greenhouse_resume_job_matches with fields from Job_postings_greenhouse."""
    
    def __init__(self, dry_run: bool = True, fields_to_update: List[str] = None, 
                 base_query_filter: Dict[str, Any] = None):
        """
        Initialize the updater.
        
        Args:
            dry_run: If True, only log what would be updated without making changes
            fields_to_update: List of field names to update
            base_query_filter: MongoDB query filter for selecting documents to update
        """
        self.dry_run = dry_run
        self.fields_to_update = fields_to_update or FIELDS_TO_UPDATE
        self.base_query_filter = base_query_filter or BASE_QUERY_FILTER
        
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[DB_NAME]
        self.greenhouse_jobs = self.db["Job_postings_greenhouse"]
        self.greenhouse_matches = self.db["greenhouse_resume_job_matches"]
        
        logger.info(f"GreenhouseFieldsUpdater initialized (DRY_RUN={dry_run})")
        logger.info(f"Fields to update: {self.fields_to_update}")
        logger.info(f"Base query filter: {self.base_query_filter}")
    
    def build_field_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Build mappings of job_posting_id to field values for all configured fields.
        
        Returns:
            Dictionary mapping field_name -> {job_posting_id -> field_value}
        """
        logger.info(f"Building job_posting_id to field mappings for: {self.fields_to_update}")
        mappings = {field: {} for field in self.fields_to_update}
        
        try:
            # Build projection to only fetch needed fields
            projection = {"_id": 1}
            for field in self.fields_to_update:
                projection[field] = 1
            
            # Build query to find documents with at least one of the fields
            field_exists_query = {
                "$or": [
                    {field: {"$exists": True, "$ne": None}}
                    for field in self.fields_to_update
                ]
            }
            
            cursor = self.greenhouse_jobs.find(field_exists_query, projection)
            
            count = 0
            for doc in cursor:
                job_id = str(doc["_id"])
                if not job_id:
                    continue
                
                for field in self.fields_to_update:
                    field_value = doc.get(field)
                    # Include field even if None/empty, but skip if field doesn't exist
                    if field in doc:
                        mappings[field][job_id] = field_value
                
                count += 1
            
            # Log statistics for each field
            for field in self.fields_to_update:
                non_null_count = sum(1 for v in mappings[field].values() if v is not None)
                logger.info(f"Found {len(mappings[field])} mappings for '{field}' "
                          f"({non_null_count} non-null values)")
            
            logger.info(f"Processed {count} documents from Job_postings_greenhouse")
            return mappings
            
        except Exception as e:
            logger.error(f"Error building field mappings: {e}")
            return {field: {} for field in self.fields_to_update}
    
    def update_matches(self, field_mappings: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update greenhouse_resume_job_matches with field values.
        
        Args:
            field_mappings: Dictionary mapping field_name -> {job_posting_id -> field_value}
        
        Returns:
            Statistics dictionary
        """
        stats = {
            "total_documents": 0,
            "updated_documents": 0,
            "skipped_no_mapping": 0,
            "skipped_no_job_posting_id": 0,
            "field_stats": {field: {"updated": 0, "skipped_no_mapping": 0, "skipped_already_exists": 0}
                          for field in self.fields_to_update},
            "errors": 0
        }
        
        logger.info("Starting field updates...")
        
        try:
            # Get all matches matching the base query filter
            all_matches = list(self.greenhouse_matches.find(self.base_query_filter))
            stats["total_documents"] = len(all_matches)
            logger.info(f"Found {len(all_matches)} documents matching query filter: {self.base_query_filter}")
            
            if not all_matches:
                logger.warning("No documents found matching the query filter!")
                return stats
            
            # Process in batches
            total_batches = (len(all_matches) + BATCH_SIZE - 1) // BATCH_SIZE
            for i in range(0, len(all_matches), BATCH_SIZE):
                batch = all_matches[i:i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                logger.info(f"Processing batch {batch_num}/{total_batches}")
                
                for doc in batch:
                    try:
                        doc_id = doc["_id"]
                        job_posting_id = str(doc.get("job_posting_id", ""))
                        
                        if not job_posting_id:
                            stats["skipped_no_job_posting_id"] += 1
                            logger.debug(f"Document {doc_id} has no job_posting_id, skipping")
                            continue
                        
                        # Build update document
                        update_fields = {}
                        fields_to_update_count = 0
                        fields_skipped_no_mapping = 0
                        fields_skipped_already_exists = 0
                        
                        for field in self.fields_to_update:
                            # Check if field already exists and has a value
                            if doc.get(field) is not None:
                                stats["field_stats"][field]["skipped_already_exists"] += 1
                                fields_skipped_already_exists += 1
                                continue
                            
                            # Look up field value
                            field_mapping = field_mappings.get(field, {})
                            field_value = field_mapping.get(job_posting_id)
                            
                            # Check if mapping exists (even if value is None)
                            if job_posting_id not in field_mapping:
                                stats["field_stats"][field]["skipped_no_mapping"] += 1
                                fields_skipped_no_mapping += 1
                                continue
                            
                            # Add to update (include None values to explicitly set them)
                            update_fields[field] = field_value
                            fields_to_update_count += 1
                        
                        # Skip if no fields to update
                        if not update_fields:
                            if fields_skipped_no_mapping > 0:
                                stats["skipped_no_mapping"] += 1
                            continue
                        
                        # Add timestamp
                        update_fields["fields_updated_at"] = datetime.now()
                        
                        # Update document
                        if self.dry_run:
                            logger.debug(f"[DRY RUN] Would update document {doc_id} with fields: {list(update_fields.keys())}")
                        else:
                            result = self.greenhouse_matches.update_one(
                                {"_id": doc_id},
                                {"$set": update_fields}
                            )
                            
                            if result.modified_count > 0:
                                logger.debug(f"Updated document {doc_id} with {len(update_fields)} fields")
                                # Update field-specific stats
                                for field in update_fields:
                                    if field != "fields_updated_at":
                                        stats["field_stats"][field]["updated"] += 1
                            else:
                                logger.warning(f"Failed to update document {doc_id}")
                                stats["errors"] += 1
                                continue
                        
                        stats["updated_documents"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing document {doc.get('_id')}: {e}")
                        stats["errors"] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error in update_matches: {e}")
            return stats
    
    def run(self) -> Dict[str, Any]:
        """Run the complete update process."""
        logger.info("Starting greenhouse fields update process...")
        start_time = datetime.now()
        
        # Build field mappings
        field_mappings = self.build_field_mappings()
        
        # Check if we have any mappings
        total_mappings = sum(len(mapping) for mapping in field_mappings.values())
        if total_mappings == 0:
            logger.error("No field mappings found. Aborting.")
            return {"error": "No field mappings found"}
        
        # Update matches
        stats = self.update_matches(field_mappings)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Log summary
        logger.info("=== UPDATE SUMMARY ===")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Query filter: {self.base_query_filter}")
        logger.info(f"Total documents processed: {stats['total_documents']}")
        logger.info(f"Successfully updated: {stats['updated_documents']}")
        logger.info(f"Skipped (no job_posting_id): {stats['skipped_no_job_posting_id']}")
        logger.info(f"Skipped (no mapping): {stats['skipped_no_mapping']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info("")
        logger.info("Field-level statistics:")
        for field in self.fields_to_update:
            field_stat = stats["field_stats"][field]
            logger.info(f"  {field}:")
            logger.info(f"    - Updated: {field_stat['updated']}")
            logger.info(f"    - Skipped (no mapping): {field_stat['skipped_no_mapping']}")
            logger.info(f"    - Skipped (already exists): {field_stat['skipped_already_exists']}")
        logger.info("======================")
        
        return {
            **stats,
            "duration": str(duration),
            "dry_run": self.dry_run,
            "fields_to_update": self.fields_to_update,
            "base_query_filter": self.base_query_filter,
            "field_mappings_count": {field: len(mapping) 
                                    for field, mapping in field_mappings.items()}
        }

def main():
    """Main function."""
    try:
        logger.info("=== Greenhouse Fields Update Script ===")
        logger.info(f"DRY_RUN mode: {DRY_RUN}")
        logger.info(f"Fields to update: {FIELDS_TO_UPDATE}")
        logger.info(f"Base query filter: {BASE_QUERY_FILTER}")
        
        if not DRY_RUN:
            logger.warning("Running in LIVE UPDATE mode!")
            response = input("Proceed? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Cancelled")
                return
        else:
            logger.info("Running in DRY RUN mode - no actual updates")
        
        updater = GreenhouseFieldsUpdater(
            dry_run=DRY_RUN,
            fields_to_update=FIELDS_TO_UPDATE,
            base_query_filter=BASE_QUERY_FILTER
        )
        results = updater.run()
        
        if "error" in results:
            logger.error(f"Update failed: {results['error']}")
            return
        
        logger.info("Update completed!")
        
        # Save results
        import json
        results_file = f"update_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results saved to: {results_file}")
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        raise

if __name__ == "__main__":
    main()

