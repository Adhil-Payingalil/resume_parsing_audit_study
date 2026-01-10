
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
from src.matching.greenhouse_matcher import GreenhouseResumeJobMatchingWorkflow
from configs.greenhouse_config import default_greenhouse_config, GreenhouseConfig

logger = get_logger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Greenhouse Resume-Job Matching Workflow")
    parser.add_argument("--limit", type=int, help="Limit number of jobs to process")
    parser.add_argument("--industry", nargs="+", help="Filter by industry prefix (e.g. ITC FIN)")
    parser.add_argument("--cycle", type=float, help="Cycle number to filter jobs (default: None/All)")
    parser.add_argument("--force", action="store_true", help="Force reprocess existing matches")
    parser.add_argument("--skip-processed", action="store_true", default=True, help="Skip already processed jobs (default)")
    
    args = parser.parse_args()
    
    # Configure
    config = default_greenhouse_config
    
    # Update cycle (Argument takes precedence, otherwise prompt)
    if args.cycle is not None:
        config.cycle = args.cycle
    else:
        # Interactive prompt
        try:
            print("Enter cycle number to filter jobs (e.g. 8.1)")
            user_input = input("Press Enter for NO FILTER (all cycles): ").strip()
            if user_input:
                config.cycle = float(user_input)
            else:
                config.cycle = None
                print("Using NO CYCLE FILTER (processing all cycles)")
        except ValueError:
            logger.error("Invalid cycle number entered. Using NO FILTER.")
            config.cycle = None

    if args.industry:
        config.industry_prefixes = args.industry
        # Also update the query to match
        config.job_filters["industry"] = args.industry 
        
    if args.force:
        config.force_reprocess = True
        config.skip_processed_jobs = False
    
    if args.limit:
        config.max_jobs = args.limit

    logger.info(f"Starting Greenhouse Matching with config: {config.get_summary()}")

    # Run
    workflow = GreenhouseResumeJobMatchingWorkflow(config)
    
    # Show processing statistics BEFORE running (replicating legacy behavior)
    try:
        if hasattr(workflow, 'get_processing_statistics'):
            stats = workflow.get_processing_statistics()
            logger.info("=" * 60)
            logger.info("PRE-PROCESSING STATISTICS:")
            logger.info("=" * 60)
            logger.info(f"Total jobs in collection: {stats.get('total_jobs', 0)}")
            logger.info(f"Jobs matching filter: {stats.get('jobs_matching_filter', 0)}")
            logger.info(f"Jobs with embeddings (all cycles): {stats.get('jobs_with_embeddings_all_cycles', 0)}")
            logger.info(f"Already processed (matched): {stats.get('processed_jobs', {}).get('matched', 0)}")
            logger.info(f"Already processed (unmatched): {stats.get('processed_jobs', {}).get('unmatched', 0)}")
            logger.info(f"Total already processed: {stats.get('processed_jobs', {}).get('total', 0)}")
            logger.info(f"Remaining jobs to process: {stats.get('remaining_jobs', 0)}")
            logger.info(f"Filter applied: {stats.get('filter_applied', {})}")
            logger.info(f"Skip processed jobs: {config.skip_processed_jobs}")
            logger.info(f"Force reprocess: {config.force_reprocess}")
            logger.info("=" * 60)
    except Exception as e:
        logger.warning(f"Could not fetch pre-processing stats: {e}")
    
    # Run workflow
    results = workflow.run_workflow(max_jobs=args.limit)
    
    # Extract statistics
    jobs_processed = results.get('jobs_processed', 0)
    resumes_passed_validation = results.get('total_valid_matches', 0)
    resumes_rejected = results.get('total_rejected_matches', 0)
    total_validations = resumes_passed_validation + resumes_rejected
    
    jobs_matched = results.get('total_valid_matches', 0) # This might needs better logic if 1:1 match
    # Legacy logic: jobs_matched = sum(1 for r in job_results if r.get('status') == 'success' and r.get('valid_matches', 0) > 0)
    # But run_workflow returns a summary dict. 
    
    logger.info("=" * 60)
    logger.info("Workflow Completed!")
    logger.info("=" * 60)
    logger.info(f"[JOBS] Total jobs processed: {jobs_processed}")
    logger.info(f"[MATCHED] Valid matches: {resumes_passed_validation}")
    logger.info(f"[REJECTED] Rejected matches: {resumes_rejected}")
    logger.info(f"[SUCCESS] Job match rate: {(resumes_passed_validation/jobs_processed*100) if jobs_processed else 0:.1f}%")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
