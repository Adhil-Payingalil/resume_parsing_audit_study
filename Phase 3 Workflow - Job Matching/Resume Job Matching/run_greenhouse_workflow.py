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

def run_workflow(force_reprocess=False, skip_processed_jobs=True):
    """
    Run the Greenhouse workflow with default settings.
    
    Args:
        force_reprocess: If True, reprocess all jobs including previously processed ones
        skip_processed_jobs: If True, skip jobs already in matches/unmatched collections
    """
    
    try:
        # Create configuration
        config = GreenhouseConfig( 
            max_jobs=None,  # Process ALL jobs
            similarity_threshold=0.30,  # Lower threshold for more matches
            validation_threshold=60,  # Lower validation threshold
            batch_size=20,  # Process in batches of 20
            max_workers=4,  # Use 4 parallel workers
            skip_processed_jobs=skip_processed_jobs,  # Control duplicate processing
            force_reprocess=force_reprocess  # Force reprocessing if needed
        )
        
        logger.info("Starting Greenhouse workflow...")
        logger.info(f"Configuration: {config.get_summary()}")
        
        # Run workflow
        with GreenhouseResumeJobMatchingWorkflow(config=config) as workflow:
            
            # Show processing statistics BEFORE running
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
            
            # Run the workflow
            results = workflow.run_workflow()
            
            # Extract statistics
            jobs_processed = results.get('jobs_processed', 0)
            resumes_passed_validation = results.get('total_valid_matches', 0)  # Total resumes that passed LLM validation
            resumes_rejected = results.get('total_rejected_matches', 0)
            total_validations = resumes_passed_validation + resumes_rejected
            
            # Calculate actual stored matches (one per job that found a valid resume)
            # Count jobs where at least one resume passed validation
            job_results = results.get('job_results', [])
            jobs_matched = sum(1 for r in job_results if r.get('status') == 'success' and r.get('valid_matches', 0) > 0)
            jobs_unmatched = results.get('total_no_resumes_found', 0)
            jobs_with_errors = results.get('total_errors', 0)
            
            # Calculate metrics
            validation_acceptance_rate = (resumes_passed_validation / total_validations * 100) if total_validations > 0 else 0
            job_match_rate = (jobs_matched / jobs_processed * 100) if jobs_processed > 0 else 0
            avg_candidates_per_job = resumes_passed_validation / jobs_matched if jobs_matched > 0 else 0
            
            # Display results
            logger.info("=" * 60)
            logger.info("Workflow Completed!")
            logger.info("=" * 60)
            logger.info(f"[JOBS] Total jobs processed: {jobs_processed}")
            logger.info(f"[MATCHED] Jobs matched (1 resume each): {jobs_matched}")
            logger.info(f"[UNMATCHED] Jobs with no valid matches: {jobs_unmatched}")
            logger.info(f"[ERRORS] Jobs with processing errors: {jobs_with_errors}")
            logger.info(f"[CANDIDATES] Total resumes passed validation: {resumes_passed_validation}")
            logger.info(f"[REJECTED] Total resumes rejected: {resumes_rejected}")
            logger.info(f"[SUCCESS] Job match rate: {job_match_rate:.1f}%")
            logger.info(f"[RATE] Validation acceptance rate: {validation_acceptance_rate:.1f}%")
            logger.info(f"[AVG] Avg valid candidates per matched job: {avg_candidates_per_job:.2f}")
            logger.info(f"[TOTAL] Total validations performed: {total_validations}")
            logger.info("=" * 60)
            logger.info("Note: Each job is matched to exactly ONE resume (the best valid candidate)")
            logger.info("      Same resume can be matched to multiple jobs")
            logger.info("=" * 60)
            
            return results
            
    except Exception as e:
        logger.error(f"Error running workflow: {e}")
        return None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run Greenhouse Resume-Job Matching Workflow")
    parser.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Reprocess all jobs including previously processed ones (overrides skip_processed_jobs)"
    )
    parser.add_argument(
        "--no-skip-processed",
        action="store_true",
        dest="no_skip",
        help="Don't skip already processed jobs (process all matching jobs)"
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Greenhouse Resume-Job Matching Workflow")
    print("=" * 60)
    
    # Determine processing mode
    if args.force_reprocess:
        skip_processed = False
        force_reprocess = True
        print("\n⚠️  FORCE REPROCESS MODE: Will reprocess ALL jobs including previously processed ones")
    elif args.no_skip:
        skip_processed = False
        force_reprocess = False
        print("\n⚠️  NO-SKIP MODE: Will process all matching jobs (may create duplicates)")
    else:
        skip_processed = True
        force_reprocess = False
        print("\nℹ️  DEFAULT MODE: Will skip already processed jobs")
        print("   Use --force-reprocess to reprocess all jobs")
        print("   Use --no-skip-processed to process all without skipping")
    
    print("=" * 60)
    
    results = run_workflow(force_reprocess=force_reprocess, skip_processed_jobs=skip_processed)
    
    if results:
        print("\n✅ Workflow completed successfully!")
    else:
        print("\n❌ Workflow failed!")
