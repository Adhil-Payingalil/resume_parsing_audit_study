"""
Optimized Resume-to-Job Matching Engine with MongoDB Vector Search

This module provides an optimized workflow for matching resumes to job postings
using MongoDB's native vector search capabilities for better performance.
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from bson import ObjectId
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from libs.gemini_processor import GeminiProcessor
from utils import get_logger

logger = get_logger(__name__)

class OptimizedResumeJobMatcher:
    """
    Optimized ResumeJobMatcher using MongoDB Vector Search for better performance.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        """
        Initialize the OptimizedResumeJobMatcher.
        
        Args:
            db_name (str): MongoDB database name
        """
        self.db_name = db_name
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[db_name]
        self.job_collection = self.db["job_postings"]
        self.resume_collection = self.db["Standardized_resume_data"]
        self.matches_collection = self.db["resume_job_matches"]
        self.unmatched_collection = self.db["unmatched_job_postings"]
        
        # Initialize Gemini processor for LLM validation
        self.gemini_processor = GeminiProcessor(
            model_name="gemini-1.5-flash",
            temperature=0.1,  # Low temperature for consistent validation
            enable_google_search=False
        )
        
        # Create indexes for performance
        self._create_indexes()
        
        logger.info(f"OptimizedResumeJobMatcher initialized for database: {db_name}")
    
    def _create_indexes(self):
        """Create necessary indexes for the collections."""
        try:
            # Indexes for matches collection
            self.matches_collection.create_index([("job_posting_id", 1)])
            self.matches_collection.create_index([("resume_id", 1)])
            self.matches_collection.create_index([("match_status", 1)])
            self.matches_collection.create_index([("created_at", -1)])
            
            # Indexes for unmatched collection
            self.unmatched_collection.create_index([("job_posting_id", 1)])
            self.unmatched_collection.create_index([("job_url_direct", 1)])
            self.unmatched_collection.create_index([("created_at", -1)])
            
            # Check if vector search index exists
            self._check_vector_search_index()
            
            logger.info("Database indexes created successfully")
            
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")
    
    def _check_vector_search_index(self):
        """Check if vector search index exists and create if needed."""
        try:
            # Check if vector search index exists
            indexes = list(self.resume_collection.list_indexes())
            vector_index_exists = any(
                index.get('name') == 'resume_vector_search' 
                for index in indexes
            )
            
            if not vector_index_exists:
                logger.warning("Vector search index not found. Using fallback brute force search.")
                logger.info("To enable vector search, create an index on the resume collection:")
                logger.info("db.Standardized_resume_data.createIndex({")
                logger.info("  'text_embedding': 'vector'")
                logger.info("}, {")
                logger.info("  'name': 'resume_vector_search',")
                logger.info("  'vectorSize': 3072,")
                logger.info("  'vectorSearchOptions': {")
                logger.info("    'type': 'cosine'")
                logger.info("  }")
                logger.info("})")
            else:
                logger.info("Vector search index found - using optimized search")
                
        except Exception as e:
            logger.error(f"Error checking vector search index: {e}")
    
    def get_pending_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get jobs that haven't been processed for matching yet.
        
        Args:
            limit (int): Maximum number of jobs to return
            
        Returns:
            List[Dict[str, Any]]: List of job documents
        """
        try:
            # Get jobs that don't have any matches yet
            pipeline = [
                {
                    "$lookup": {
                        "from": "resume_job_matches",
                        "localField": "_id",
                        "foreignField": "job_posting_id",
                        "as": "matches"
                    }
                },
                {
                    "$match": {
                        "matches": {"$size": 0},
                        "jd_embedding": {"$exists": True, "$ne": None}
                    }
                },
                {"$limit": limit}
            ]
            
            pending_jobs = list(self.job_collection.aggregate(pipeline))
            logger.info(f"Found {len(pending_jobs)} pending jobs for matching")
            return pending_jobs
            
        except Exception as e:
            logger.error(f"Error getting pending jobs: {e}")
            return []
    
    def vector_search_resumes_optimized(self, job_doc: Dict[str, Any], top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Perform optimized vector search using MongoDB's vector search capabilities.
        
        Args:
            job_doc (Dict[str, Any]): Job document with embedding
            top_k (int): Number of top resumes to return
            
        Returns:
            List[Dict[str, Any]]: List of resume documents with similarity scores
        """
        try:
            job_embedding = job_doc.get("jd_embedding")
            if not job_embedding:
                logger.warning(f"Job {job_doc.get('_id')} has no embedding")
                return []
            
            # Try vector search first (if index exists)
            try:
                pipeline = [
                    {
                        "$vectorSearch": {
                            "queryVector": job_embedding,
                            "path": "text_embedding",
                            "numCandidates": top_k * 10,  # Get more candidates for better results
                            "limit": top_k,
                            "index": "resume_vector_search"
                        }
                    },
                    {
                        "$addFields": {
                            "similarity_score": {"$meta": "vectorSearchScore"}
                        }
                    }
                ]
                
                top_resumes = list(self.resume_collection.aggregate(pipeline))
                
                if top_resumes:
                    logger.info(f"Vector search found {len(top_resumes)} top resumes for job {job_doc.get('_id')}")
                    return top_resumes
                    
            except Exception as e:
                logger.warning(f"Vector search failed, falling back to brute force: {e}")
            
            # Fallback to brute force search
            return self._brute_force_vector_search(job_doc, top_k)
            
        except Exception as e:
            logger.error(f"Error in optimized vector search: {e}")
            return []
    
    def _brute_force_vector_search(self, job_doc: Dict[str, Any], top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Fallback brute force vector search.
        
        Args:
            job_doc (Dict[str, Any]): Job document with embedding
            top_k (int): Number of top resumes to return
            
        Returns:
            List[Dict[str, Any]]: List of resume documents with similarity scores
        """
        try:
            job_embedding = job_doc.get("jd_embedding")
            
            # Get all resumes with embeddings
            resumes = list(self.resume_collection.find(
                {"text_embedding": {"$exists": True, "$ne": None}}
            ))
            
            if not resumes:
                logger.warning("No resumes with embeddings found")
                return []
            
            # Calculate similarities
            similarities = []
            for resume in resumes:
                resume_embedding = resume.get("text_embedding")
                if resume_embedding:
                    similarity = self._calculate_cosine_similarity(
                        job_embedding, resume_embedding
                    )
                    similarities.append((similarity, resume))
            
            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x[0], reverse=True)
            top_resumes = []
            
            for similarity, resume in similarities[:top_k]:
                resume_with_score = resume.copy()
                resume_with_score["similarity_score"] = similarity
                top_resumes.append(resume_with_score)
            
            logger.info(f"Brute force search found {len(top_resumes)} top resumes for job {job_doc.get('_id')}")
            return top_resumes
            
        except Exception as e:
            logger.error(f"Error in brute force vector search: {e}")
            return []
    
    def _calculate_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1 (List[float]): First vector
            vec2 (List[float]): Second vector
            
        Returns:
            float: Cosine similarity score
        """
        try:
            # Convert to numpy arrays and reshape for sklearn
            vec1_array = np.array(vec1).reshape(1, -1)
            vec2_array = np.array(vec2).reshape(1, -1)
            
            # Calculate cosine similarity
            similarity = cosine_similarity(vec1_array, vec2_array)[0][0]
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def llm_validate_match(self, job_doc: Dict[str, Any], resume_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to validate the quality of a job-resume match.
        
        Args:
            job_doc (Dict[str, Any]): Job document
            resume_doc (Dict[str, Any]): Resume document
            
        Returns:
            Dict[str, Any]: Validation result with score and reasoning
        """
        try:
            # Create validation prompt
            prompt = self._create_validation_prompt(job_doc, resume_doc)
            
            # Get LLM response
            response = self.gemini_processor.generate_content(prompt)
            
            # Parse response
            validation_result = self._parse_validation_response(response.text)
            
            # Add similarity score
            validation_result["similarity_score"] = resume_doc.get("similarity_score", 0.0)
            
            logger.info(f"LLM validation completed for job {job_doc.get('_id')} and resume {resume_doc.get('_id')}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")
            return {
                "llm_score": 0.0,
                "llm_reasoning": f"Error during validation: {str(e)}",
                "is_valid": False,
                "similarity_score": resume_doc.get("similarity_score", 0.0)
            }
    
    def _create_validation_prompt(self, job_doc: Dict[str, Any], resume_doc: Dict[str, Any]) -> str:
        """
        Create the prompt for LLM validation.
        
        Args:
            job_doc (Dict[str, Any]): Job document
            resume_doc (Dict[str, Any]): Resume document
            
        Returns:
            str: Formatted prompt for LLM
        """
        # Extract key information
        job_title = job_doc.get("job_title", "Unknown")
        company_name = job_doc.get("company_name", "Unknown")
        job_description = job_doc.get("job_description_raw", "")[:1500]  # Limit length
        
        resume_data = resume_doc.get("resume_data", {})
        key_metrics = resume_doc.get("key_metrics", {})
        
        # Extract resume details
        skills = resume_data.get("skills", [])
        work_experience = resume_data.get("work_experience", [])
        education = resume_data.get("education", [])
        
        experience_level = key_metrics.get("experience_level", "Unknown")
        primary_industry = key_metrics.get("primary_industry_sector", "Unknown")
        
        prompt = f"""
You are an expert technical recruiter evaluating the match between a job posting and a resume.

JOB DETAILS:
Title: {job_title}
Company: {company_name}
Description: {job_description}

RESUME DETAILS:
Experience Level: {experience_level}
Primary Industry: {primary_industry}
Skills: {json.dumps(skills, indent=2)}
Work Experience: {json.dumps(work_experience, indent=2)}
Education: {json.dumps(education, indent=2)}

TASK: Evaluate this match and provide a score from 0-100, where:
- 90-100: Excellent match, highly qualified candidate
- 70-89: Good match, well-qualified candidate  
- 50-69: Fair match, some qualifications but gaps exist
- 30-49: Poor match, significant gaps
- 0-29: Very poor match, not suitable

Return ONLY a valid JSON object with these fields:
{{
    "llm_score": <number between 0-100>,
    "llm_reasoning": "<detailed explanation of the match quality>",
    "is_valid": <true if score >= 70, false otherwise>
}}

Do not include any other text or formatting.
"""
        return prompt
    
    def _parse_validation_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse the LLM validation response.
        
        Args:
            response_text (str): Raw LLM response
            
        Returns:
            Dict[str, Any]: Parsed validation result
        """
        try:
            # Clean the response
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            result = json.loads(cleaned_text)
            
            # Validate required fields
            required_fields = ["llm_score", "llm_reasoning", "is_valid"]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return {
                "llm_score": 0.0,
                "llm_reasoning": f"Error parsing response: {str(e)}",
                "is_valid": False
            }
    
    def store_validated_match(self, job_doc: Dict[str, Any], resume_doc: Dict[str, Any], match_result: Dict[str, Any]):
        """
        Store a validated match in the database.
        
        Args:
            job_doc (Dict[str, Any]): Job document
            resume_doc (Dict[str, Any]): Resume document
            match_result (Dict[str, Any]): Match validation result
        """
        try:
            match_doc = {
                # References
                "job_posting_id": job_doc["_id"],
                "resume_id": resume_doc["_id"],
                
                # Key job details
                "job_url_direct": job_doc.get("job_url_direct"),
                "job_title": job_doc.get("job_title"),
                "company_name": job_doc.get("company_name"),
                "job_description_raw": job_doc.get("job_description_raw"),
                
                # Key resume details
                "file_id": resume_doc.get("file_id"),
                "resume_data": resume_doc.get("resume_data"),
                "key_metrics": resume_doc.get("key_metrics"),
                
                # Matching metrics
                "semantic_similarity": match_result["similarity_score"],
                "match_score": match_result["llm_score"],
                "match_reasoning": match_result["llm_reasoning"],
                
                # Status
                "match_status": "VALIDATED",
                "created_at": datetime.now(),
                "validated_at": datetime.now()
            }
            
            self.matches_collection.insert_one(match_doc)
            logger.info(f"Stored validated match for job {job_doc.get('_id')} and resume {resume_doc.get('_id')}")
            
        except Exception as e:
            logger.error(f"Error storing validated match: {e}")
    
    def store_unmatched_job(self, job_doc: Dict[str, Any], top_resumes: List[Dict[str, Any]], top_similarity_score: float):
        """
        Store a job that couldn't be matched with any resume.
        
        Args:
            job_doc (Dict[str, Any]): Job document
            top_resumes (List[Dict[str, Any]]): Top resumes that were evaluated
            top_similarity_score (float): Best similarity score found
        """
        try:
            # Extract file IDs from top resumes
            top_resume_file_ids = [
                {
                    "file_id": resume.get("file_id", "Unknown"),
                    "similarity_score": resume.get("similarity_score", 0.0),
                    "llm_score": resume.get("llm_score", 0.0) if "llm_score" in resume else None
                }
                for resume in top_resumes
            ]
            
            unmatched_doc = {
                # Reference
                "job_posting_id": job_doc["_id"],
                
                # Key job details
                "job_url_direct": job_doc.get("job_url_direct"),
                "job_title": job_doc.get("job_title"),
                "company_name": job_doc.get("company_name"),
                "job_description_raw": job_doc.get("job_description_raw"),
                
                # Rejection info
                "rejection_reason": "No suitable matches found",
                "top_similarity_score": top_similarity_score,
                "top_resumes_evaluated": top_resume_file_ids,
                
                # Timestamps
                "created_at": datetime.now(),
                "scraped_at": job_doc.get("scraped_at")
            }
            
            self.unmatched_collection.insert_one(unmatched_doc)
            logger.info(f"Stored unmatched job {job_doc.get('_id')} with {len(top_resume_file_ids)} evaluated resumes")
            
        except Exception as e:
            logger.error(f"Error storing unmatched job: {e}")
    
    def process_job_matching(self, job_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process matching for a single job posting with detailed output.
        
        Args:
            job_doc (Dict[str, Any]): Job document to process
            
        Returns:
            Dict[str, Any]: Processing result summary with detailed match info
        """
        try:
            job_id = job_doc.get('_id')
            job_title = job_doc.get('job_title', 'Unknown')
            company_name = job_doc.get('company_name', 'Unknown')
            
            logger.info(f"Processing job matching for job {job_id}: {job_title} at {company_name}")
            
            # Stage 1: Vector search for top resumes
            top_resumes = self.vector_search_resumes_optimized(job_doc, top_k=4)
            
            if not top_resumes:
                logger.warning(f"No resumes found for job {job_id}")
                self.store_unmatched_job(job_doc, [], 0.0)
                return {
                    "status": "no_resumes_found", 
                    "matches_created": 0,
                    "top_resumes": [],
                    "job_details": {"id": str(job_id), "title": job_title, "company": company_name}
                }
            
            # Stage 2: LLM validation of each match
            validated_matches = []
            top_similarity_score = 0.0
            detailed_results = []
            
            for i, resume in enumerate(top_resumes):
                similarity_score = resume.get("similarity_score", 0.0)
                top_similarity_score = max(top_similarity_score, similarity_score)
                file_id = resume.get("file_id", "Unknown")
                
                logger.info(f"Evaluating resume {i+1}/4: {file_id} (similarity: {similarity_score:.3f})")
                
                # Only validate if similarity is above threshold
                if similarity_score >= 0.3:  # Adjustable threshold
                    match_result = self.llm_validate_match(job_doc, resume)
                    
                    # Add resume details to result
                    match_result["resume_file_id"] = file_id
                    match_result["resume_id"] = str(resume.get("_id"))
                    
                    detailed_results.append({
                        "rank": i + 1,
                        "file_id": file_id,
                        "similarity_score": similarity_score,
                        "llm_score": match_result.get("llm_score", 0.0),
                        "is_valid": match_result.get("is_valid", False),
                        "reasoning": match_result.get("llm_reasoning", "")[:200] + "..."  # Truncate for output
                    })
                    
                    if match_result.get("is_valid", False):
                        validated_matches.append((resume, match_result))
                        self.store_validated_match(job_doc, resume, match_result)
                else:
                    detailed_results.append({
                        "rank": i + 1,
                        "file_id": file_id,
                        "similarity_score": similarity_score,
                        "llm_score": None,
                        "is_valid": False,
                        "reasoning": "Below similarity threshold (0.3)"
                    })
            
            # Store unmatched job if no valid matches found
            if not validated_matches:
                self.store_unmatched_job(job_doc, top_resumes, top_similarity_score)
                return {
                    "status": "no_valid_matches",
                    "matches_created": 0,
                    "top_similarity_score": top_similarity_score,
                    "top_resumes": detailed_results,
                    "job_details": {"id": str(job_id), "title": job_title, "company": company_name}
                }
            
            logger.info(f"Created {len(validated_matches)} valid matches for job {job_id}")
            return {
                "status": "success",
                "matches_created": len(validated_matches),
                "top_similarity_score": top_similarity_score,
                "top_resumes": detailed_results,
                "job_details": {"id": str(job_id), "title": job_title, "company": company_name}
            }
            
        except Exception as e:
            logger.error(f"Error processing job matching: {e}")
            return {
                "status": "error", 
                "error": str(e), 
                "matches_created": 0,
                "job_details": {"id": str(job_doc.get('_id')), "title": job_doc.get('job_title', 'Unknown'), "company": job_doc.get('company_name', 'Unknown')}
            }
    
    def get_matching_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the matching process.
        
        Returns:
            Dict[str, Any]: Statistics summary
        """
        try:
            total_jobs = self.job_collection.count_documents({})
            jobs_with_embeddings = self.job_collection.count_documents({"jd_embedding": {"$exists": True, "$ne": None}})
            
            total_matches = self.matches_collection.count_documents({})
            validated_matches = self.matches_collection.count_documents({"match_status": "VALIDATED"})
            
            total_unmatched = self.unmatched_collection.count_documents({})
            
            total_resumes = self.resume_collection.count_documents({})
            resumes_with_embeddings = self.resume_collection.count_documents({"text_embedding": {"$exists": True, "$ne": None}})
            
            return {
                "jobs": {
                    "total": total_jobs,
                    "with_embeddings": jobs_with_embeddings,
                    "without_embeddings": total_jobs - jobs_with_embeddings
                },
                "resumes": {
                    "total": total_resumes,
                    "with_embeddings": resumes_with_embeddings,
                    "without_embeddings": total_resumes - resumes_with_embeddings
                },
                "matches": {
                    "total": total_matches,
                    "validated": validated_matches,
                    "unmatched_jobs": total_unmatched
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {} 