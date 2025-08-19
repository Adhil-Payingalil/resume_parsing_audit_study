"""
Batch Job Embedding Script

This script processes all existing job postings in the job_postings collection
and adds vector embeddings to each document for semantic search capabilities.

Usage:
    python batch_job_embedding.py

Features:
- Processes all job postings in job_postings collection
- Extracts key content for embedding generation
- Generates embeddings using Gemini API with caching
- Updates MongoDB documents with jd_embedding field
- Provides progress tracking and error handling
"""

import os
import sys
import time
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from libs.gemini_processor import GeminiProcessor
from libs.text_extraction import extract_job_content_from_mongo_doc
from utils import get_logger

logger = get_logger(__name__)

class BatchJobEmbeddingProcessor:
    """
    Processes job postings in batch to generate and store embeddings.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        self.db_name = db_name
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.job_collection = self.db["job_postings"]
        
        # Initialize Gemini processor for embeddings
        self.embedding_processor = GeminiProcessor(
            model_name="gemini-1.5-flash",  # Model doesn't matter for embeddings
            temperature=0.0,  # Not used for embeddings
            enable_google_search=False
        )
        
        logger.info(f"BatchJobEmbeddingProcessor initialized for database: {db_name}")
    
    def get_jobs_without_embeddings(self) -> List[Dict[str, Any]]:
        """
        Get all job postings that don't have embeddings yet.
        
        Returns:
            List[Dict[str, Any]]: List of job documents without embeddings
        """
        try:
            # Find documents that don't have jd_embedding field or have empty embedding
            query = {
                "$or": [
                    {"jd_embedding": {"$exists": False}},
                    {"jd_embedding": None},
                    {"jd_embedding": []}
                ]
            }
            
            jobs = list(self.job_collection.find(query))
            logger.info(f"Found {len(jobs)} job postings without embeddings")
            return jobs
            
        except Exception as e:
            logger.error(f"Error retrieving jobs without embeddings: {e}")
            return []
    
    def process_job_embedding(self, job_doc: Dict[str, Any]) -> bool:
        """
        Process a single job document to generate and store embedding.
        
        Args:
            job_doc (Dict[str, Any]): Job document from MongoDB
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            job_id = str(job_doc.get("_id", "unknown"))
            job_title = job_doc.get("job_title", "unknown")
            logger.info(f"Processing job: {job_title} (ID: {job_id})")
            
            # Extract content for embedding
            content = extract_job_content_from_mongo_doc(job_doc)
            if not content:
                logger.warning(f"No content extracted for job: {job_title}")
                return False
            
            # Generate embedding
            embedding = self.embedding_processor.generate_embedding(
                text=content,
                task_type="RETRIEVAL_QUERY"  # Jobs are queries for resume matching
            )
            
            if not embedding:
                logger.error(f"Failed to generate embedding for job: {job_title}")
                return False
            
            # Update document with embedding
            result = self.job_collection.update_one(
                {"_id": job_doc["_id"]},
                {
                    "$set": {
                        "jd_embedding": embedding,
                        "embedding_generated_at": datetime.now(),
                        "embedding_model": "embedding-001",
                        "embedding_task_type": "RETRIEVAL_QUERY"
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Successfully updated job {job_title} with embedding (dimensions: {len(embedding)})")
                return True
            else:
                logger.warning(f"No document updated for job: {job_title}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing job {job_doc.get('job_title', 'unknown')}: {e}")
            return False
    
    def process_all_jobs(self, batch_size: int = 10, delay_seconds: float = 1.0):
        """
        Process all job postings without embeddings in batches.
        
        Args:
            batch_size (int): Number of jobs to process in each batch
            delay_seconds (float): Delay between batches to avoid rate limiting
        """
        try:
            # Get all jobs without embeddings
            jobs = self.get_jobs_without_embeddings()
            
            if not jobs:
                logger.info("No job postings found without embeddings")
                return
            
            total_jobs = len(jobs)
            successful = 0
            failed = 0
            
            logger.info(f"Starting batch processing of {total_jobs} job postings")
            
            # Process in batches
            for i in range(0, total_jobs, batch_size):
                batch = jobs[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (total_jobs + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} jobs)")
                
                # Process each job in the batch
                for job in batch:
                    if self.process_job_embedding(job):
                        successful += 1
                    else:
                        failed += 1
                    
                    # Small delay between individual jobs
                    time.sleep(0.5)
                
                # Delay between batches
                if i + batch_size < total_jobs:
                    logger.info(f"Waiting {delay_seconds} seconds before next batch...")
                    time.sleep(delay_seconds)
            
            logger.info(f"Batch processing completed. Successful: {successful}, Failed: {failed}")
            
        except Exception as e:
            logger.error(f"Error in batch processing: {e}")
    
    def get_embedding_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about embedding status in the collection.
        
        Returns:
            Dict[str, Any]: Statistics about embeddings
        """
        try:
            total_docs = self.job_collection.count_documents({})
            docs_with_embeddings = self.job_collection.count_documents({"jd_embedding": {"$exists": True, "$ne": None, "$ne": []}})
            docs_without_embeddings = total_docs - docs_with_embeddings
            
            stats = {
                "total_documents": total_docs,
                "documents_with_embeddings": docs_with_embeddings,
                "documents_without_embeddings": docs_without_embeddings,
                "embedding_coverage_percentage": (docs_with_embeddings / total_docs * 100) if total_docs > 0 else 0
            }
            
            logger.info(f"Embedding statistics: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting embedding statistics: {e}")
            return {}

def main():
    """Main function to run the batch job embedding process."""
    try:
        logger.info("Starting batch job embedding process")
        
        # Initialize processor
        processor = BatchJobEmbeddingProcessor()
        
        # Get initial statistics
        initial_stats = processor.get_embedding_statistics()
        logger.info(f"Initial statistics: {initial_stats}")
        
        # Process all jobs
        processor.process_all_jobs(batch_size=5, delay_seconds=2.0)
        
        # Get final statistics
        final_stats = processor.get_embedding_statistics()
        logger.info(f"Final statistics: {final_stats}")
        
        logger.info("Batch job embedding process completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise

if __name__ == "__main__":
    main() 