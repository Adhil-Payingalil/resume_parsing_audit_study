#!/usr/bin/env python3
"""
Simple script to run the Greenhouse workflow
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from greenhouse_resume_job_matching_workflow import GreenhouseResumeJobMatchingWorkflow
from greenhouse_config import GreenhouseConfig
from utils import get_logger

logger = get_logger(__name__)

def run_workflow():
    """Run the Greenhouse workflow with default settings."""
    
    try:
        # Create configuration
        config = GreenhouseConfig( 
            max_jobs=None,  # Process ALL jobs
            similarity_threshold=0.30,  # Lower threshold for more matches
            validation_threshold=60,  # Lower validation threshold
            batch_size=20,  # Process in batches of 20
            max_workers=4  # Use 4 parallel workers
        )
        
        logger.info("Starting Greenhouse workflow...")
        logger.info(f"Configuration: {config.get_summary()}")
        
        # Run workflow
        with GreenhouseResumeJobMatchingWorkflow(config=config) as workflow:
            
            # Show processing statistics
            stats = workflow.get_processing_statistics()
            logger.info(f"Processing statistics: {stats}")
            
            # Run the workflow
            results = workflow.run_workflow()
            
            # Display results
            logger.info("Workflow completed!")
            logger.info(f"Jobs processed: {results.get('jobs_processed', 0)}")
            logger.info(f"Valid matches: {results.get('total_valid_matches', 0)}")
            logger.info(f"Rejected matches: {results.get('total_rejected_matches', 0)}")
            logger.info(f"Success rate: {results.get('success_rate', 0):.1f}%")
            
            return results
            
    except Exception as e:
        logger.error(f"Error running workflow: {e}")
        return None

if __name__ == "__main__":
    print("=" * 60)
    print("Greenhouse Resume-Job Matching Workflow")
    print("=" * 60)
    
    results = run_workflow()
    
    if results:
        print("\n✅ Workflow completed successfully!")
    else:
        print("\n❌ Workflow failed!")
