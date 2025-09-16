#!/usr/bin/env python3
"""
Simple test script for Greenhouse workflow
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

def test_imports():
    """Test that all required imports work."""
    try:
        print("Testing imports...")
        
        # Test basic imports
        from libs.mongodb import _get_mongo_client
        print("✓ MongoDB import successful")
        
        from libs.gemini_processor import GeminiProcessor
        print("✓ Gemini processor import successful")
        
        from utils import get_logger
        print("✓ Utils import successful")
        
        # Test config import
        from greenhouse_config import GreenhouseConfig, default_greenhouse_config
        print("✓ Greenhouse config import successful")
        
        # Test workflow import
        from greenhouse_resume_job_matching_workflow import GreenhouseResumeJobMatchingWorkflow
        print("✓ Greenhouse workflow import successful")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

def test_config():
    """Test configuration creation."""
    try:
        print("\nTesting configuration...")
        
        from greenhouse_config import GreenhouseConfig
        
        config = GreenhouseConfig(
            industry_prefixes=["ITC"],
            max_jobs=5
        )
        
        print(f"✓ Config created successfully")
        print(f"  - Database: {config.db_name}")
        print(f"  - Job collection: {config.collections['job_postings']}")
        print(f"  - Matches collection: {config.collections['matches']}")
        print(f"  - Industry prefixes: {config.industry_prefixes}")
        
        return True
        
    except Exception as e:
        print(f"✗ Config error: {e}")
        return False

def test_workflow_init():
    """Test workflow initialization."""
    try:
        print("\nTesting workflow initialization...")
        
        from greenhouse_resume_job_matching_workflow import GreenhouseResumeJobMatchingWorkflow
        from greenhouse_config import GreenhouseConfig
        
        config = GreenhouseConfig(max_jobs=1)  # Minimal config for testing
        
        # Try to initialize workflow (this will test MongoDB connection)
        workflow = GreenhouseResumeJobMatchingWorkflow(config=config)
        print("✓ Workflow initialized successfully")
        
        # Test cleanup
        workflow.cleanup()
        print("✓ Workflow cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"✗ Workflow initialization error: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("Greenhouse Workflow Simple Test")
    print("=" * 60)
    
    tests = [
        ("Import Test", test_imports),
        ("Configuration Test", test_config),
        ("Workflow Initialization Test", test_workflow_init),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
            print(f"✓ {test_name} PASSED")
        else:
            print(f"✗ {test_name} FAILED")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All tests passed! The Greenhouse workflow is ready to use.")
        return True
    else:
        print("✗ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
