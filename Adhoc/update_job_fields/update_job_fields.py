"""
Adhoc Script: Add Missing Job Fields to Existing resume_job_matches

This script adds location and date_posted fields to existing documents in the 
resume_job_matches collection by looking up the complete job data from 
job_postings collection using job_posting_id.

Fields to add:
    - location: Job location from job_postings
    - date_posted: When the job was posted

Usage:
    python update_job_fields.py
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from bson import ObjectId

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

class JobFieldsUpdater:
    """Updates existing resume_job_matches documents with location and date_posted fields."""
    
    def __init__(self):
        """Initialize the updater."""
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client["Resume_study"]
        self.job_collection = self.db["job_postings"]
        self.matches_collection = self.db["resume_job_matches"]
        
        # Fields to add from job_postings
        self.fields_to_add = ["location", "date_posted"]
        
        logger.info(f"JobFieldsUpdater initialized")
        logger.info(f"Will add fields: {', '.join(self.fields_to_add)}")
    
    def get_job_fields_to_add(self, job_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the location and date_posted fields from a job document.
        
        Args:
            job_doc: Complete job document from job_postings collection
            
        Returns:
            Dictionary with location and date_posted fields
        """
        fields_to_add = {}
        
        for field in self.fields_to_add:
            if field in job_doc and job_doc[field] is not None:
                fields_to_add[field] = job_doc[field]
            else:
                # Set default values if fields don't exist
                if field == "location":
                    fields_to_add[field] = "Not specified"
                elif field == "date_posted":
                    fields_to_add[field] = None
        
        return fields_to_add
    
    def update_single_match(self, match_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a single resume_job_matches document with location and date_posted.
        
        Args:
            match_doc: Document from resume_job_matches collection
            
        Returns:
            Update result summary
        """
        try:
            job_id = match_doc.get("job_posting_id")
            if not job_id:
                return {
                    "status": "error", 
                    "message": "No job_posting_id found", 
                    "match_id": str(match_doc.get("_id"))
                }
            
            # Convert string ID to ObjectId if needed
            if isinstance(job_id, str):
                try:
                    job_id = ObjectId(job_id)
                except Exception as e:
                    return {
                        "status": "error", 
                        "message": f"Invalid job_posting_id format: {e}", 
                        "match_id": str(match_doc.get("_id"))
                    }
            
            # Fetch complete job document
            job_doc = self.job_collection.find_one({"_id": job_id})
            if not job_doc:
                return {
                    "status": "error", 
                    "message": f"Job {job_id} not found in job_postings", 
                    "match_id": str(match_doc.get("_id"))
                }
            
            # Get fields to add
            fields_to_add = self.get_job_fields_to_add(job_doc)
            
            if not fields_to_add:
                return {
                    "status": "no_fields", 
                    "message": "No fields to add", 
                    "match_id": str(match_doc.get("_id"))
                }
            
            # Add metadata about the update
            fields_to_add["_last_updated"] = datetime.now()
            fields_to_add["_update_source"] = "adhoc_location_date_update"
            
            # Update the document
            result = self.matches_collection.update_one(
                {"_id": match_doc["_id"]},
                {"$set": fields_to_add}
            )
            
            if result.modified_count > 0:
                return {
                    "status": "success",
                    "match_id": str(match_doc.get("_id")),
                    "job_id": str(job_id),
                    "fields_added": list(fields_to_add.keys()),
                    "fields_count": len(fields_to_add),
                    "location": fields_to_add.get("location"),
                    "date_posted": fields_to_add.get("date_posted")
                }
            else:
                return {
                    "status": "no_changes",
                    "match_id": str(match_doc.get("_id")),
                    "job_id": str(job_id),
                    "message": "Document updated but no fields were modified"
                }
                
        except Exception as e:
            logger.error(f"Error updating match {match_doc.get('_id')}: {e}")
            return {
                "status": "error", 
                "message": str(e), 
                "match_id": str(match_doc.get("_id"))
            }
    
    def update_all_matches(self, batch_size: int = 50) -> Dict[str, Any]:
        """
        Update all existing resume_job_matches documents with location and date_posted.
        
        Args:
            batch_size: Number of documents to process in each batch
            
        Returns:
            Summary of the update operation
        """
        try:
            logger.info("Starting bulk update of resume_job_matches documents")
            
            # Get total count
            total_matches = self.matches_collection.count_documents({})
            logger.info(f"Found {total_matches} documents to update")
            
            if total_matches == 0:
                return {"status": "no_documents", "message": "No documents found to update"}
            
            # Process in batches
            processed = 0
            successful = 0
            errors = 0
            no_fields = 0
            no_changes = 0
            
            # Process documents in batches using find with limit and skip
            for i in range(0, total_matches, batch_size):
                batch_docs = list(self.matches_collection.find({}).skip(i).limit(batch_size))
                batch_results = []
                
                for match_doc in batch_docs:
                    result = self.update_single_match(match_doc)
                    batch_results.append(result)
                    processed += 1
                    
                    # Log progress
                    if processed % 10 == 0:
                        logger.info(f"Processed {processed}/{total_matches} documents")
                
                # Count results
                for result in batch_results:
                    if result["status"] == "success":
                        successful += 1
                    elif result["status"] == "error":
                        errors += 1
                    elif result["status"] == "no_fields":
                        no_fields += 1
                    elif result["status"] == "no_changes":
                        no_changes += 1
                
                # Small delay between batches to avoid overwhelming the database
                time.sleep(0.1)
            
            summary = {
                "status": "completed",
                "total_documents": total_matches,
                "processed": processed,
                "successful_updates": successful,
                "errors": errors,
                "no_fields_added": no_fields,
                "no_changes": no_changes,
                "success_rate": (successful / total_matches * 100) if total_matches > 0 else 0
            }
            
            logger.info(f"Update completed: {summary}")
            return summary
            
        except Exception as e:
            logger.error(f"Error in bulk update: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_update_summary(self) -> Dict[str, Any]:
        """
        Get a summary of what fields will be added and their current status.
        
        Returns:
            Summary of fields and their availability
        """
        try:
            # Sample a few job documents to see what fields are available
            sample_jobs = list(self.job_collection.find({}).limit(20))
            
            field_availability = {}
            for field in self.fields_to_add:
                available_count = sum(1 for job in sample_jobs if field in job and job[field] is not None)
                field_availability[field] = {
                    "available": available_count > 0,
                    "sample_count": available_count,
                    "total_sample": len(sample_jobs),
                    "availability_percentage": (available_count / len(sample_jobs) * 100) if sample_jobs else 0
                }
            
            # Check current matches collection structure
            sample_match = self.matches_collection.find_one({})
            current_fields = list(sample_match.keys()) if sample_match else []
            
            # Check if our fields already exist
            fields_already_exist = {
                field: field in current_fields for field in self.fields_to_add
            }
            
            return {
                "fields_to_add": self.fields_to_add,
                "field_availability": field_availability,
                "fields_already_exist": fields_already_exist,
                "current_matches_fields": current_fields,
                "total_matches": self.matches_collection.count_documents({}),
                "total_jobs": self.job_collection.count_documents({})
            }
            
        except Exception as e:
            logger.error(f"Error getting update summary: {e}")
            return {"error": str(e)}
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            if self.mongo_client:
                self.mongo_client.close()
            logger.info("Updater cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

def main():
    """Main execution function."""
    try:
        updater = JobFieldsUpdater()
        
        # Show what will be updated
        logger.info("=== UPDATE SUMMARY ===")
        summary = updater.get_update_summary()
        
        print(f"\n=== JOB FIELDS UPDATE SUMMARY ===")
        print(f"Total matches to update: {summary.get('total_matches', 0)}")
        print(f"Fields to add: {', '.join(summary.get('fields_to_add', []))}")
        
        print(f"\nField Availability in job_postings:")
        for field, info in summary.get('field_availability', {}).items():
            status = "✓" if info['available'] else "✗"
            print(f"  {status} {field}: {info['sample_count']}/{info['total_sample']} available ({info['availability_percentage']:.1f}%)")
        
        print(f"\nCurrent Status in resume_job_matches:")
        for field, exists in summary.get('fields_already_exist', {}).items():
            status = "✓" if exists else "✗"
            print(f"  {status} {field}: {'Already exists' if exists else 'Missing'}")
        
        # Ask for confirmation
        response = input(f"\nProceed with updating {summary.get('total_matches', 0)} documents? (y/N): ")
        if response.lower() != 'y':
            print("Update cancelled.")
            return
        
        # Update matches collection
        logger.info("=== UPDATING RESUME_JOB_MATCHES COLLECTION ===")
        matches_result = updater.update_all_matches(batch_size=50)
        
        print(f"\n=== UPDATE RESULTS ===")
        print(f"Status: {matches_result.get('status', 'unknown')}")
        print(f"Total documents: {matches_result.get('total_documents', 0)}")
        print(f"Successfully updated: {matches_result.get('successful_updates', 0)}")
        print(f"Errors: {matches_result.get('errors', 0)}")
        print(f"No fields added: {matches_result.get('no_fields_added', 0)}")
        print(f"No changes: {matches_result.get('no_changes', 0)}")
        
        if matches_result.get('successful_updates', 0) > 0:
            success_rate = matches_result.get('success_rate', 0)
            print(f"Success rate: {success_rate:.1f}%")
            print(f"\n✓ Successfully added location and date_posted fields to {matches_result.get('successful_updates', 0)} documents!")
        else:
            print(f"\n⚠ No documents were updated. Check the logs for details.")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
        print(f"Error: {e}")
    finally:
        if 'updater' in locals():
            updater.cleanup()

if __name__ == "__main__":
    main()
