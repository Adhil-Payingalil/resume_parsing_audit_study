"""
Test Script for Greenhouse Resume-Job Matching Workflow

This script demonstrates how to use the Greenhouse workflow to match resumes
with job postings from the Job_postings_greenhouse collection.

Usage:
    python test_greenhouse_workflow.py
"""

import os
import sys
import json
from datetime import datetime

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from greenhouse_resume_job_matching_workflow import GreenhouseResumeJobMatchingWorkflow
from greenhouse_config import GreenhouseConfig, default_greenhouse_config
from utils import get_logger

logger = get_logger(__name__)

def test_greenhouse_workflow():
    """Test the Greenhouse workflow with a small sample of jobs."""
    
    try:
        # Create a custom configuration for testing
        test_config = GreenhouseConfig(
            industry_prefixes=["ITC"],  # Focus on ITC industry
            max_jobs=5,  # Limit to 5 jobs for testing
            batch_size=2,  # Small batch size for testing
            max_workers=2,  # Limited workers for testing
            similarity_threshold=0.25,  # Lower threshold for testing
            validation_threshold=60  # Lower validation threshold for testing
        )
        
        logger.info("Starting Greenhouse workflow test")
        logger.info(f"Configuration: {test_config.get_summary()}")
        
        # Initialize workflow
        with GreenhouseResumeJobMatchingWorkflow(config=test_config) as workflow:
            
            # Check processing statistics before running
            stats = workflow.get_processing_statistics()
            logger.info(f"Processing statistics: {json.dumps(stats, indent=2, default=str)}")
            
            # Run the workflow
            logger.info("Running Greenhouse workflow...")
            results = workflow.run_workflow()
            
            # Display results
            logger.info("Workflow completed!")
            logger.info(f"Results: {json.dumps(results, indent=2, default=str)}")
            
            # Check processing statistics after running
            stats_after = workflow.get_processing_statistics()
            logger.info(f"Processing statistics after: {json.dumps(stats_after, indent=2, default=str)}")
            
            return results
            
    except Exception as e:
        logger.error(f"Error in Greenhouse workflow test: {e}")
        return {"status": "error", "error": str(e)}

def test_single_job_processing():
    """Test processing a single Greenhouse job."""
    
    try:
        # Use default configuration
        config = default_greenhouse_config
        
        logger.info("Testing single job processing")
        
        with GreenhouseResumeJobMatchingWorkflow(config=config) as workflow:
            
            # Get a single job for testing
            jobs = workflow.get_filtered_jobs(limit=1)
            
            if not jobs:
                logger.info("No Greenhouse jobs found for testing")
                return {"status": "no_jobs"}
            
            job = jobs[0]
            logger.info(f"Testing with job: {job.get('title')} at {job.get('company')}")
            
            # Process the single job
            result = workflow.process_job(job)
            
            logger.info(f"Single job processing result: {json.dumps(result, indent=2, default=str)}")
            
            return result
            
    except Exception as e:
        logger.error(f"Error in single job processing test: {e}")
        return {"status": "error", "error": str(e)}

def main():
    """Main test function."""
    
    print("=" * 60)
    print("Greenhouse Resume-Job Matching Workflow Test")
    print("=" * 60)
    
    # Test 1: Single job processing
    print("\n1. Testing single job processing...")
    single_result = test_single_job_processing()
    
    # Test 2: Full workflow (small batch)
    print("\n2. Testing full workflow with small batch...")
    workflow_result = test_greenhouse_workflow()
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"Single job test: {single_result.get('status', 'unknown')}")
    print(f"Workflow test: {workflow_result.get('status', 'unknown')}")
    
    if workflow_result.get('status') == 'completed':
        print(f"Jobs processed: {workflow_result.get('jobs_processed', 0)}")
        print(f"Valid matches: {workflow_result.get('total_valid_matches', 0)}")
        print(f"Rejected matches: {workflow_result.get('total_rejected_matches', 0)}")
        print(f"Success rate: {workflow_result.get('success_rate', 0):.1f}%")

if __name__ == "__main__":
    main()
