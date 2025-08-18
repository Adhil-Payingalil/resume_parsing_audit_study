#!/usr/bin/env python3
"""
Simple Production Runner for Resume-Job Matching Workflow

This script runs the resume-job matching workflow with simple configuration.
Just modify the config section below to set your filters.
"""

import json
import sys
import os
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from resume_job_matching_workflow import ResumeJobMatchingWorkflow

def main():
    """Run the workflow with simple configuration."""
    print("🚀 Resume-Job Matching Workflow")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # ========================================
    # CONFIGURATION - EDIT IN config.py
    # ========================================
    
    # Use the default configuration from config.py
    # To change settings, edit the values directly in config.py
    config = Config()
    
    # ========================================
    # END CONFIGURATION
    # ========================================
    
    print("\n📋 Configuration:")
    if config.industry_prefixes:
        print(f"• Industry Prefixes: {config.industry_prefixes}")
    else:
        print("• Industry Prefixes: All industries")
        
    if config.search_terms:
        print(f"• Search Terms: {config.search_terms}")
    else:
        print("• Search Terms: All job types")
        
    if config.max_jobs:
        print(f"• Max Jobs: {config.max_jobs}")
    else:
        print("• Max Jobs: All matching jobs")
    
    print(f"• Top K: {config.top_k}")
    print(f"• Similarity Threshold: {config.similarity_threshold}")
    print(f"• Validation Threshold: {config.validation_threshold}")
    
    print("\n🚀 Starting workflow...")
    
    try:
        with ResumeJobMatchingWorkflow(config) as workflow:
            results = workflow.run_workflow()
            
            if results["status"] == "completed":
                print(f"\n✅ Workflow completed successfully!")
                print(f"• Jobs processed: {results['jobs_processed']}")
                print(f"• Valid matches: {results['total_valid_matches']}")
                print(f"• Rejected matches: {results['total_rejected_matches']}")
                print(f"• Success rate: {results['success_rate']:.1f}%")
                
                # Save results
                output_file = f"workflow_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"\n💾 Results saved to: {output_file}")
                
            else:
                print(f"\n❌ Workflow failed: {results.get('message', 'Unknown error')}")
                if "error" in results:
                    print(f"Error details: {results['error']}")
        
        print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
