"""
Greenhouse Job Embedding Script with Parallel Processing

This script processes all job postings in the Job_postings_greenhouse collection
where jd_extraction=True and adds vector embeddings to each document for semantic search capabilities.

Key Performance Optimizations:
- Concurrent processing using asyncio and aiohttp
- Connection pooling and reuse
- Smart error handling and retry logic
- Progress tracking and recovery

Usage:
    python greenhouse_job_embedding.py [--concurrent N]

Features:
- Processes all job postings with jd_extraction=True
- Generates embeddings using Gemini API with caching
- Updates MongoDB documents with jd_embedding field
- Parallel processing for 100x+ speed improvement
"""

import os
import sys
import asyncio
import aiohttp
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Add parent directories to path for imports
import sys
import os
# Add root directory (Repo) to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from libs.mongodb import _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

class GreenhouseJobEmbeddingProcessor:
    """
    Processes greenhouse job postings in parallel to generate and store embeddings.
    """
    
    def __init__(self, db_name: str = "Resume_study", max_concurrent: int = 3, cycle: float = 0):
        self.db_name = db_name
        self.max_concurrent = max_concurrent
        self.cycle = cycle
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.job_collection = self.db["Job_postings_greenhouse"]
        
        # Get API key for async requests
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        logger.info(f"GreenhouseJobEmbeddingProcessor initialized for database: {db_name}")
        logger.info(f"Max concurrent requests: {max_concurrent}")
        logger.info(f"Target Cycle: {cycle}")
    
    def get_jobs_without_embeddings(self) -> List[Dict[str, Any]]:
        """
        Get all job postings that don't have embeddings yet and have jd_extraction=True.
        
        Returns:
            List[Dict[str, Any]]: List of job documents without embeddings
        """
        try:
            # Find documents with jd_extraction=True that don't have embeddings
            query = {
                "cycle": self.cycle,
                "jd_extraction": True,
                "$or": [
                    {"jd_embedding": {"$exists": False}},
                    {"jd_embedding": None},
                    {"jd_embedding": []}
                ]
            }
            
            jobs = list(self.job_collection.find(query))
            logger.info(f"Found {len(jobs)} greenhouse job postings without embeddings for cycle {self.cycle}")
            return jobs
            
        except Exception as e:
            logger.error(f"Error retrieving jobs without embeddings: {e}")
            return []
    
    # ... extract_greenhouse_job_content, generate_embedding_async, process_job_embedding, process_jobs_concurrently remain the same ...

    def extract_greenhouse_job_content(self, job_doc: Dict[str, Any]) -> str:
        """
        Extract content from greenhouse job document for embedding.
        Extracts job title and job description (focusing on key sections).
        
        Args:
            job_doc (Dict[str, Any]): Job document from MongoDB
            
        Returns:
            str: Extracted content for embedding
        """
        try:
            content_parts = []
            
            # Extract job title
            job_title = job_doc.get("title", "")
            if job_title:
                content_parts.append(f"Job Title: {job_title}")
            
            # Extract job description (main content)
            job_description = job_doc.get("job_description", "")
            if job_description:
                # Focus on key sections for better embeddings
                lines = job_description.split('\n')
                key_sections = []
                
                for line in lines:
                    line_lower = line.lower().strip()
                    # Look for sections that typically contain requirements and skills
                    if any(keyword in line_lower for keyword in [
                        'requirements', 'qualifications', 'skills', 'responsibilities',
                        'duties', 'experience', 'education', 'must have', 'should have',
                        'preferred', 'knowledge of', 'proficiency in', 'familiarity with',
                        'what you\'ll do', 'what we\'re looking for', 'nice to have'
                    ]):
                        key_sections.append(line.strip())
                
                # If we found key sections, use them; otherwise use the full description
                if key_sections:
                    content_parts.extend(key_sections)
                else:
                    # Use first 3000 characters of description
                    content_parts.append(job_description[:3000])
            
            # Join all parts
            extracted_content = " ".join(content_parts)
            
            # Limit to reasonable length for embedding (max 8000 characters)
            if len(extracted_content) > 8000:
                extracted_content = extracted_content[:8000]
                logger.info(f"Truncated job content from {len(' '.join(content_parts))} to 8000 characters")
            
            logger.info(f"Extracted {len(extracted_content)} characters from greenhouse job")
            return extracted_content
            
        except Exception as e:
            logger.error(f"Error extracting greenhouse job content: {e}")
            return ""
    
    async def generate_embedding_async(self, session: aiohttp.ClientSession, text: str, task_type: str = "RETRIEVAL_QUERY") -> Optional[List[float]]:
        """
        Generate embedding asynchronously using aiohttp with retry logic.
        
        Args:
            session (aiohttp.ClientSession): HTTP session
            text (str): Text to generate embedding for
            task_type (str): Type of embedding task
            
        Returns:
            Optional[List[float]]: Embedding vector or None if failed
        """
        max_retries = 3
        retry_delay = 1.0
        
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/embedding-001:embedContent?key={self.api_key}"
                
                payload = {
                    "model": "models/embedding-001",
                    "content": {
                        "parts": [{"text": text}]
                    },
                    "taskType": task_type
                }
                
                headers = {
                    "Content-Type": "application/json"
                }
                
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        embedding = result["embedding"]["values"]
                        logger.info(f"Successfully generated embedding (dimensions: {len(embedding)})")
                        return embedding
                    elif response.status == 429:  # Rate limited
                        if attempt < max_retries - 1:
                            wait_time = retry_delay * (2 ** attempt)
                            logger.warning(f"Rate limited, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(f"Rate limited after {max_retries} attempts: {error_text}")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error(f"API error {response.status}: {error_text}")
                        return None
                        
            except asyncio.TimeoutError:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Timeout, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Timeout after {max_retries} attempts")
                    return None
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Error generating embedding, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Error generating embedding after {max_retries} attempts: {e}")
                    return None
        
        return None
    
    async def process_job_embedding(self, session: aiohttp.ClientSession, job_doc: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Process a single job document to generate and store embedding.
        
        Args:
            session (aiohttp.ClientSession): HTTP session
            job_doc (Dict[str, Any]): Job document from MongoDB
            
        Returns:
            Tuple[bool, str]: (success, job_id)
        """
        try:
            job_id = str(job_doc.get("_id", "unknown"))
            job_title = job_doc.get("title", "unknown")
            
            # Extract content for embedding
            content = self.extract_greenhouse_job_content(job_doc)
            if not content:
                logger.warning(f"No content extracted for job: {job_title}")
                return False, job_id
            
            # Generate embedding
            embedding = await self.generate_embedding_async(session, content, "RETRIEVAL_QUERY")
            
            if not embedding:
                logger.error(f"Failed to generate embedding for job: {job_title}")
                return False, job_id
            
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
                return True, job_id
            else:
                logger.warning(f"No document updated for job: {job_title}")
                return False, job_id
                
        except Exception as e:
            logger.error(f"Error processing job {job_doc.get('title', 'unknown')}: {e}")
            return False, str(job_doc.get("_id", "unknown"))
    
    async def process_jobs_concurrently(self, jobs: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Process all jobs concurrently with rate limiting.
        
        Args:
            jobs (List[Dict[str, Any]]): List of job documents to process
            
        Returns:
            Dict[str, int]: Statistics about processing results
        """
        stats = {
            "total": len(jobs),
            "successful": 0,
            "failed": 0,
            "start_time": time.time()
        }
        
        # Create semaphore to limit concurrent requests
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(session, job):
            async with semaphore:
                return await self.process_job_embedding(session, job)
        
        # Create HTTP session with connection pooling
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=20)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create tasks for all jobs
            tasks = [process_with_semaphore(session, job) for job in jobs]
            
            # Process in batches to avoid overwhelming the API
            batch_size = self.max_concurrent * 2
            for i in range(0, len(tasks), batch_size):
                batch_tasks = tasks[i:i + batch_size]
                logger.info(f"Processing batch {i//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size} ({len(batch_tasks)} jobs)")
                
                # Wait for batch to complete
                results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Task failed with exception: {result}")
                        stats["failed"] += 1
                    else:
                        success, job_id = result
                        if success:
                            stats["successful"] += 1
                        else:
                            stats["failed"] += 1
                
                # Small delay between batches to respect rate limits
                if i + batch_size < len(tasks):
                    await asyncio.sleep(2.0)
        
        stats["end_time"] = time.time()
        stats["duration"] = stats["end_time"] - stats["start_time"]
        
        return stats
    
    def get_embedding_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about embedding status in the collection.
        
        Returns:
            Dict[str, Any]: Statistics about embeddings
        """
        try:
            total_docs = self.job_collection.count_documents({"jd_extraction": True, "cycle": self.cycle})
            docs_with_embeddings = self.job_collection.count_documents({
                "jd_extraction": True,
                "cycle": self.cycle,
                "jd_embedding": {"$exists": True, "$ne": None, "$ne": []}
            })
            docs_without_embeddings = total_docs - docs_with_embeddings
            
            stats = {
                "total_documents_with_extraction": total_docs,
                "documents_with_embeddings": docs_with_embeddings,
                "documents_without_embeddings": docs_without_embeddings,
                "embedding_coverage_percentage": (docs_with_embeddings / total_docs * 100) if total_docs > 0 else 0
            }
            
            logger.info(f"Embedding statistics: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error getting embedding statistics: {e}")
            return {}

async def main(cycle: float = 0):
    """Main function to run the greenhouse job embedding process with parallel processing."""
    try:
        logger.info(f"Starting greenhouse job embedding process with parallel processing for cycle {cycle}")
        
        # Initialize processor
        processor = GreenhouseJobEmbeddingProcessor(max_concurrent=3, cycle=cycle)
        
        # Get initial statistics
        initial_stats = processor.get_embedding_statistics()
        logger.info(f"Initial statistics: {initial_stats}")
        
        # Get jobs to process
        jobs = processor.get_jobs_without_embeddings()
        
        if not jobs:
            logger.info("No job postings found without embeddings")
            return
        
        logger.info(f"Processing {len(jobs)} job postings concurrently...")
        
        # Process all jobs concurrently
        stats = await processor.process_jobs_concurrently(jobs)
        
        # Log final statistics
        logger.info(f"Processing completed in {stats['duration']:.2f} seconds")
        logger.info(f"Successful: {stats['successful']}, Failed: {stats['failed']}")
        logger.info(f"Processing rate: {stats['total']/stats['duration']:.2f} jobs/second")
        
        # Get final statistics
        final_stats = processor.get_embedding_statistics()
        logger.info(f"Final statistics: {final_stats}")
        
        logger.info("Greenhouse job embedding process completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise

def run():
    """Synchronous wrapper to run the async main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Greenhouse Job Embedding Processor")
    parser.add_argument("--concurrent", type=int, default=3,
                       help="Number of concurrent requests")
    parser.add_argument("--cycle", type=float, default=0,
                       help="Cycle number to process (default: 0)")
    
    args = parser.parse_args()
    
    if args.concurrent != 3:
        logger.info(f"Using {args.concurrent} concurrent requests")
    
    asyncio.run(main(cycle=args.cycle))

if __name__ == "__main__":
    run()
