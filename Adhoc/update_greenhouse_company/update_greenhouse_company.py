"""
Update greenhouse_resume_job_matches with company field from Job_postings_greenhouse

This script adds the company field to greenhouse_resume_job_matches by looking up 
the company from Job_postings_greenhouse using job_posting_id.

Usage:
    python update_greenhouse_company.py
"""

import os
import sys
from typing import Dict, Any
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

# Configuration
DRY_RUN = True  # Set to False to actually update
DB_NAME = "Resume_study"
BATCH_SIZE = 100

class GreenhouseCompanyUpdater:
    """Updates greenhouse_resume_job_matches with company field."""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[DB_NAME]
        self.greenhouse_jobs = self.db["Job_postings_greenhouse"]
        self.greenhouse_matches = self.db["greenhouse_resume_job_matches"]
        
        logger.info(f"GreenhouseCompanyUpdater initialized (DRY_RUN={dry_run})")
    
    def build_company_mapping(self) -> Dict[str, str]:
        """Build mapping of job_posting_id to company."""
        logger.info("Building job_posting_id to company mapping...")
        mapping = {}
        
        try:
            cursor = self.greenhouse_jobs.find(
                {"company": {"$exists": True, "$ne": None}},
                {"_id": 1, "company": 1}
            )
            
            count = 0
            for doc in cursor:
                job_id = str(doc["_id"])
                company = doc.get("company", "")
                if job_id and company:
                    mapping[job_id] = company
                    count += 1
            
            logger.info(f"Found {count} companies from Job_postings_greenhouse")
            return mapping
            
        except Exception as e:
            logger.error(f"Error building company mapping: {e}")
            return {}
    
    def update_matches(self, company_mapping: Dict[str, str]) -> Dict[str, int]:
        """Update greenhouse_resume_job_matches with company field."""
        stats = {
            "total_documents": 0,
            "updated_documents": 0,
            "skipped_no_mapping": 0,
            "skipped_already_has_company": 0,
            "errors": 0
        }
        
        logger.info("Starting company field update...")
        
        try:
            # Get all matches
            all_matches = list(self.greenhouse_matches.find({}))
            stats["total_documents"] = len(all_matches)
            logger.info(f"Found {len(all_matches)} documents in greenhouse_resume_job_matches")
            
            # Process in batches
            for i in range(0, len(all_matches), BATCH_SIZE):
                batch = all_matches[i:i + BATCH_SIZE]
                logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(all_matches) + BATCH_SIZE - 1)//BATCH_SIZE}")
                
                for doc in batch:
                    try:
                        doc_id = doc["_id"]
                        job_posting_id = str(doc.get("job_posting_id", ""))
                        
                        # Skip if already has company
                        if doc.get("company"):
                            stats["skipped_already_has_company"] += 1
                            continue
                        
                        # Look up company
                        company = company_mapping.get(job_posting_id)
                        
                        if not company:
                            logger.debug(f"No company found for job_posting_id: {job_posting_id}")
                            stats["skipped_no_mapping"] += 1
                            continue
                        
                        # Update document
                        if self.dry_run:
                            logger.info(f"[DRY RUN] Would update document {doc_id} with company: {company}")
                        else:
                            result = self.greenhouse_matches.update_one(
                                {"_id": doc_id},
                                {
                                    "$set": {
                                        "company": company,
                                        "company_updated_at": datetime.now()
                                    }
                                }
                            )
                            
                            if result.modified_count > 0:
                                logger.info(f"Updated document {doc_id} with company: {company}")
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
        logger.info("Starting greenhouse company update process...")
        start_time = datetime.now()
        
        # Build company mapping
        company_mapping = self.build_company_mapping()
        if not company_mapping:
            logger.error("No companies found. Aborting.")
            return {"error": "No companies found"}
        
        # Update matches
        stats = self.update_matches(company_mapping)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Log summary
        logger.info("=== UPDATE SUMMARY ===")
        logger.info(f"Mode: {'DRY RUN' if self.dry_run else 'LIVE UPDATE'}")
        logger.info(f"Duration: {duration}")
        logger.info(f"Total documents: {stats['total_documents']}")
        logger.info(f"Successfully updated: {stats['updated_documents']}")
        logger.info(f"Already has company: {stats['skipped_already_has_company']}")
        logger.info(f"Skipped (no mapping): {stats['skipped_no_mapping']}")
        logger.info(f"Errors: {stats['errors']}")
        logger.info(f"Available companies: {len(company_mapping)}")
        logger.info("======================")
        
        return {
            **stats,
            "duration": str(duration),
            "dry_run": self.dry_run,
            "available_companies": len(company_mapping)
        }

def main():
    """Main function."""
    try:
        logger.info("=== Greenhouse Company Update Script ===")
        logger.info(f"DRY_RUN mode: {DRY_RUN}")
        
        if not DRY_RUN:
            logger.warning("Running in LIVE UPDATE mode!")
            response = input("Proceed? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Cancelled")
                return
        else:
            logger.info("Running in DRY RUN mode - no actual updates")
        
        updater = GreenhouseCompanyUpdater(dry_run=DRY_RUN)
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

