"""
Setup MongoDB Vector Search Index

This script creates the necessary vector search index for optimal performance.
"""

import os
import sys
from pymongo import MongoClient
from dotenv import load_dotenv

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

def setup_vector_search_index():
    """Set up vector search index for the resume collection."""
    try:
        # Connect to MongoDB
        mongo_client = _get_mongo_client()
        if not mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        db = mongo_client["Resume_study"]
        resume_collection = db["Standardized_resume_data"]
        
        logger.info("Setting up vector search index...")
        
        # Check if index already exists
        existing_indexes = list(resume_collection.list_indexes())
        vector_index_exists = any(
            index.get('name') == 'resume_vector_search' 
            for index in existing_indexes
        )
        
        if vector_index_exists:
            logger.info("Vector search index already exists!")
            return True
        
        # Create vector search index
        index_definition = {
            "text_embedding": "vector"
        }
        
        index_options = {
            "name": "resume_vector_search",
            "vectorSize": 3072,  # For gemini-embedding-001
            "vectorSearchOptions": {
                "type": "cosine"
            }
        }
        
        logger.info("Creating vector search index...")
        logger.info(f"Index definition: {index_definition}")
        logger.info(f"Index options: {index_options}")
        
        # Create the index
        resume_collection.create_index(index_definition, **index_options)
        
        logger.info("✅ Vector search index created successfully!")
        logger.info("The optimized workflow will now use MongoDB's native vector search for better performance.")
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting up vector search index: {e}")
        return False

def check_index_status():
    """Check the status of all indexes on the resume collection."""
    try:
        mongo_client = _get_mongo_client()
        if not mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        db = mongo_client["Resume_study"]
        resume_collection = db["Standardized_resume_data"]
        
        logger.info("Checking index status...")
        
        indexes = list(resume_collection.list_indexes())
        
        logger.info(f"Found {len(indexes)} indexes:")
        for i, index in enumerate(indexes):
            logger.info(f"  {i+1}. {index.get('name', 'unnamed')}")
            if 'vectorSearchOptions' in index:
                logger.info(f"     Type: Vector Search ({index['vectorSearchOptions']['type']})")
                logger.info(f"     Vector Size: {index.get('vectorSize', 'unknown')}")
        
        # Check for vector search index specifically
        vector_index_exists = any(
            index.get('name') == 'resume_vector_search' 
            for index in indexes
        )
        
        if vector_index_exists:
            logger.info("✅ Vector search index is ready!")
        else:
            logger.info("❌ Vector search index not found. Run setup_vector_search_index() to create it.")
        
        return vector_index_exists
        
    except Exception as e:
        logger.error(f"Error checking index status: {e}")
        return False

def main():
    """Main function to set up vector search."""
    logger.info("MongoDB Vector Search Setup")
    logger.info("=" * 40)
    
    # Check current status
    logger.info("1. Checking current index status...")
    current_status = check_index_status()
    
    if not current_status:
        logger.info("\n2. Setting up vector search index...")
        success = setup_vector_search_index()
        
        if success:
            logger.info("\n3. Verifying setup...")
            check_index_status()
        else:
            logger.error("Failed to set up vector search index")
            return 1
    else:
        logger.info("Vector search index is already set up!")
    
    logger.info("\nSetup complete!")
    return 0

if __name__ == "__main__":
    exit(main()) 