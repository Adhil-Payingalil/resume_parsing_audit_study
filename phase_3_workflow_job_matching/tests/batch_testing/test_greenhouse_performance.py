"""
Test Script for Greenhouse Job Embedding Performance

This script tests the performance of the parallel processing
greenhouse job embedding script.

Usage:
    python test_greenhouse_performance.py
"""

import os
import sys
import time
import asyncio
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

def get_test_jobs(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get a small sample of jobs for testing.
    
    Args:
        limit (int): Maximum number of jobs to retrieve
        
    Returns:
        List[Dict[str, Any]]: List of test job documents
    """
    try:
        mongo_client = _get_mongo_client()
        if not mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        db = mongo_client["Resume_study"]
        collection = db["Job_postings_greenhouse"]
        
        # Get jobs with jd_extraction=True that don't have embeddings
        query = {
            "jd_extraction": True,
            "$or": [
                {"jd_embedding": {"$exists": False}},
                {"jd_embedding": None},
                {"jd_embedding": []}
            ]
        }
        
        jobs = list(collection.find(query).limit(limit))
        logger.info(f"Retrieved {len(jobs)} test jobs")
        
        mongo_client.close()
        return jobs
        
    except Exception as e:
        logger.error(f"Error retrieving test jobs: {e}")
        return []

def clear_test_embeddings(job_ids: List[str]):
    """
    Clear embeddings from test jobs to allow re-testing.
    
    Args:
        job_ids (List[str]): List of job IDs to clear embeddings from
    """
    try:
        mongo_client = _get_mongo_client()
        if not mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        db = mongo_client["Resume_study"]
        collection = db["Job_postings_greenhouse"]
        
        # Clear embeddings from test jobs
        from bson import ObjectId
        object_ids = [ObjectId(job_id) for job_id in job_ids]
        
        result = collection.update_many(
            {"_id": {"$in": object_ids}},
            {"$unset": {"jd_embedding": "", "embedding_generated_at": "", "embedding_model": "", "embedding_task_type": ""}}
        )
        
        logger.info(f"Cleared embeddings from {result.modified_count} test jobs")
        mongo_client.close()
        
    except Exception as e:
        logger.error(f"Error clearing test embeddings: {e}")

async def test_async_performance(jobs: List[Dict[str, Any]], max_concurrent: int = 3) -> Dict[str, Any]:
    """
    Test async processing performance.
    
    Args:
        jobs (List[Dict[str, Any]]): Jobs to process
        max_concurrent (int): Maximum concurrent requests
        
    Returns:
        Dict[str, Any]: Performance statistics
    """
    try:
        from greenhouse_job_embedding import GreenhouseJobEmbeddingProcessor
        
        processor = GreenhouseJobEmbeddingProcessor(max_concurrent=max_concurrent)
        
        start_time = time.time()
        stats = await processor.process_jobs_concurrently(jobs)
        end_time = time.time()
        
        stats["total_time"] = end_time - start_time
        stats["jobs_per_second"] = len(jobs) / stats["total_time"]
        
        return stats
        
    except Exception as e:
        logger.error(f"Error in async performance test: {e}")
        return {"error": str(e)}


async def main():
    """Main test function."""
    try:
        logger.info("Starting greenhouse job embedding performance test")
        
        # Get test jobs (limit to 5 for testing)
        test_jobs = get_test_jobs(limit=5)
        
        if not test_jobs:
            logger.error("No test jobs available")
            return
        
        job_ids = [str(job["_id"]) for job in test_jobs]
        logger.info(f"Testing with {len(test_jobs)} jobs")
        
        # Clear any existing embeddings
        clear_test_embeddings(job_ids)
        
        # Test async processing
        logger.info("Testing async processing...")
        async_stats = await test_async_performance(test_jobs, max_concurrent=3)
        
        # Display results
        logger.info("\n" + "="*50)
        logger.info("PERFORMANCE TEST RESULTS")
        logger.info("="*50)
        
        if "error" not in async_stats:
            logger.info(f"Async Processing:")
            logger.info(f"  - Total time: {async_stats['total_time']:.2f} seconds")
            logger.info(f"  - Jobs per second: {async_stats['jobs_per_second']:.2f}")
            logger.info(f"  - Successful: {async_stats['successful']}")
            logger.info(f"  - Failed: {async_stats['failed']}")
        else:
            logger.error(f"Test failed: {async_stats['error']}")
        
        logger.info("="*50)
        
    except Exception as e:
        logger.error(f"Error in performance test: {e}")

if __name__ == "__main__":
    asyncio.run(main())
