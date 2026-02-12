
import os
import sys
import argparse

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir) # Repo root

# Add paths for imports
sys.path.append(parent_dir) # For libs, utils
sys.path.append(current_dir) # For configs, src

from utils import get_logger
from src.matching.job_spy_matcher import JobSpyResumeJobMatchingWorkflow
from configs.config import default_config, Config

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="JobSpy Resume-Job Matching Workflow")
    parser.add_argument("--limit", type=int, help="Limit number of jobs to process")
    parser.add_argument("--industry", nargs="+", help="Filter by industry prefix (e.g. ITC FIN)")
    parser.add_argument("--force", action="store_true", help="Force reprocess existing matches")
    parser.add_argument("--skip-processed", action="store_true", default=True, help="Skip already processed jobs (default)")
    
    args = parser.parse_args()
    
    # Configure
    config = default_config
    
    if args.industry:
        config.industry_prefixes = args.industry
        # Also update the query to match
        config.job_filters["industry"] = args.industry 
        
    if args.force:
        config.force_reprocess = True
        config.skip_processed_jobs = False
    
    if args.limit:
        config.max_jobs = args.limit

    logger.info(f"Starting JobSpy Matching with config: {config.get_summary()}")

    # Run
    workflow = JobSpyResumeJobMatchingWorkflow(config)
    results = workflow.run_workflow(max_jobs=args.limit)
    
    logger.info("Workflow Finished.")
    
    if results.get("status") == "success" or results.get("loading_status") == "success": # Check return format of standard workflow
         # Standard workflow returns a dict summary based on run_workflow implementation
         # run_workflow calls _calculate_workflow_summary
         pass

    # Basic logging of results (the workflow log already has details, but let's make it nice)
    jobs_processed = results.get('jobs_processed', 0)
    valid_matches = results.get('total_valid_matches', 0)
    rejected_matches = results.get('total_rejected_matches', 0)
    
    logger.info("=" * 60)
    logger.info("Workflow Summary")
    logger.info("=" * 60)
    logger.info(f"Jobs Processed: {jobs_processed}")
    logger.info(f"Valid Matches: {valid_matches}")
    logger.info(f"Rejected Matches: {rejected_matches}")
    logger.info(f"Success Rate: {(valid_matches/jobs_processed*100) if jobs_processed else 0:.1f}%")
    logger.info("=" * 60)
    
    logger.info(results)

if __name__ == "__main__":
    main()
