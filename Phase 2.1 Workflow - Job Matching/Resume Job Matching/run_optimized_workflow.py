"""
Optimized Resume-to-Job Matching Workflow Runner

This script runs the optimized resume-to-job matching workflow with detailed output.
"""

import os
import sys
import argparse
import time
import json
from datetime import datetime
from typing import List, Dict, Any

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resume_job_matcher_optimized import OptimizedResumeJobMatcher
from utils import get_logger

logger = get_logger(__name__)

class OptimizedMatchingWorkflowRunner:
    """
    Optimized runner for the resume-to-job matching workflow with detailed output.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        """
        Initialize the workflow runner.
        
        Args:
            db_name (str): MongoDB database name
        """
        self.db_name = db_name
        self.matcher = OptimizedResumeJobMatcher(db_name)
        logger.info(f"OptimizedMatchingWorkflowRunner initialized for database: {db_name}")
    
    def run_batch_matching(self, 
                          batch_size: int = 10, 
                          max_jobs: int = None,
                          delay_between_jobs: float = 1.0,
                          similarity_threshold: float = 0.3) -> Dict[str, Any]:
        """
        Run batch matching for multiple jobs with detailed output.
        
        Args:
            batch_size (int): Number of jobs to process in each batch
            max_jobs (int): Maximum total jobs to process (None for all)
            delay_between_jobs (float): Delay between processing jobs (seconds)
            similarity_threshold (float): Minimum similarity threshold for validation
            
        Returns:
            Dict[str, Any]: Summary of the batch processing
        """
        logger.info(f"Starting optimized batch matching workflow...")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Max jobs: {max_jobs if max_jobs else 'All'}")
        logger.info(f"Delay between jobs: {delay_between_jobs}s")
        logger.info(f"Similarity threshold: {similarity_threshold}")
        
        # Get initial statistics
        initial_stats = self.matcher.get_matching_statistics()
        logger.info(f"Initial statistics: {json.dumps(initial_stats, indent=2, default=str)}")
        
        total_processed = 0
        total_matches_created = 0
        successful_jobs = 0
        failed_jobs = 0
        detailed_results = []
        
        start_time = datetime.now()
        
        while True:
            # Get pending jobs
            pending_jobs = self.matcher.get_pending_jobs(limit=batch_size)
            
            if not pending_jobs:
                logger.info("No more pending jobs to process")
                break
            
            logger.info(f"Processing batch of {len(pending_jobs)} jobs...")
            
            batch_results = []
            for i, job in enumerate(pending_jobs):
                job_id = job.get("_id")
                job_title = job.get("job_title", "Unknown")
                company_name = job.get("company_name", "Unknown")
                
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing job {i+1}/{len(pending_jobs)}: {job_title} at {company_name}")
                logger.info(f"Job ID: {job_id}")
                logger.info(f"{'='*60}")
                
                try:
                    # Process the job
                    result = self.matcher.process_job_matching(job)
                    batch_results.append(result)
                    detailed_results.append(result)
                    
                    # Update counters
                    total_processed += 1
                    if result.get("status") == "success":
                        successful_jobs += 1
                        total_matches_created += result.get("matches_created", 0)
                    else:
                        failed_jobs += 1
                    
                    # Display detailed results
                    self._display_job_results(result)
                    
                except Exception as e:
                    logger.error(f"Error processing job {job_id}: {e}")
                    failed_jobs += 1
                    total_processed += 1
                
                # Check if we've reached max jobs
                if max_jobs and total_processed >= max_jobs:
                    logger.info(f"Reached maximum jobs limit ({max_jobs})")
                    break
                
                # Delay between jobs
                if delay_between_jobs > 0:
                    time.sleep(delay_between_jobs)
            
            # Check if we've reached max jobs
            if max_jobs and total_processed >= max_jobs:
                break
        
        end_time = datetime.now()
        processing_duration = (end_time - start_time).total_seconds()
        
        # Get final statistics
        final_stats = self.matcher.get_matching_statistics()
        
        # Create summary
        summary = {
            "processing_summary": {
                "total_jobs_processed": total_processed,
                "successful_jobs": successful_jobs,
                "failed_jobs": failed_jobs,
                "total_matches_created": total_matches_created,
                "processing_duration_seconds": processing_duration,
                "jobs_per_minute": (total_processed / processing_duration * 60) if processing_duration > 0 else 0
            },
            "detailed_results": detailed_results,
            "initial_statistics": initial_stats,
            "final_statistics": final_stats,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        logger.info(f"\n{'='*60}")
        logger.info("BATCH MATCHING WORKFLOW COMPLETED!")
        logger.info(f"{'='*60}")
        logger.info(f"Summary: {json.dumps(summary['processing_summary'], indent=2)}")
        
        return summary
    
    def _display_job_results(self, result: Dict[str, Any]):
        """Display detailed results for a single job."""
        status = result.get("status", "unknown")
        job_details = result.get("job_details", {})
        top_resumes = result.get("top_resumes", [])
        
        logger.info(f"\nJob: {job_details.get('title', 'Unknown')} at {job_details.get('company', 'Unknown')}")
        logger.info(f"Status: {status.upper()}")
        
        if status == "success":
            matches_created = result.get("matches_created", 0)
            logger.info(f"[SUCCESS] Created {matches_created} valid matches")
        elif status == "no_valid_matches":
            logger.info(f"[FAILED] No valid matches found")
        elif status == "no_resumes_found":
            logger.info(f"[WARNING] No resumes found for matching")
        else:
            logger.info(f"[ERROR] {result.get('error', 'Unknown error')}")
        
        if top_resumes:
            logger.info(f"\nTop 4 Resumes Evaluated:")
            logger.info(f"{'Rank':<4} {'File ID':<20} {'Similarity':<12} {'LLM Score':<12} {'Valid':<6}")
            logger.info(f"{'-'*60}")
            
            for resume in top_resumes:
                rank = resume.get("rank", "?")
                file_id = resume.get("file_id", "Unknown")[:18] + ".." if len(resume.get("file_id", "")) > 20 else resume.get("file_id", "Unknown")
                similarity = f"{resume.get('similarity_score', 0):.3f}"
                llm_score = f"{resume.get('llm_score', 'N/A')}" if resume.get('llm_score') is not None else "N/A"
                is_valid = "[YES]" if resume.get("is_valid", False) else "[NO]"
                
                logger.info(f"{rank:<4} {file_id:<20} {similarity:<12} {llm_score:<12} {is_valid:<6}")
            
            # Show reasoning for top match
            if top_resumes and top_resumes[0].get("reasoning"):
                logger.info(f"\nTop Match Reasoning:")
                logger.info(f"{top_resumes[0].get('reasoning', 'No reasoning available')}")
        
        logger.info(f"\n{'-'*60}")
    
    def run_single_job_matching(self, job_id: str) -> Dict[str, Any]:
        """
        Run matching for a single specific job with detailed output.
        
        Args:
            job_id (str): MongoDB ObjectId of the job to process
            
        Returns:
            Dict[str, Any]: Processing result
        """
        logger.info(f"Processing single job: {job_id}")
        
        try:
            # Get the job document
            from bson import ObjectId
            job = self.matcher.job_collection.find_one({"_id": ObjectId(job_id)})
            
            if not job:
                logger.error(f"Job with ID {job_id} not found")
                return {"status": "error", "error": "Job not found"}
            
            # Process the job
            result = self.matcher.process_job_matching(job)
            
            # Display results
            self._display_job_results(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing single job {job_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """
        Get current status of the matching workflow with recent activity.
        
        Returns:
            Dict[str, Any]: Current workflow status
        """
        try:
            stats = self.matcher.get_matching_statistics()
            
            # Get recent activity
            recent_matches = list(self.matcher.matches_collection.find().sort("created_at", -1).limit(5))
            recent_unmatched = list(self.matcher.unmatched_collection.find().sort("created_at", -1).limit(5))
            
            status = {
                "statistics": stats,
                "recent_matches": [
                    {
                        "job_title": match.get("job_title"),
                        "company_name": match.get("company_name"),
                        "resume_file_id": match.get("file_id"),
                        "match_score": match.get("match_score"),
                        "similarity_score": match.get("semantic_similarity"),
                        "created_at": match.get("created_at")
                    }
                    for match in recent_matches
                ],
                "recent_unmatched": [
                    {
                        "job_title": unmatched.get("job_title"),
                        "company_name": unmatched.get("company_name"),
                        "rejection_reason": unmatched.get("rejection_reason"),
                        "top_similarity_score": unmatched.get("top_similarity_score"),
                        "top_resumes_evaluated": unmatched.get("top_resumes_evaluated", []),
                        "created_at": unmatched.get("created_at")
                    }
                    for unmatched in recent_unmatched
                ]
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting workflow status: {e}")
            return {"error": str(e)}

def main():
    """Main function to run the optimized matching workflow."""
    parser = argparse.ArgumentParser(description="Optimized Resume-to-Job Matching Workflow")
    parser.add_argument("--mode", choices=["batch", "single", "status"], default="batch",
                       help="Mode to run: batch processing, single job, or status check")
    parser.add_argument("--batch-size", type=int, default=10,
                       help="Number of jobs to process in each batch")
    parser.add_argument("--max-jobs", type=int, default=None,
                       help="Maximum total jobs to process")
    parser.add_argument("--delay", type=float, default=1.0,
                       help="Delay between processing jobs (seconds)")
    parser.add_argument("--job-id", type=str, default=None,
                       help="Specific job ID to process (for single mode)")
    parser.add_argument("--db-name", type=str, default="Resume_study",
                       help="MongoDB database name")
    
    args = parser.parse_args()
    
    try:
        runner = OptimizedMatchingWorkflowRunner(args.db_name)
        
        if args.mode == "batch":
            summary = runner.run_batch_matching(
                batch_size=args.batch_size,
                max_jobs=args.max_jobs,
                delay_between_jobs=args.delay
            )
            logger.info("Optimized batch processing completed successfully")
            
        elif args.mode == "single":
            if not args.job_id:
                logger.error("Job ID is required for single mode")
                return 1
            
            result = runner.run_single_job_matching(args.job_id)
            logger.info(f"Single job processing completed: {result.get('status')}")
            
        elif args.mode == "status":
            status = runner.get_workflow_status()
            logger.info(f"Workflow status: {json.dumps(status, indent=2, default=str)}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main()) 