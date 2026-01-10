"""
Embedding Verification Script

This script verifies that embeddings are created correctly in the Job_postings_greenhouse collection.
It checks embedding dimensions, quality, and provides statistics.

Usage:
    python verify_embeddings.py
"""

import os
import sys
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from utils import get_logger

logger = get_logger(__name__)

class EmbeddingVerifier:
    """
    Verifies embedding quality and provides statistics.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        self.db_name = db_name
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.job_collection = self.db["Job_postings_greenhouse"]
        
        logger.info(f"EmbeddingVerifier initialized for database: {db_name}")
    
    def get_embedding_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about embeddings in the collection.
        
        Returns:
            Dict[str, Any]: Statistics about embeddings
        """
        try:
            # Total documents with jd_extraction=True
            total_docs = self.job_collection.count_documents({"jd_extraction": True})
            
            # Documents with embeddings
            docs_with_embeddings = self.job_collection.count_documents({
                "jd_extraction": True,
                "jd_embedding": {"$exists": True, "$ne": None, "$ne": []}
            })
            
            # Documents without embeddings
            docs_without_embeddings = total_docs - docs_with_embeddings
            
            # Get sample of documents with embeddings for analysis
            sample_docs = list(self.job_collection.find({
                "jd_extraction": True,
                "jd_embedding": {"$exists": True, "$ne": None, "$ne": []}
            }).limit(10))
            
            # Analyze embedding dimensions and quality
            embedding_analysis = self._analyze_embeddings(sample_docs)
            
            stats = {
                "total_documents_with_extraction": total_docs,
                "documents_with_embeddings": docs_with_embeddings,
                "documents_without_embeddings": docs_without_embeddings,
                "embedding_coverage_percentage": (docs_with_embeddings / total_docs * 100) if total_docs > 0 else 0,
                "embedding_analysis": embedding_analysis
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting embedding statistics: {e}")
            return {}
    
    def _analyze_embeddings(self, sample_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze embedding quality from sample documents.
        
        Args:
            sample_docs (List[Dict[str, Any]]): Sample documents with embeddings
            
        Returns:
            Dict[str, Any]: Analysis results
        """
        if not sample_docs:
            return {"error": "No sample documents available"}
        
        try:
            embeddings = []
            dimensions = []
            models = []
            task_types = []
            generation_dates = []
            
            for doc in sample_docs:
                embedding = doc.get("jd_embedding", [])
                if embedding and isinstance(embedding, list) and len(embedding) > 0:
                    embeddings.append(embedding)
                    dimensions.append(len(embedding))
                    models.append(doc.get("embedding_model", "unknown"))
                    task_types.append(doc.get("embedding_task_type", "unknown"))
                    generation_dates.append(doc.get("embedding_generated_at"))
            
            if not embeddings:
                return {"error": "No valid embeddings found in sample"}
            
            # Convert to numpy array for analysis
            embeddings_array = np.array(embeddings)
            
            analysis = {
                "sample_size": len(embeddings),
                "embedding_dimensions": {
                    "expected": 768,  # Gemini embedding-001 dimension
                    "actual": dimensions[0] if dimensions else 0,
                    "consistent": len(set(dimensions)) == 1,
                    "all_dimensions": dimensions
                },
                "embedding_models": list(set(models)),
                "task_types": list(set(task_types)),
                "embedding_quality": {
                    "mean_magnitude": float(np.mean(np.linalg.norm(embeddings_array, axis=1))),
                    "std_magnitude": float(np.std(np.linalg.norm(embeddings_array, axis=1))),
                    "min_magnitude": float(np.min(np.linalg.norm(embeddings_array, axis=1))),
                    "max_magnitude": float(np.max(np.linalg.norm(embeddings_array, axis=1)))
                },
                "generation_dates": {
                    "earliest": min(generation_dates) if generation_dates else None,
                    "latest": max(generation_dates) if generation_dates else None,
                    "count": len([d for d in generation_dates if d])
                }
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing embeddings: {e}")
            return {"error": str(e)}
    
    def verify_embedding_consistency(self) -> Dict[str, Any]:
        """
        Verify that all embeddings are consistent and properly formatted.
        
        Returns:
            Dict[str, Any]: Consistency check results
        """
        try:
            # Get all documents with embeddings
            docs_with_embeddings = list(self.job_collection.find({
                "jd_extraction": True,
                "jd_embedding": {"$exists": True, "$ne": None, "$ne": []}
            }))
            
            if not docs_with_embeddings:
                return {"error": "No documents with embeddings found"}
            
            issues = []
            dimensions = []
            models = []
            
            for doc in docs_with_embeddings:
                doc_id = str(doc.get("_id", "unknown"))
                embedding = doc.get("jd_embedding", [])
                
                # Check if embedding is a list
                if not isinstance(embedding, list):
                    issues.append(f"Document {doc_id}: embedding is not a list")
                    continue
                
                # Check if embedding is empty
                if len(embedding) == 0:
                    issues.append(f"Document {doc_id}: embedding is empty")
                    continue
                
                # Check if embedding contains only numbers
                try:
                    float_embedding = [float(x) for x in embedding]
                    dimensions.append(len(float_embedding))
                    models.append(doc.get("embedding_model", "unknown"))
                except (ValueError, TypeError):
                    issues.append(f"Document {doc_id}: embedding contains non-numeric values")
            
            # Check dimension consistency
            unique_dimensions = set(dimensions)
            if len(unique_dimensions) > 1:
                issues.append(f"Inconsistent embedding dimensions: {unique_dimensions}")
            
            # Check model consistency
            unique_models = set(models)
            if len(unique_models) > 1:
                issues.append(f"Inconsistent embedding models: {unique_models}")
            
            return {
                "total_documents_checked": len(docs_with_embeddings),
                "issues_found": len(issues),
                "issues": issues,
                "dimension_consistency": len(unique_dimensions) == 1,
                "model_consistency": len(unique_models) == 1,
                "common_dimension": list(unique_dimensions)[0] if unique_dimensions else None,
                "common_model": list(unique_models)[0] if unique_models else None
            }
            
        except Exception as e:
            logger.error(f"Error verifying embedding consistency: {e}")
            return {"error": str(e)}
    
    def test_embedding_similarity(self, num_samples: int = 5) -> Dict[str, Any]:
        """
        Test embedding similarity to verify they're working correctly.
        
        Args:
            num_samples (int): Number of sample embeddings to test
            
        Returns:
            Dict[str, Any]: Similarity test results
        """
        try:
            # Get sample documents
            sample_docs = list(self.job_collection.find({
                "jd_extraction": True,
                "jd_embedding": {"$exists": True, "$ne": None, "$ne": []}
            }).limit(num_samples))
            
            if len(sample_docs) < 2:
                return {"error": "Need at least 2 documents with embeddings for similarity test"}
            
            embeddings = []
            titles = []
            
            for doc in sample_docs:
                embedding = doc.get("jd_embedding", [])
                if embedding and isinstance(embedding, list) and len(embedding) > 0:
                    embeddings.append(np.array(embedding))
                    titles.append(doc.get("title", "Unknown"))
            
            if len(embeddings) < 2:
                return {"error": "Not enough valid embeddings for similarity test"}
            
            # Calculate cosine similarities
            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    # Calculate cosine similarity
                    dot_product = np.dot(embeddings[i], embeddings[j])
                    norm_i = np.linalg.norm(embeddings[i])
                    norm_j = np.linalg.norm(embeddings[j])
                    
                    if norm_i > 0 and norm_j > 0:
                        similarity = dot_product / (norm_i * norm_j)
                        similarities.append({
                            "doc1": titles[i],
                            "doc2": titles[j],
                            "similarity": float(similarity)
                        })
            
            return {
                "similarity_tests": len(similarities),
                "average_similarity": float(np.mean([s["similarity"] for s in similarities])),
                "min_similarity": float(np.min([s["similarity"] for s in similarities])),
                "max_similarity": float(np.max([s["similarity"] for s in similarities])),
                "similarities": similarities
            }
            
        except Exception as e:
            logger.error(f"Error testing embedding similarity: {e}")
            return {"error": str(e)}

def main():
    """Main function to run embedding verification."""
    try:
        logger.info("Starting embedding verification")
        
        # Initialize verifier
        verifier = EmbeddingVerifier()
        
        # Get basic statistics
        logger.info("Getting embedding statistics...")
        stats = verifier.get_embedding_statistics()
        
        print("\n" + "="*60)
        print("EMBEDDING STATISTICS")
        print("="*60)
        print(f"Total documents with jd_extraction=True: {stats.get('total_documents_with_extraction', 0)}")
        print(f"Documents with embeddings: {stats.get('documents_with_embeddings', 0)}")
        print(f"Documents without embeddings: {stats.get('documents_without_embeddings', 0)}")
        print(f"Coverage percentage: {stats.get('embedding_coverage_percentage', 0):.1f}%")
        
        # Show embedding analysis
        analysis = stats.get('embedding_analysis', {})
        if 'error' not in analysis:
            print(f"\nEmbedding Analysis:")
            print(f"  Sample size: {analysis.get('sample_size', 0)}")
            print(f"  Expected dimensions: {analysis.get('embedding_dimensions', {}).get('expected', 'unknown')}")
            print(f"  Actual dimensions: {analysis.get('embedding_dimensions', {}).get('actual', 'unknown')}")
            print(f"  Dimensions consistent: {analysis.get('embedding_dimensions', {}).get('consistent', False)}")
            print(f"  Models used: {analysis.get('embedding_models', [])}")
            print(f"  Task types: {analysis.get('task_types', [])}")
            
            quality = analysis.get('embedding_quality', {})
            print(f"  Mean magnitude: {quality.get('mean_magnitude', 0):.4f}")
            print(f"  Std magnitude: {quality.get('std_magnitude', 0):.4f}")
        else:
            print(f"\nEmbedding Analysis Error: {analysis.get('error', 'Unknown error')}")
        
        # Check consistency
        logger.info("Checking embedding consistency...")
        consistency = verifier.verify_embedding_consistency()
        
        print(f"\nConsistency Check:")
        print(f"  Documents checked: {consistency.get('total_documents_checked', 0)}")
        print(f"  Issues found: {consistency.get('issues_found', 0)}")
        print(f"  Dimension consistent: {consistency.get('dimension_consistency', False)}")
        print(f"  Model consistent: {consistency.get('model_consistency', False)}")
        print(f"  Common dimension: {consistency.get('common_dimension', 'unknown')}")
        print(f"  Common model: {consistency.get('common_model', 'unknown')}")
        
        if consistency.get('issues', []):
            print(f"  Issues:")
            for issue in consistency['issues']:
                print(f"    - {issue}")
        
        # Test similarity
        logger.info("Testing embedding similarity...")
        similarity = verifier.test_embedding_similarity(num_samples=5)
        
        if 'error' not in similarity:
            print(f"\nSimilarity Test:")
            print(f"  Tests performed: {similarity.get('similarity_tests', 0)}")
            print(f"  Average similarity: {similarity.get('average_similarity', 0):.4f}")
            print(f"  Min similarity: {similarity.get('min_similarity', 0):.4f}")
            print(f"  Max similarity: {similarity.get('max_similarity', 0):.4f}")
        else:
            print(f"\nSimilarity Test Error: {similarity.get('error', 'Unknown error')}")
        
        print("="*60)
        logger.info("Embedding verification completed")
        
    except Exception as e:
        logger.error(f"Error in verification: {e}")
        raise

if __name__ == "__main__":
    main()
