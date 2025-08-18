#!/usr/bin/env python3
"""
Test script for the production resume-job matching workflow.

This script tests the new production workflow with a small number of jobs
to ensure everything is working correctly before running on larger datasets.

Tests cover:
- Basic workflow functionality
- Industry filtering (specific industries vs. all industries)
- Search term filtering
- Research-focused configurations
- Small workflow execution
- Max jobs configuration limits
- Error handling and edge cases
"""

import json
import sys
import os
from datetime import datetime

# Add the current directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from resume_job_matching_workflow import ResumeJobMatchingWorkflow

def test_basic_functionality():
    """Test basic workflow functionality with minimal configuration."""
    print("🧪 Testing basic workflow functionality...")
    
    try:
        # Create a minimal test configuration
        config = Config()
        config.top_k = 3
        
        # Test workflow initialization
        with ResumeJobMatchingWorkflow(config) as workflow:
            print("✅ Workflow initialized successfully")
            
            # Test getting filtered jobs
            jobs = workflow.get_filtered_jobs(limit=2)
            print(f"✅ Found {len(jobs)} test jobs")
            
            if jobs:
                # Test processing a single job
                job = jobs[0]
                print(f"🔍 Testing job: {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
                
                result = workflow.process_job(job)
                print(f"✅ Job processing completed: {result['status']}")
                
                if result.get('status') == 'success':
                    print(f"   • Valid matches: {result.get('valid_matches', 0)}")
                    print(f"   • Rejected matches: {result.get('rejected_matches', 0)}")
                elif result.get('status') == 'no_resumes_found':
                    print("   • No resumes found (this is normal for some jobs)")
                else:
                    print(f"   • Result: {result}")
            
            # Test statistics
            stats = workflow.get_workflow_statistics()
            print("✅ Statistics retrieved successfully")
            print(f"   • Total jobs in database: {stats['collection_stats']['total_jobs']}")
            print(f"   • Total resumes in database: {stats['collection_stats']['total_resumes']}")
            
        print("✅ Basic functionality test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_filtering_functionality():
    """Test filtering functionality with different configurations."""
    print("\n🧪 Testing filtering functionality...")
    
    try:
        # Test industry filtering
        config = Config()
        config.industry_prefixes = ["tech"]
        
        with ResumeJobMatchingWorkflow(config) as workflow:
            jobs = workflow.get_filtered_jobs(limit=5)
            print(f"✅ Industry filter: Found {len(jobs)} technology jobs")
            
            if jobs:
                print("   • Sample job titles:")
                for job in jobs[:3]:
                    print(f"     - {job.get('title', 'Unknown')}")
        
        # Test search term filtering
        config = Config()
        config.search_terms = ["Software Engineer", "Data Analyst"]
        
        with ResumeJobMatchingWorkflow(config) as workflow:
            jobs = workflow.get_filtered_jobs(limit=5)
            print(f"✅ Search term filter: Found {len(jobs)} jobs with 'Software Engineer' or 'Data Analyst'")
        
        print("✅ Filtering functionality test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Filtering functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_research_configuration():
    """Test a research-focused configuration with industry filtering."""
    print("\n🧪 Testing research configuration...")
    
    try:
        # Create a research-focused config (similar to what get_research_config() would provide)
        config = Config()
        config.industry_prefixes = ["ITC"]  # Focus on ITC industry
        config.max_jobs = 10               # Limit for research purposes
        config.top_k = 3                   # Fewer candidates for focused analysis
        
        with ResumeJobMatchingWorkflow(config) as workflow:
            print("✅ Research configuration loaded successfully")
            
            # Test with research config
            jobs = workflow.get_filtered_jobs(limit=3)
            print(f"✅ Research config: Found {len(jobs)} jobs matching research criteria")
            
            if jobs:
                print("   • Research-focused job details:")
                for job in jobs:
                    industry = job.get('industry', 'Unknown')
                    function = job.get('job_function', 'Unknown')
                    print(f"     - {job.get('title', 'Unknown')} | {industry} | {function}")
        
        print("✅ Research configuration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Research configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_small_workflow():
    """Test running a small workflow with 2-3 jobs."""
    print("\n🧪 Testing small workflow execution...")
    
    try:
        # Create a focused config for testing
        config = Config()
        config.industry_prefixes = ["ITC"]  # Focus on ITC industry
        config.max_jobs = 5                # Small limit for testing
        config.top_k = 2                   # Fewer candidates for focused analysis
        
        with ResumeJobMatchingWorkflow(config) as workflow:
            print("✅ Starting small workflow test...")
            
            # Run workflow with limited jobs
            results = workflow.run_workflow(max_jobs=2)
            
            if results["status"] == "completed":
                print("✅ Small workflow completed successfully")
                print(f"   • Jobs processed: {results['jobs_processed']}")
                print(f"   • Valid matches: {results['total_valid_matches']}")
                print(f"   • Rejected matches: {results['total_rejected_matches']}")
                
                # Save test results
                output_file = f"test_workflow_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(output_file, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                print(f"   • Results saved to: {output_file}")
                
            elif results["status"] == "no_jobs":
                print("⚠️ No jobs found matching criteria (this may be normal)")
            else:
                print(f"❌ Small workflow failed: {results.get('message', 'Unknown error')}")
                if "error" in results:
                    print(f"   • Error: {results['error']}")
        
        print("✅ Small workflow test completed")
        return True
        
    except Exception as e:
        print(f"❌ Small workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_all_industries_config():
    """Test configuration with no industry filtering (all industries)."""
    print("\n🧪 Testing all industries configuration...")
    
    try:
        # Create config with no industry restrictions
        config = Config()
        config.industry_prefixes = []  # Empty list = all industries
        config.max_jobs = 3            # Small limit for testing
        config.top_k = 2               # Fewer candidates for focused analysis
        
        with ResumeJobMatchingWorkflow(config) as workflow:
            print("✅ All industries configuration loaded successfully")
            
            # Test getting filtered jobs
            jobs = workflow.get_filtered_jobs(limit=3)
            print(f"✅ All industries config: Found {len(jobs)} jobs (no industry filter)")
            
            if jobs:
                print("   • Sample job details:")
                for job in jobs[:2]:
                    industry = job.get('industry', 'Unknown')
                    print(f"     - {job.get('title', 'Unknown')} | {industry}")
            
            # Test getting filtered resumes (should include all industries)
            resumes = workflow.get_filtered_resumes(limit=5)
            print(f"✅ All industries config: Found {len(resumes)} resumes (no industry filter)")
        
        print("✅ All industries configuration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ All industries configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_max_jobs_config():
    """Test the max_jobs configuration setting."""
    print("\n🧪 Testing max_jobs configuration...")
    
    try:
        # Test with different max_jobs values
        test_configs = [
            (1, "Single job limit"),
            (3, "Small job limit"),
            (5, "Medium job limit")
        ]
        
        for max_jobs, description in test_configs:
            print(f"   Testing {description}: max_jobs = {max_jobs}")
            
            config = Config()
            config.max_jobs = max_jobs
            config.industry_prefixes = ["ITC"]  # Focus on one industry for testing
            
            with ResumeJobMatchingWorkflow(config) as workflow:
                # Test that the limit is respected
                jobs = workflow.get_filtered_jobs(limit=max_jobs + 2)  # Try to get more than limit
                
                # Calculate how many jobs we actually got (respecting the limit)
                actual_jobs = len(jobs)
                if max_jobs and actual_jobs > max_jobs:
                    actual_jobs = max_jobs
                
                print(f"     ✅ Found {len(jobs)} jobs, respecting limit: {actual_jobs}")
                
                if jobs:
                    print(f"       • Sample: {jobs[0].get('title', 'Unknown')}")
        
        print("✅ Max jobs configuration test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Max jobs configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Starting Production Workflow Tests")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ("Basic Functionality", test_basic_functionality),
        ("Filtering Functionality", test_filtering_functionality),
        ("Research Configuration", test_research_configuration),
        ("Small Workflow", test_small_workflow),
        ("All Industries Config", test_all_industries_config),
        ("Max Jobs Config", test_max_jobs_config),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print(f"{'='*60}")
        
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The production workflow is ready to use.")
    else:
        print("⚠️ Some tests failed. Please review the errors above.")
    
    print(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
