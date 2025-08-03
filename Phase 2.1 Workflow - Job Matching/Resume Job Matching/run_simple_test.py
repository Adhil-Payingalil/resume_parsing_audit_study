#!/usr/bin/env python3
"""
Simple script to run the resume-job matching test workflow.

This script runs the test workflow with MongoDB vector search and batch LLM validation,
providing detailed, formatted output to evaluate matching performance.
"""

import json
import sys
import os
from datetime import datetime
from typing import Dict, Any
from bson import ObjectId

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_simple_matching_workflow import SimpleMatchingWorkflow

def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "="*100)
    print(f" {title}")
    print("="*100)

def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{'-'*80}")
    print(f" {title}")
    print(f"{'-'*80}")

def format_match_details(matched_resumes: list) -> None:
    """Format and print match details."""
    print("\nMatched Resumes:")
    print(f"{'Rank':<6} {'File ID':<30} {'Similarity':<12} {'LLM Score':<10} {'Status':<8}")
    print("-" * 70)
    
    for resume in sorted(matched_resumes, key=lambda x: x.get('rank', 999)):
        similarity = resume.get('similarity_score', 0.0)
        llm_score = resume.get('llm_score', 0)
        status = "✓" if llm_score >= 70 else "✗"
        
        print(f"{resume.get('rank', '-'):<6} "
              f"{resume.get('file_id', 'Unknown'):<30} "
              f"{similarity:.3f}{'':>5} "
              f"{llm_score:<10} "
              f"{status:<8}")
        
        # Print the summary indented
        summary = resume.get('summary', '')
        if summary:
            print(f"  → {summary}")

def format_job_result(job_result: Dict[str, Any]) -> None:
    """Format a single job result for display."""
    job_id = job_result["job_id"]
    job_title = job_result.get("title", "Unknown")
    company = job_result.get("company", "Unknown")
    result = job_result["result"]
    
    print(f"\n📋 Job Details:")
    print(f"Title: {job_title}")
    print(f"Company: {company}")
    print(f"ID: {job_id}")
    
    if result["status"] == "success":
        print(f"\n✓ Status: {result['status'].upper()}")
        print(f"• Valid matches: {result['valid_matches']}")
        print(f"• Rejected matches: {result['rejected_matches']}")
        print(f"• Total processed: {result['total_processed']}")
        
        if result.get('best_match'):
            print(f"\n🏆 Best Match:")
            print(f"• ID: {result['best_match']}")
            if result.get('best_match_summary'):
                print(f"• Summary: {result['best_match_summary']}")
    
    elif result["status"] == "no_resumes_found":
        print(f"\n⚠ Status: {result['status'].upper()}")
        print("No resumes found for this job")
    else:
        print(f"\n✗ Status: {result['status'].upper()}")
        if "error" in result:
            print(f"Error: {result['error']}")

def format_collection_stats(db_stats: Dict[str, Any]) -> None:
    """Format and print collection statistics."""
    matches = db_stats.get('matches', {})
    unmatched = db_stats.get('unmatched', {})
    
    print("\n📊 Collection Statistics:")
    print(f"{'Collection':<25} {'Total':<10} {'Valid':<10} {'Rejected':<10}")
    print("-" * 55)
    print(f"{'resume_job_matches':<25} "
          f"{matches.get('total', 0):<10} "
          f"{matches.get('validated', 0):<10} "
          f"{matches.get('rejected', 0):<10}")
    print(f"{'unmatched_job_postings':<25} "
          f"{unmatched.get('total', 0):<10} "
          f"{'N/A':<10} "
          f"{'N/A':<10}")

def main():
    """Main function to run the test workflow."""
    try:
        print_header("RESUME-JOB MATCHING TEST WORKFLOW")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Initialize the workflow
        print_section("Initializing Workflow")
        workflow = SimpleMatchingWorkflow()
        print("✓ Workflow initialized successfully")
        print("• Using MongoDB Vector Search")
        print("• Using Gemini Pro for validation")
        
        # Get initial statistics
        print_section("Initial Statistics")
        initial_stats = workflow.get_test_statistics()
        format_collection_stats(initial_stats)
        
        # Run the test workflow
        print_section("Running Test Workflow")
        print("Processing 5 test jobs...")
        results = workflow.run_test_workflow(num_jobs=5)
        
        # Display results
        print_section("Test Results Summary")
        if results["status"] == "completed":
            print(f"✓ Workflow completed successfully")
            print(f"\n📈 Overall Results:")
            print(f"• Jobs processed: {results['jobs_processed']}")
            print(f"• Valid matches: {results['total_valid_matches']}")
            print(f"• Rejected matches: {results['total_rejected_matches']}")
            
            # Display individual job results
            print_section("Individual Job Results")
            for job_result in results["job_results"]:
                format_job_result(job_result)
        else:
            print(f"✗ Workflow failed: {results.get('message', 'Unknown error')}")
            if "error" in results:
                print(f"Error details: {results['error']}")
        
        # Get final statistics
        print_section("Final Statistics")
        final_stats = workflow.get_test_statistics()
        format_collection_stats(final_stats)
        
        # Calculate success metrics
        total_jobs = results.get('jobs_processed', 0)
        valid_matches = results.get('total_valid_matches', 0)
        if total_jobs > 0:
            success_rate = (valid_matches / total_jobs) * 100
            print(f"\n📊 Success Metrics:")
            print(f"• Match success rate: {success_rate:.1f}%")
            print(f"• Average matches per job: {valid_matches/total_jobs:.1f}")
        
        print_header("TEST COMPLETED")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save detailed results to file
        output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "statistics": final_stats,
                "success_metrics": {
                    "success_rate": success_rate if total_jobs > 0 else 0,
                    "avg_matches_per_job": valid_matches/total_jobs if total_jobs > 0 else 0
                }
            }, f, indent=2, default=str)
        
        print(f"\n💾 Detailed results saved to: {output_file}")
        
    except Exception as e:
        print(f"\n✗ Error running test workflow: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()