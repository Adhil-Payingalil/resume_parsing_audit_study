"""
Test Job Embedding and Semantic Search

This script tests:
1. Job embedding generation for a single document
2. Semantic search to find matching resumes
3. Cosine similarity calculations between job and resume embeddings

Usage:
    python test_job_embedding_and_search.py
"""

import os
import sys
import json
from typing import List, Dict, Any, Tuple
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.mongodb import _get_mongo_client
from libs.gemini_processor import GeminiProcessor
from libs.text_extraction import extract_job_content_from_mongo_doc, extract_resume_content_from_mongo_doc
from utils import get_logger
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = get_logger(__name__)

class JobEmbeddingAndSearchTester:
    """
    Test class for job embedding generation and semantic search functionality.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        self.db_name = db_name
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.job_collection = self.db["job_postings"]
        self.resume_collection = self.db["Standardized_resume_data"]
        
        # Initialize Gemini processor for embeddings
        self.embedding_processor = GeminiProcessor(
            model_name="gemini-1.5-flash",  # Model doesn't matter for embeddings
            temperature=0.0,  # Not used for embeddings
            enable_google_search=False
        )
        
        logger.info(f"JobEmbeddingAndSearchTester initialized for database: {db_name}")
    
    def check_collections(self):
        """
        Check the status of job and resume collections.
        """
        try:
            # Check job collection
            job_count = self.job_collection.count_documents({})
            jobs_with_embeddings = self.job_collection.count_documents({"jd_embedding": {"$exists": True, "$ne": None, "$ne": []}})
            
            logger.info(f"Job collection status:")
            logger.info(f"  Total jobs: {job_count}")
            logger.info(f"  Jobs with embeddings: {jobs_with_embeddings}")
            logger.info(f"  Jobs without embeddings: {job_count - jobs_with_embeddings}")
            
            # Check resume collection
            resume_count = self.resume_collection.count_documents({})
            resumes_with_embeddings = self.resume_collection.count_documents({"text_embedding": {"$exists": True, "$ne": None, "$ne": []}})
            
            logger.info(f"Resume collection status:")
            logger.info(f"  Total resumes: {resume_count}")
            logger.info(f"  Resumes with embeddings: {resumes_with_embeddings}")
            logger.info(f"  Resumes without embeddings: {resume_count - resumes_with_embeddings}")
            
        except Exception as e:
            logger.error(f"Error checking collections: {e}")

    def get_sample_job(self) -> Dict[str, Any]:
        """
        Get a sample job document for testing.
        
        Returns:
            Dict[str, Any]: Sample job document
        """
        try:
            # Get first job without embedding
            job = self.job_collection.find_one({"jd_embedding": {"$exists": False}})
            if not job:
                # If all jobs have embeddings, get any job
                job = self.job_collection.find_one()
            
            if not job:
                raise ValueError("No job documents found in collection")
            
            # Debug: Print job structure
            logger.info(f"Selected job for testing: {job.get('job_title', 'Unknown')}")
            logger.info(f"Job document keys: {list(job.keys())}")
            logger.info(f"Job title: {job.get('job_title') or job.get('title')}")
            logger.info(f"Company name: {job.get('company_name') or job.get('company')}")
            logger.info(f"Has job_description_raw: {'job_description_raw' in job}")
            logger.info(f"Has description: {'description' in job}")
            if 'description' in job:
                logger.info(f"Job description length: {len(job.get('description', ''))}")
                logger.info(f"Job description preview: {job.get('description', '')[:200]}...")
            
            return job
            
        except Exception as e:
            logger.error(f"Error getting sample job: {e}")
            raise
    
    def get_sample_resumes(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get sample resume documents for testing.
        
        Args:
            limit (int): Number of resumes to retrieve
            
        Returns:
            List[Dict[str, Any]]: List of resume documents
        """
        try:
            # Get resumes with embeddings
            resumes = list(self.resume_collection.find(
                {"text_embedding": {"$exists": True, "$ne": None, "$ne": []}},
                limit=limit
            ))
            
            if not resumes:
                logger.warning("No resumes with embeddings found")
                return []
            
            logger.info(f"Retrieved {len(resumes)} resumes for testing")
            return resumes
            
        except Exception as e:
            logger.error(f"Error getting sample resumes: {e}")
            return []
    
    def test_job_embedding(self, job_doc: Dict[str, Any]) -> Tuple[bool, List[float]]:
        """
        Test embedding generation for a job document.
        
        Args:
            job_doc (Dict[str, Any]): Job document
            
        Returns:
            Tuple[bool, List[float]]: Success status and embedding vector
        """
        try:
            job_title = job_doc.get("job_title", "unknown")
            logger.info(f"Testing embedding generation for job: {job_title}")
            
            # Extract content for embedding
            content = extract_job_content_from_mongo_doc(job_doc)
            if not content:
                logger.error(f"No content extracted for job: {job_title}")
                return False, []
            
            logger.info(f"Extracted content length: {len(content)} characters")
            logger.info(f"Content preview: {content[:200]}...")
            
            # Generate embedding
            embedding = self.embedding_processor.generate_embedding(
                text=content,
                task_type="RETRIEVAL_QUERY"
            )
            
            if not embedding:
                logger.error(f"Failed to generate embedding for job: {job_title}")
                return False, []
            
            logger.info(f"Successfully generated embedding (dimensions: {len(embedding)})")
            logger.info(f"Embedding preview: {embedding[:5]}...")
            
            return True, embedding
            
        except Exception as e:
            logger.error(f"Error testing job embedding: {e}")
            return False, []
    
    def calculate_similarity(self, job_embedding: List[float], resume_embedding: List[float]) -> float:
        """
        Calculate cosine similarity between job and resume embeddings.
        
        Args:
            job_embedding (List[float]): Job embedding vector
            resume_embedding (List[float]): Resume embedding vector
            
        Returns:
            float: Cosine similarity score (0-1)
        """
        try:
            # Convert to numpy arrays and reshape for sklearn
            job_vec = np.array(job_embedding).reshape(1, -1)
            resume_vec = np.array(resume_embedding).reshape(1, -1)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(job_vec, resume_vec)[0][0]
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0
    
    def test_semantic_search(self, job_embedding: List[float], resumes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Test semantic search by finding most similar resumes to a job.
        
        Args:
            job_embedding (List[float]): Job embedding vector
            resumes (List[Dict[str, Any]]): List of resume documents
            
        Returns:
            List[Dict[str, Any]]: Sorted list of resumes with similarity scores
        """
        try:
            results = []
            
            for resume in resumes:
                resume_embedding = resume.get("text_embedding")
                if not resume_embedding:
                    continue
                
                # Calculate similarity
                similarity = self.calculate_similarity(job_embedding, resume_embedding)
                
                # Get resume info
                file_id = resume.get("file_id", "unknown")
                resume_data = resume.get("resume_data", {})
                basics = resume_data.get("basics", {})
                summary = basics.get("summary", "")[:100] + "..." if basics.get("summary") else "No summary"
                
                results.append({
                    "file_id": file_id,
                    "similarity_score": similarity,
                    "summary_preview": summary,
                    "resume_doc": resume
                })
            
            # Sort by similarity score (highest first)
            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            logger.info(f"Found {len(results)} matching resumes")
            return results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []
    
    def run_comprehensive_test(self):
        """
        Run a comprehensive test of job embedding and semantic search.
        """
        try:
            logger.info("=== Starting Comprehensive Job Embedding and Search Test ===")
            
            # Step 0: Check collections status
            logger.info("\n0. Checking collections status...")
            self.check_collections()
            
            # Step 1: Get sample job
            logger.info("\n1. Getting sample job...")
            job_doc = self.get_sample_job()
            job_title = job_doc.get("job_title") or job_doc.get("title", "Unknown")
            logger.info(f"Selected job: {job_title}")
            
            # Step 2: Test job embedding
            logger.info("\n2. Testing job embedding generation...")
            success, job_embedding = self.test_job_embedding(job_doc)
            
            if not success:
                logger.error("Job embedding test failed. Exiting.")
                return
            
            # Step 3: Get sample resumes
            logger.info("\n3. Getting sample resumes...")
            resumes = self.get_sample_resumes(limit=10)
            
            if not resumes:
                logger.error("No resumes available for testing. Exiting.")
                return
            
            # Step 4: Test semantic search
            logger.info("\n4. Testing semantic search...")
            search_results = self.test_semantic_search(job_embedding, resumes)
            
            # Step 5: Display results
            logger.info("\n5. Search Results:")
            logger.info("=" * 80)
            logger.info(f"Job: {job_title}")
            logger.info("=" * 80)
            
            for i, result in enumerate(search_results[:5], 1):
                logger.info(f"\n{i}. File: {result['file_id']}")
                logger.info(f"   Similarity Score: {result['similarity_score']:.4f}")
                logger.info(f"   Summary: {result['summary_preview']}")
            
            # Step 6: Save test results
            logger.info("\n6. Saving test results...")
            self.save_test_results(job_doc, job_embedding, search_results)
            
            logger.info("\n=== Test Completed Successfully ===")
            
        except Exception as e:
            logger.error(f"Error in comprehensive test: {e}")
    
    def save_test_results(self, job_doc: Dict[str, Any], job_embedding: List[float], search_results: List[Dict[str, Any]]):
        """
        Save test results to a file for analysis.
        
        Args:
            job_doc (Dict[str, Any]): Job document
            job_embedding (List[float]): Job embedding vector
            search_results (List[Dict[str, Any]]): Search results
        """
        try:
            # Create results directory if it doesn't exist
            os.makedirs("test_results", exist_ok=True)
            
            # Prepare results data
            results_data = {
                "test_timestamp": datetime.now().isoformat(),
                "job_info": {
                    "job_title": job_doc.get("job_title") or job_doc.get("title"),
                    "company_name": job_doc.get("company_name") or job_doc.get("company"),
                    "job_id": str(job_doc.get("_id")),
                    "embedding_dimensions": len(job_embedding),
                    "embedding_preview": job_embedding[:10]  # First 10 values
                },
                "search_results": [
                    {
                        "rank": i + 1,
                        "file_id": result["file_id"],
                        "similarity_score": result["similarity_score"],
                        "summary_preview": result["summary_preview"]
                    }
                    for i, result in enumerate(search_results[:10])  # Top 10 results
                ],
                "statistics": {
                    "total_resumes_searched": len(search_results),
                    "average_similarity": np.mean([r["similarity_score"] for r in search_results]),
                    "max_similarity": max([r["similarity_score"] for r in search_results]),
                    "min_similarity": min([r["similarity_score"] for r in search_results])
                }
            }
            
            # Save to JSON file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"test_results/job_embedding_test_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Test results saved to: {filename}")
            
        except Exception as e:
            logger.error(f"Error saving test results: {e}")

def main():
    """Main function to run the test."""
    try:
        logger.info("Starting Job Embedding and Semantic Search Test")
        
        # Initialize tester
        tester = JobEmbeddingAndSearchTester()
        
        # Run comprehensive test
        tester.run_comprehensive_test()
        
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main test: {e}")
        raise

if __name__ == "__main__":
    main() 