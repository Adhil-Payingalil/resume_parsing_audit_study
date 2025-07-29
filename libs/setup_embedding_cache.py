"""
Setup Embedding Cache Collection

This script sets up the MongoDB embedding_cache collection with proper indexes
for efficient caching of embeddings.

Usage:
    python setup_embedding_cache.py

Features:
- Creates embedding_cache collection if it doesn't exist
- Sets up indexes for efficient querying
- Provides statistics about the cache
"""

import os
import sys
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.mongodb import _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

def setup_embedding_cache():
    """
    Set up the embedding_cache collection with proper indexes.
    """
    try:
        # Get MongoDB client
        mongo_client = _get_mongo_client()
        if not mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        db = mongo_client["Resume_study"]
        cache_collection = db["embedding_cache"]
        
        logger.info("Setting up embedding_cache collection...")
        
        # Create indexes for efficient querying
        indexes_created = []
        
        # Index on text_hash for fast lookups
        try:
            cache_collection.create_index("text_hash", unique=True)
            indexes_created.append("text_hash (unique)")
            logger.info("Created unique index on text_hash")
        except Exception as e:
            logger.warning(f"Could not create text_hash index: {e}")
        
        # Index on model_name for filtering by model
        try:
            cache_collection.create_index("model_name")
            indexes_created.append("model_name")
            logger.info("Created index on model_name")
        except Exception as e:
            logger.warning(f"Could not create model_name index: {e}")
        
        # Index on task_type for filtering by task type
        try:
            cache_collection.create_index("task_type")
            indexes_created.append("task_type")
            logger.info("Created index on task_type")
        except Exception as e:
            logger.warning(f"Could not create task_type index: {e}")
        
        # Index on created_at for time-based queries
        try:
            cache_collection.create_index("created_at")
            indexes_created.append("created_at")
            logger.info("Created index on created_at")
        except Exception as e:
            logger.warning(f"Could not create created_at index: {e}")
        
        # Compound index for common query patterns
        try:
            cache_collection.create_index([("model_name", 1), ("task_type", 1)])
            indexes_created.append("model_name + task_type")
            logger.info("Created compound index on model_name + task_type")
        except Exception as e:
            logger.warning(f"Could not create compound index: {e}")
        
        logger.info(f"Successfully created {len(indexes_created)} indexes: {', '.join(indexes_created)}")
        
        # Get collection statistics
        stats = get_cache_statistics(cache_collection)
        logger.info(f"Cache collection statistics: {stats}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error setting up embedding cache: {e}")
        return False

def get_cache_statistics(cache_collection):
    """
    Get statistics about the embedding cache collection.
    
    Args:
        cache_collection: MongoDB collection object
        
    Returns:
        dict: Statistics about the cache
    """
    try:
        total_docs = cache_collection.count_documents({})
        
        # Count by model
        model_stats = {}
        for doc in cache_collection.aggregate([
            {"$group": {"_id": "$model_name", "count": {"$sum": 1}}}
        ]):
            model_stats[doc["_id"]] = doc["count"]
        
        # Count by task type
        task_stats = {}
        for doc in cache_collection.aggregate([
            {"$group": {"_id": "$task_type", "count": {"$sum": 1}}}
        ]):
            task_stats[doc["_id"]] = doc["count"]
        
        # Get oldest and newest entries
        oldest_doc = cache_collection.find_one({}, sort=[("created_at", 1)])
        newest_doc = cache_collection.find_one({}, sort=[("created_at", -1)])
        
        stats = {
            "total_entries": total_docs,
            "models": model_stats,
            "task_types": task_stats,
            "oldest_entry": oldest_doc["created_at"] if oldest_doc else None,
            "newest_entry": newest_doc["created_at"] if newest_doc else None
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting cache statistics: {e}")
        return {}

def cleanup_old_cache_entries(days_old: int = 30):
    """
    Clean up old cache entries to manage storage.
    
    Args:
        days_old (int): Remove entries older than this many days
    """
    try:
        mongo_client = _get_mongo_client()
        if not mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        db = mongo_client["Resume_study"]
        cache_collection = db["embedding_cache"]
        
        # Calculate cutoff date
        cutoff_date = datetime.now() - datetime.timedelta(days=days_old)
        
        # Delete old entries
        result = cache_collection.delete_many({"created_at": {"$lt": cutoff_date}})
        
        logger.info(f"Cleaned up {result.deleted_count} cache entries older than {days_old} days")
        
        return result.deleted_count
        
    except Exception as e:
        logger.error(f"Error cleaning up old cache entries: {e}")
        return 0

def main():
    """Main function to set up the embedding cache."""
    try:
        logger.info("Starting embedding cache setup...")
        
        # Set up the cache collection
        success = setup_embedding_cache()
        
        if success:
            logger.info("Embedding cache setup completed successfully")
            
            # Optionally clean up old entries
            # cleanup_old_cache_entries(days_old=30)
        else:
            logger.error("Embedding cache setup failed")
            
    except Exception as e:
        logger.error(f"Error in main process: {e}")
        raise

if __name__ == "__main__":
    main() 