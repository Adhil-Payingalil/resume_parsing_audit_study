#!/usr/bin/env python3
"""
Simple script to run the resume-job matching test workflow.

This script runs the test workflow and provides clear, formatted output
to help evaluate the matching performance.
"""

import json
import sys
import os
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from test_simple_matching_workflow import SimpleMatchingWorkflow

def print_header(title):
    """Print a formatted header."""
    print("\n" + "="*80)
    print(f" {title}")
    print("="*80)

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'-'*60}")
    print(f" {title}")
    print(f"{'-'*60}")

def format_job_result(job_result):
    """Format a single job result for display."""
    job_id = job_result["job_id"]
    job_title = job_result.get("title")
    company = job_result.get("company")
    result = job_result["result"]
    
    print(f"\nJob: {job_title}")
    print(f"Company: {company}")
    print(f"Job ID: {job_id}")
    
    if result["status"] == "success":
        print(f"✓ Status: {result['status']}")
        print(f"  Valid matches: {result['valid_matches']}")
        print(f"  Rejected matches: {result['rejected_matches']}")
        print(f"  Total processed: {result['total_processed']}")
    elif result["status"] == "no_resumes_found":
        print(f"⚠ Status: {result['status']}")
        print(f"  No resumes found for this job")
    else:
        print(f"✗ Status: {result['status']}")
        if "error" in result:
            print(f"  Error: {result['error']}")

def main():
    """Main function to run the test workflow."""
    try:
        print_header("RESUME-JOB MATCHING TEST WORKFLOW")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Initialize the workflow
        print_section("Initializing Workflow")
        workflow = SimpleMatchingWorkflow()
        print("✓ Workflow initialized successfully")
        
        # Get initial statistics
        print_section("Initial Statistics")
        initial_stats = workflow.get_test_statistics()
        print(f"Existing test matches: {initial_stats.get('test_matches', {}).get('total', 0)}")
        
        # Run the test workflow
        print_section("Running Test Workflow")
        print("Processing 5 test jobs...")
        results = workflow.run_test_workflow(num_jobs=5)
        
        # Display results
        print_section("Test Results Summary")
        if results["status"] == "completed":
            print(f"✓ Workflow completed successfully")
            print(f"Jobs processed: {results['jobs_processed']}")
            print(f"Total valid matches: {results['total_valid_matches']}")
            print(f"Total rejected matches: {results['total_rejected_matches']}")
            
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
        test_matches = final_stats.get('test_matches', {})
        print(f"Total test matches: {test_matches.get('total', 0)}")
        print(f"Validated matches: {test_matches.get('validated', 0)}")
        print(f"Rejected matches: {test_matches.get('rejected', 0)}")
        
        # Calculate success rate
        total_matches = test_matches.get('total', 0)
        validated_matches = test_matches.get('validated', 0)
        if total_matches > 0:
            success_rate = (validated_matches / total_matches) * 100
            print(f"Success rate: {success_rate:.1f}%")
        
        print_header("TEST COMPLETED")
        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Save detailed results to file
        output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "results": results,
                "statistics": final_stats
            }, f, indent=2, default=str)
        
        print(f"\nDetailed results saved to: {output_file}")
        
    except Exception as e:
        print(f"\n✗ Error running test workflow: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main() 