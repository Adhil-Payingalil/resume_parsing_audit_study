"""
Test Resume-to-Job Matching Workflow

This script tests the ResumeJobMatcher functionality with sample data.
"""

import os
import sys
import json
from datetime import datetime

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resume_job_matcher import ResumeJobMatcher
from utils import get_logger

logger = get_logger(__name__)

class ResumeJobMatchingTester:
    """
    Test class for the ResumeJobMatcher functionality.
    """
    
    def __init__(self):
        """Initialize the tester."""
        try:
            self.matcher = ResumeJobMatcher()
            logger.info("ResumeJobMatchingTester initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize tester: {e}")
            raise
    
    def test_initialization(self):
        """Test basic initialization and database connection."""
        logger.info("Testing initialization...")
        
        try:
            # Test database connection
            stats = self.matcher.get_matching_statistics()
            logger.info("Database connection successful")
            logger.info(f"Current statistics: {json.dumps(stats, indent=2, default=str)}")
            return True
        except Exception as e:
            logger.error(f"Initialization test failed: {e}")
            return False
    
    def test_get_pending_jobs(self):
        """Test getting pending jobs for matching."""
        logger.info("Testing get_pending_jobs...")
        
        try:
            pending_jobs = self.matcher.get_pending_jobs(limit=5)
            logger.info(f"Found {len(pending_jobs)} pending jobs")
            
            if pending_jobs:
                for i, job in enumerate(pending_jobs[:3]):  # Show first 3
                    logger.info(f"Job {i+1}: {job.get('job_title', 'Unknown')} at {job.get('company_name', 'Unknown')}")
            
            return len(pending_jobs) >= 0  # Success if we can query (even if no jobs)
        except Exception as e:
            logger.error(f"get_pending_jobs test failed: {e}")
            return False
    
    def test_vector_search(self):
        """Test vector search functionality."""
        logger.info("Testing vector search...")
        
        try:
            # Get a job with embedding
            job = self.matcher.job_collection.find_one({"jd_embedding": {"$exists": True, "$ne": None}})
            
            if not job:
                logger.warning("No job with embedding found for testing")
                return False
            
            # Test vector search
            top_resumes = self.matcher.vector_search_resumes(job, top_k=3)
            logger.info(f"Vector search found {len(top_resumes)} top resumes")
            
            if top_resumes:
                for i, resume in enumerate(top_resumes):
                    similarity = resume.get("similarity_score", 0.0)
                    file_id = resume.get("file_id", "Unknown")
                    logger.info(f"Resume {i+1}: {file_id} (similarity: {similarity:.3f})")
            
            return True
        except Exception as e:
            logger.error(f"Vector search test failed: {e}")
            return False
    
    def test_llm_validation(self):
        """Test LLM validation functionality."""
        logger.info("Testing LLM validation...")
        
        try:
            # Get a job with embedding
            job = self.matcher.job_collection.find_one({"jd_embedding": {"$exists": True, "$ne": None}})
            
            if not job:
                logger.warning("No job with embedding found for testing")
                return False
            
            # Get a resume with embedding
            resume = self.matcher.resume_collection.find_one({"text_embedding": {"$exists": True, "$ne": None}})
            
            if not resume:
                logger.warning("No resume with embedding found for testing")
                return False
            
            # Test LLM validation
            validation_result = self.matcher.llm_validate_match(job, resume)
            logger.info(f"LLM validation result: {json.dumps(validation_result, indent=2)}")
            
            # Check required fields
            required_fields = ["llm_score", "llm_reasoning", "is_valid", "similarity_score"]
            for field in required_fields:
                if field not in validation_result:
                    logger.error(f"Missing required field: {field}")
                    return False
            
            logger.info("LLM validation test passed")
            return True
        except Exception as e:
            logger.error(f"LLM validation test failed: {e}")
            return False
    
    def test_single_job_processing(self):
        """Test processing a single job through the complete workflow."""
        logger.info("Testing single job processing...")
        
        try:
            # Get a pending job
            pending_jobs = self.matcher.get_pending_jobs(limit=1)
            
            if not pending_jobs:
                logger.warning("No pending jobs found for testing")
                return False
            
            job = pending_jobs[0]
            logger.info(f"Processing job: {job.get('job_title')} at {job.get('company_name')}")
            
            # Process the job
            result = self.matcher.process_job_matching(job)
            logger.info(f"Processing result: {json.dumps(result, indent=2)}")
            
            # Check result structure
            if "status" not in result:
                logger.error("Missing status in result")
                return False
            
            logger.info("Single job processing test completed")
            return True
        except Exception as e:
            logger.error(f"Single job processing test failed: {e}")
            return False
    
    def test_batch_processing(self, batch_size: int = 3):
        """Test processing multiple jobs in batch."""
        logger.info(f"Testing batch processing with {batch_size} jobs...")
        
        try:
            # Get pending jobs
            pending_jobs = self.matcher.get_pending_jobs(limit=batch_size)
            
            if not pending_jobs:
                logger.warning("No pending jobs found for batch testing")
                return False
            
            logger.info(f"Processing {len(pending_jobs)} jobs in batch...")
            
            results = []
            for i, job in enumerate(pending_jobs):
                logger.info(f"Processing job {i+1}/{len(pending_jobs)}: {job.get('job_title')}")
                result = self.matcher.process_job_matching(job)
                results.append(result)
                
                # Add small delay to avoid rate limiting
                import time
                time.sleep(1)
            
            # Summarize results
            successful = sum(1 for r in results if r.get("status") == "success")
            total_matches = sum(r.get("matches_created", 0) for r in results)
            
            logger.info(f"Batch processing completed:")
            logger.info(f"  - Jobs processed: {len(results)}")
            logger.info(f"  - Successful: {successful}")
            logger.info(f"  - Total matches created: {total_matches}")
            
            return True
        except Exception as e:
            logger.error(f"Batch processing test failed: {e}")
            return False
    
    def run_comprehensive_test(self):
        """Run all tests in sequence."""
        logger.info("Starting comprehensive test of ResumeJobMatcher...")
        
        tests = [
            ("Initialization", self.test_initialization),
            ("Get Pending Jobs", self.test_get_pending_jobs),
            ("Vector Search", self.test_vector_search),
            ("LLM Validation", self.test_llm_validation),
            ("Single Job Processing", self.test_single_job_processing),
        ]
        
        results = {}
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"Running test: {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                result = test_func()
                results[test_name] = result
                status = "PASSED" if result else "FAILED"
                logger.info(f"Test {test_name}: {status}")
            except Exception as e:
                results[test_name] = False
                logger.error(f"Test {test_name} failed with exception: {e}")
        
        # Summary
        logger.info(f"\n{'='*50}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*50}")
        
        passed = sum(1 for result in results.values() if result)
        total = len(results)
        
        for test_name, result in results.items():
            status = "PASSED" if result else "FAILED"
            logger.info(f"{test_name}: {status}")
        
        logger.info(f"\nOverall: {passed}/{total} tests passed")
        
        return passed == total

def main():
    """Main function to run the tests."""
    try:
        tester = ResumeJobMatchingTester()
        success = tester.run_comprehensive_test()
        
        if success:
            logger.info("All tests passed! ResumeJobMatcher is working correctly.")
        else:
            logger.warning("Some tests failed. Please check the logs for details.")
        
        return success
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1) 