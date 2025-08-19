"""
Batch Resume Embedding Script

This script processes all existing resumes in the Standardized_resume_data collection
and adds vector embeddings to each document for semantic search capabilities.

Usage:
    python batch_resume_embedding.py

Features:
- Processes all resumes in Standardized_resume_data collection
- Extracts key content for embedding generation
- Generates embeddings using Gemini API with caching
- Updates MongoDB documents with text_embedding field
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
from libs.text_extraction import extract_resume_content_from_mongo_doc
from utils import get_logger

logger = get_logger(__name__)

class BatchResumeEmbeddingProcessor:
    """
    Processes resumes in batch to generate and store embeddings.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        self.db_name = db_name
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.resume_collection = self.db["Standardized_resume_data"]
        
        # Initialize Gemini processor for embeddings
        self.embedding_processor = GeminiProcessor(
            model_name="gemini-1.5-flash",  # Model doesn't matter for embeddings
            temperature=0.0,  # Not used for embeddings
            enable_google_search=False
        )
        
        logger.info(f"BatchResumeEmbeddingProcessor initialized for database: {db_name}")
    
    def get_resumes_without_embeddings(self) -> List[Dict[str, Any]]:
        """
        Get all resumes that don't have embeddings yet.
        
        Returns:
            List[Dict[str, Any]]: List of resume documents without embeddings
        """
        try:
            # Find documents that don't have text_embedding field or have empty embedding
            query = {
                "$or": [
                    {"text_embedding": {"$exists": False}},
                    {"text_embedding": None},
                    {"text_embedding": []}
                ]
            }
            
            resumes = list(self.resume_collection.find(query))
            logger.info(f"Found {len(resumes)} resumes without embeddings")
            return resumes
            
        except Exception as e:
            logger.error(f"Error retrieving resumes without embeddings: {e}")
            return []
    
    def process_resume_embedding(self, resume_doc: Dict[str, Any]) -> bool:
        """
        Process a single resume document to generate and store embedding.
        
        Args:
            resume_doc (Dict[str, Any]): Resume document from MongoDB
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_id = resume_doc.get("file_id", "unknown")
            logger.info(f"Processing resume: {file_id}")
            
            # Extract content for embedding
            content = extract_resume_content_from_mongo_doc(resume_doc)
            if not content:
                logger.warning(f"No content extracted for resume: {file_id}")
                return False
            
            # Generate embedding
            embedding = self.embedding_processor.generate_embedding(
                text=content,
                task_type="RETRIEVAL_DOCUMENT"
            )
            
            if not embedding:
                logger.error(f"Failed to generate embedding for resume: {file_id}")
                return False
            
            # Update document with embedding
            result = self.resume_collection.update_one(
                {"_id": resume_doc["_id"]},
                {
                    "$set": {
                        "text_embedding": embedding,
                        "embedding_generated_at": datetime.now(),
                        "embedding_model": "embedding-001",
                        "embedding_task_type": "RETRIEVAL_DOCUMENT"
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"Successfully updated resume {file_id} with embedding (dimensions: {len(embedding)})")
                return True
            else:
                logger.warning(f"No document updated for resume: {file_id}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing resume {resume_doc.get('file_id', 'unknown')}: {e}")
            return False
    
    def process_all_resumes(self, batch_size: int = 10, delay_seconds: float = 1.0):
        """
        Process all resumes without embeddings in batches.
        
        Args:
            batch_size (int): Number of resumes to process in each batch
            delay_seconds (float): Delay between batches to avoid rate limiting
        """
        try:
            # Get all resumes without embeddings
            resumes = self.get_resumes_without_embeddings()
            
            if not resumes:
                logger.info("No resumes found without embeddings")
                return
            
            total_resumes = len(resumes)
            successful = 0
            failed = 0
            
            logger.info(f"Starting batch processing of {total_resumes} resumes")
            
            # Process in batches
            for i in range(0, total_resumes, batch_size):
                batch = resumes[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (total_resumes + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} resumes)")
                
                # Process each resume in the batch
                for resume in batch:
                    if self.process_resume_embedding(resume):
                        successful += 1
                    else:
                        failed += 1
                    
                    # Small delay between individual resumes
                    time.sleep(0.5)
                
                # Delay between batches
                if i + batch_size < total_resumes:
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
            total_docs = self.resume_collection.count_documents({})
            docs_with_embeddings = self.resume_collection.count_documents({"text_embedding": {"$exists": True, "$ne": None, "$ne": []}})
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
    """Main function to run the batch resume embedding process."""
    try:
        logger.info("Starting batch resume embedding process")
        
        # Initialize processor
        processor = BatchResumeEmbeddingProcessor()
        
        # Get initial statistics
        initial_stats = processor.get_embedding_statistics()
        logger.info(f"Initial statistics: {initial_stats}")
        
        # Process all resumes
        processor.process_all_resumes(batch_size=5, delay_seconds=2.0)
        
        # Get final statistics
        final_stats = processor.get_embedding_statistics()
        logger.info(f"Final statistics: {final_stats}")
        
        logger.info("Batch resume embedding process completed successfully")
        
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise

if __name__ == "__main__":
    main() 