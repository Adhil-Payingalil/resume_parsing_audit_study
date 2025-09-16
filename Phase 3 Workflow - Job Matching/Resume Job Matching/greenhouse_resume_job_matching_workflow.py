"""
Greenhouse Resume-Job Matching Workflow

This module provides a robust, configurable workflow for matching resumes to job postings
from the Greenhouse collection using MongoDB vector search and LLM validation. 
Designed for production use with flexible filtering capabilities.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from bson import ObjectId

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from libs.gemini_processor import GeminiProcessor
from utils import get_logger
from greenhouse_config import GreenhouseConfig, default_greenhouse_config

logger = get_logger(__name__)

class ResumeCache:
    """Cache for industry-filtered resumes to avoid repeated database queries."""
    
    def __init__(self, ttl: int = 3600):
        self.cache = {}
        self.timestamps = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Get cached resumes if not expired."""
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                # Expired, remove from cache
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, key: str, resumes: List[Dict[str, Any]]) -> None:
        """Cache resumes with timestamp."""
        self.cache[key] = resumes
        self.timestamps[key] = time.time()
    
    def clear(self) -> None:
        """Clear all cached data."""
        self.cache.clear()
        self.timestamps.clear()

class GreenhouseResumeJobMatchingWorkflow:
    """
    Workflow for resume-job matching using MongoDB vector search with Greenhouse job postings.
    
    Features:
    - Configurable filtering for jobs and resumes
    - MongoDB vector search for semantic similarity
    - LLM validation for match quality assessment
    - Batch processing with rate limiting
    - Comprehensive error handling and logging
    - Progress tracking and result persistence
    """
    
    def __init__(self, config: Optional[GreenhouseConfig] = None):
        """
        Initialize the Greenhouse resume-job matching workflow.
        
        Args:
            config: GreenhouseConfig instance. Uses default if not provided.
        """
        self.config = config or default_greenhouse_config
        self.mongo_client = _get_mongo_client()
        if not self.mongo_client:
            raise ConnectionError("Failed to connect to MongoDB")
        
        self.db = self.mongo_client[self.config.db_name]
        self.job_collection = self.db["Job_postings_greenhouse"]  # Greenhouse collection
        self.resume_collection = self.db[self.config.collections["resumes"]]
        self.matches_collection = self.db["greenhouse_resume_job_matches"]  # Separate collection
        self.unmatched_collection = self.db["greenhouse_unmatched_job_postings"]  # Separate collection
        
        # Initialize Gemini processor for LLM validation
        self.gemini_processor = GeminiProcessor(
            model_name=self.config.llm_model,
            temperature=0.3,  # Fixed value for simplicity
            enable_google_search=False
        )
        
        # Initialize resume cache for performance
        self.resume_cache = ResumeCache(ttl=self.config.cache_ttl)
        
        # Initialize performance tracking
        self.performance_metrics = {
            "vector_search_times": [],
            "llm_validation_times": [],
            "cache_hits": 0,
            "cache_misses": 0
        }
        
        # Initialize counters and state
        self.stats = {
            "jobs_processed": 0,
            "valid_matches": 0,
            "rejected_matches": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None
        }
        
        logger.info(f"GreenhouseResumeJobMatchingWorkflow initialized")
        logger.info(f"Database: {self.config.db_name}")
        logger.info(f"Active filters: {self.config.get_summary()['filters']}")
    
    def get_filtered_jobs(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get Greenhouse jobs based on current filtering configuration.
        Only considers jobs with jd_extraction=True and jd_embedding.
        
        Args:
            limit: Optional limit on number of jobs to return
            
        Returns:
            List of job documents matching the filters
        """
        try:
            # Build query for Greenhouse jobs with jd_extraction=True and embeddings
            query = {
                "jd_extraction": True,
                "jd_embedding": {"$exists": True, "$ne": None}
            }
            
            # Handle duplicate processing based on configuration
            if self.config.force_reprocess:
                logger.info("Force reprocessing enabled - will process all jobs including previously processed ones")
            elif self.config.skip_processed_jobs:
                # Add filter for jobs that haven't been processed yet
                processed_job_ids = self.matches_collection.distinct("job_posting_id")
                unmatched_job_ids = self.unmatched_collection.distinct("job_posting_id")
                
                if processed_job_ids or unmatched_job_ids:
                    query["_id"] = {"$nin": processed_job_ids + unmatched_job_ids}
                    logger.info(f"Skipping {len(processed_job_ids)} already matched jobs and {len(unmatched_job_ids)} already unmatched jobs")
                else:
                    logger.info("No previously processed jobs found - processing all available jobs")
            else:
                logger.info("Duplicate processing enabled - will process all jobs including previously processed ones")
            
            # Execute query
            if limit:
                jobs = list(self.job_collection.find(query).limit(limit))
            else:
                jobs = list(self.job_collection.find(query))
            
            # Additional check for embeddings
            jobs_with_embeddings = [job for job in jobs if job.get("jd_embedding")]
            jobs_without_embeddings = len(jobs) - len(jobs_with_embeddings)
            
            if jobs_without_embeddings > 0:
                logger.warning(f"Found {jobs_without_embeddings} jobs without embeddings - these will be skipped")
            
            logger.info(f"Found {len(jobs)} Greenhouse jobs with jd_extraction=True ({len(jobs_with_embeddings)} with embeddings)")
            return jobs_with_embeddings
            
        except Exception as e:
            logger.error(f"Error getting filtered Greenhouse jobs: {e}")
            return []
    
    def get_filtered_resumes(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get resumes based on current filtering configuration.
        
        Args:
            limit: Optional limit on number of resumes to return
            
        Returns:
            List of resume documents matching the filters
        """
        try:
            # Build query based on configuration
            query = self.config.get_resume_query()
            
            # Execute query
            if limit:
                resumes = list(self.resume_collection.find(query).limit(limit))
            else:
                resumes = list(self.resume_collection.find(query))
            
            logger.info(f"Found {len(resumes)} resumes matching filters")
            return resumes
            
        except Exception as e:
            logger.error(f"Error getting filtered resumes: {e}")
            return []
    
    def get_filtered_resumes_for_job(self, job_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get resumes that match industry criteria BEFORE vector search.
        This is the first stage of two-stage filtering for performance optimization.
        Uses caching to avoid repeated database queries.
        
        Args:
            job_doc: Job document
            
        Returns:
            List of resume documents matching industry criteria
        """
        try:
            # Create cache key based on industry prefixes
            cache_key = "_".join(sorted(self.config.industry_prefixes)) if self.config.industry_prefixes else "all_industries"
            
            # Check cache first
            cached_resumes = self.resume_cache.get(cache_key)
            if cached_resumes is not None:
                self.performance_metrics["cache_hits"] += 1
                logger.info(f"Cache hit: Using {len(cached_resumes)} cached resumes for industries: {self.config.industry_prefixes}")
                return cached_resumes
            
            self.performance_metrics["cache_misses"] += 1
            
            # Stage 1: Fast industry prefix filtering using the new index
            if self.config.industry_prefixes:
                industry_query = {"industry_prefix": {"$in": self.config.industry_prefixes}}
                industry_resumes = list(self.resume_collection.find(industry_query))
                logger.info(f"Industry filter: {len(industry_resumes)} resumes match industry criteria for job {job_doc.get('_id')}")
                
                # Cache the results
                self.resume_cache.set(cache_key, industry_resumes)
                
                # Early exit if no industry matches
                if len(industry_resumes) == 0:
                    logger.info(f"Job {job_doc.get('_id')}: No resumes in target industries - skipping")
                    return []
                
                # Early exit if too few candidates for meaningful comparison
                if len(industry_resumes) < 2:
                    logger.info(f"Job {job_doc.get('_id')}: Only {len(industry_resumes)} resume(s) match industry criteria - skipping")
                    return []
                
                return industry_resumes
            else:
                # No industry filter - get all resumes
                all_resumes = list(self.resume_collection.find({}))
                logger.info(f"No industry filter: {len(all_resumes)} resumes available for job {job_doc.get('_id')}")
                
                # Cache the results
                self.resume_cache.set(cache_key, all_resumes)
                return all_resumes
                
        except Exception as e:
            logger.error(f"Error in industry filtering: {e}")
            return []

    def vector_search_resumes(self, job_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Use MongoDB vector search to find similar resumes for a Greenhouse job.
        This is the second stage of two-stage filtering for performance optimization.
        
        Args:
            job_doc: Job document with embedding
            
        Returns:
            List of resume documents with similarity scores
        """
        try:
            # Track performance
            start_time = time.time()
            
            # Stage 1: Get pre-filtered resumes by industry
            candidate_resumes = self.get_filtered_resumes_for_job(job_doc)
            
            if not candidate_resumes:
                logger.info(f"No resumes match industry criteria for job {job_doc.get('_id')}")
                return []
            
            # Early exit if too few candidates
            if len(candidate_resumes) < 2:
                logger.info(f"Job {job_doc.get('_id')}: Insufficient candidates ({len(candidate_resumes)}) - skipping")
                return []
            
            job_embedding = job_doc.get("jd_embedding")
            if not job_embedding:
                logger.warning(f"Job {job_doc.get('_id')} has no embedding")
                return []
            
            # Stage 2: Vector search ONLY on industry-filtered resumes
            # Get the IDs of industry-filtered resumes for post-filtering
            industry_filtered_ids = [r["_id"] for r in candidate_resumes]
            
            # Run vector search on the main collection
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "resume_embedding_index",
                        "queryVector": job_embedding,
                        "path": "text_embedding",
                        "numCandidates": min(len(candidate_resumes) * 2, self.config.top_k * 5),
                        "limit": self.config.top_k * 2
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "file_id": 1,
                        "resume_data": 1,
                        "key_metrics": 1,
                        "text_embedding": 1,
                        "industry_prefix": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            
            similar_resumes = list(self.resume_collection.aggregate(pipeline))
            logger.info(f"Vector search found {len(similar_resumes)} resumes for job {job_doc.get('_id')}")
            
            # Filter to only include industry-filtered resumes
            industry_filtered_results = []
            for resume in similar_resumes:
                if resume["_id"] in industry_filtered_ids:
                    industry_filtered_results.append(resume)
            
            logger.info(f"After industry filtering: {len(industry_filtered_results)} resumes from vector search results")
            
            # Convert MongoDB vector search score to similarity score (0-1 range)
            for resume in industry_filtered_results:
                raw_score = resume.get("score", 0.0)
                # Normalize score to 0-1 range
                similarity_score = min(1.0, max(0.0, raw_score))
                resume["similarity_score"] = similarity_score
                del resume["score"]  # Remove the raw score
            
            # Filter by similarity threshold
            threshold = self.config.similarity_threshold
            valid_resumes = [r for r in industry_filtered_results if r["similarity_score"] >= threshold]
            
            # Track performance metrics
            search_time = time.time() - start_time
            self.performance_metrics["vector_search_times"].append(search_time)
            
            logger.info(f"Found {len(valid_resumes)} resumes above threshold {threshold} for job {job_doc.get('_id')} in {search_time:.2f}s")
            return valid_resumes
            
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    def llm_validate_matches(self, job_doc: Dict[str, Any], resume_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Use LLM to validate and rank multiple resumes against a Greenhouse job posting.
        
        Args:
            job_doc: Job document
            resume_docs: List of resume documents with similarity scores
            
        Returns:
            Validation results for all resumes with rankings
        """
        try:
            # Track performance
            start_time = time.time()
            
            # Limit number of resumes for validation (optimized for performance)
            max_resumes = min(3, len(resume_docs))  # Reduced from 5 to 3 for better performance
            if len(resume_docs) > max_resumes:
                logger.info(f"Limiting validation to top {max_resumes} resumes for performance")
                resume_docs = resume_docs[:max_resumes]
            
            # Create validation prompt
            prompt = self._create_multiple_validation_prompt(job_doc, resume_docs)
            
            # Get LLM response
            response = self.gemini_processor.generate_content(prompt)
            
            # Parse response
            validation_results = self._parse_multiple_validation_response(response.text)
            
            # Track performance metrics
            validation_time = time.time() - start_time
            self.performance_metrics["llm_validation_times"].append(validation_time)
            
            logger.info(f"LLM validation completed for job {job_doc.get('_id')} with {len(resume_docs)} resumes in {validation_time:.2f}s")
            return validation_results
            
        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")
            return {
                "error": str(e),
                "candidates": [],
                "best_match": None
            }
    
    def _create_multiple_validation_prompt(self, job_doc: Dict[str, Any], resume_docs: List[Dict[str, Any]]) -> str:
        """Create the prompt for LLM validation of multiple resumes against a Greenhouse job."""
        # Extract key job information from Greenhouse format
        job_title = job_doc.get("title", "Unknown")
        company_name = job_doc.get("company", "Unknown")
        job_description = job_doc.get("job_description", "")[:1500]  # Limit length
        location = job_doc.get("location", "Not specified")

        # Create the base prompt
        prompt = f"""
You are an expert technical recruiter evaluating multiple candidates for a Greenhouse job posting.

JOB DETAILS:
Title: {job_title}
Company: {company_name}
Location: {location}
Description: {job_description}

CANDIDATE RESUMES:
"""

        # Add each resume's details
        for idx, resume in enumerate(resume_docs, 1):
            resume_data = resume.get("resume_data", {}).get("resume_data", {})
            key_metrics = resume.get("key_metrics", {})
            
            skills = resume_data.get("skills", [])
            work_experience = resume_data.get("work_experience", [])
            education = resume_data.get("education", [])
            similarity_score = resume.get("similarity_score", 0.0)
            
            prompt += f"""
CANDIDATE {idx}:
ID: {resume.get("_id")}
Experience Level: {key_metrics.get("experience_level", "Unknown")}
Primary Industry: {key_metrics.get("primary_industry_sector", "Unknown")}
Total Experience: {key_metrics.get("total_experience_years", "Unknown")} years
Similarity Score: {similarity_score:.2f}
Skills: {json.dumps(skills, indent=2) if skills else 'Not specified'}
Work Experience: {json.dumps(work_experience, indent=2) if work_experience else 'Not specified'}
Education: {json.dumps(education, indent=2) if education else 'Not specified'}
"""

        prompt += f"""
TASK: Evaluate all candidates and:
1. Score each candidate from 0-100 based on job fit
2. Rank candidates from best to worst match
3. Provide specific reasoning for each candidate
4. Consider skills match, experience relevance, and overall fit

Return ONLY a valid JSON object with this structure:
{{
    "candidates": [
        {{
            "candidate_id": "<resume_id>",
            "rank": <number>,
            "score": <0-100>,
            "summary": "<one sentence summary of match quality>",
            "is_valid": <true if score >= {self.config.validation_threshold}, false otherwise>
        }},
        ...
    ],
    "best_match": "<resume_id of best candidate>"
}}

Do not include any other text or formatting.
"""
        return prompt
    
    def _parse_multiple_validation_response(self, response_text: str) -> Dict[str, Any]:
        """Parse the LLM validation response for multiple candidates."""
        try:
            # Clean the response
            cleaned_text = response_text.strip()
            
            # Handle various response formats
            if "```json" in cleaned_text:
                start = cleaned_text.find("```json") + 7
                end = cleaned_text.find("```", start)
                if end == -1:
                    end = len(cleaned_text)
                cleaned_text = cleaned_text[start:end]
            elif "```" in cleaned_text:
                start = cleaned_text.find("```") + 3
                end = cleaned_text.find("```", start)
                if end == -1:
                    end = len(cleaned_text)
                cleaned_text = cleaned_text[start:end]
            
            cleaned_text = cleaned_text.strip()
            
            # Parse JSON
            result = json.loads(cleaned_text)
            
            # Validate structure
            if "candidates" not in result or "best_match" not in result:
                raise ValueError("Missing required fields in response")
            
            # Validate each candidate result
            for candidate in result["candidates"]:
                required_fields = ["candidate_id", "rank", "score", "summary", "is_valid"]
                for field in required_fields:
                    if field not in candidate:
                        raise ValueError(f"Missing required field in candidate: {field}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return {
                "error": str(e),
                "candidates": [],
                "best_match": None
            }
    
    def process_job(self, job_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process matching for a single Greenhouse job posting with optimized two-stage filtering.
        
        Args:
            job_doc: Job document to process
            
        Returns:
            Processing result summary
        """
        try:
            job_id = job_doc.get("_id")
            job_title = job_doc.get("title", "Unknown")
            company = job_doc.get("company", "Unknown")
            
            logger.info(f"Processing Greenhouse job: {job_id} - {job_title} at {company}")
            
            # Stage 1: Two-stage filtering (industry + vector search)
            top_resumes = self.vector_search_resumes(job_doc)
            
            if not top_resumes:
                logger.info(f"No resumes found for Greenhouse job {job_id}")
                return {"status": "no_resumes_found", "job_id": str(job_id)}
            
            # Stage 2: LLM validation
            validation_results = self.llm_validate_matches(job_doc, top_resumes)
            
            if "error" in validation_results:
                logger.error(f"Error in validation for Greenhouse job {job_id}: {validation_results['error']}")
                return {"status": "validation_error", "job_id": str(job_id), "error": validation_results["error"]}
            
            # Process validation results
            return self._process_validation_results(job_doc, top_resumes, validation_results)
            
        except Exception as e:
            logger.error(f"Error processing Greenhouse job {job_doc.get('_id')}: {e}")
            return {"status": "error", "job_id": str(job_doc.get("_id")), "error": str(e)}
    
    def _process_validation_results(self, job_doc: Dict[str, Any], resumes: List[Dict[str, Any]], 
                                  validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Process and store validation results."""
        try:
            # Create list of matched resumes with scores
            matched_resumes = []
            for resume in resumes:
                candidate_result = next(
                    (c for c in validation_results["candidates"] 
                     if str(c["candidate_id"]) == str(resume["_id"])),
                    None
                )
                if candidate_result:
                    matched_resumes.append({
                        "file_id": resume.get("file_id"),
                        "resume_id": str(resume["_id"]),
                        "similarity_score": resume["similarity_score"],
                        "llm_score": candidate_result["score"],
                        "rank": candidate_result["rank"],
                        "summary": candidate_result["summary"],
                        "is_valid": candidate_result["is_valid"]
                    })
            
            # Find best match
            best_match_result = next(
                (c for c in validation_results["candidates"] 
                 if str(c["candidate_id"]) == str(validation_results["best_match"])),
                None
            )
            
            if not best_match_result:
                raise ValueError("Best match not found in validation results")
            
            # Count valid and rejected matches
            valid_matches = len([r for r in matched_resumes if r["is_valid"]])
            rejected_matches = len([r for r in matched_resumes if r["is_valid"] == False])
            
            # Store results
            if valid_matches > 0:
                self._store_valid_match(job_doc, matched_resumes, best_match_result)
            else:
                self._store_unmatched_job(job_doc, matched_resumes)
            
            return {
                "status": "success",
                "job_id": str(job_doc["_id"]),
                "valid_matches": valid_matches,
                "rejected_matches": rejected_matches,
                "total_processed": len(matched_resumes),
                "best_match": validation_results["best_match"],
                "best_match_summary": best_match_result.get("summary")
            }
            
        except Exception as e:
            logger.error(f"Error processing validation results: {e}")
            return {"status": "error", "error": str(e)}
    
    def _store_valid_match(self, job_doc: Dict[str, Any], matched_resumes: List[Dict[str, Any]], 
                           best_match_result: Dict[str, Any]) -> None:
        """Store valid match in the Greenhouse matches collection."""
        try:
            # Find the best match resume
            best_match_resume = next(
                (r for r in matched_resumes if r["is_valid"]),
                None
            )
            
            if not best_match_resume:
                return
            
            # Get full resume document
            resume_doc = self.resume_collection.find_one({"_id": ObjectId(best_match_resume["resume_id"])})
            if not resume_doc:
                return
            
            # Prepare base job document for Greenhouse format
            job_doc_base = {
                "job_posting_id": job_doc["_id"],
                "title": job_doc.get("title"),
                "company": job_doc.get("company"),
                "location": job_doc.get("location"),
                "job_description": job_doc.get("job_description"),
                "matched_resumes": [
                    {
                        "file_id": r.get("file_id"),
                        "similarity_score": r["similarity_score"],
                        "llm_score": r["llm_score"],
                        "rank": r["rank"],
                        "summary": r["summary"]
                    }
                    for r in matched_resumes
                ],
                "created_at": datetime.now(),
                "validated_at": datetime.now(),
                "workflow_run": True
            }
            
            # Create match document for Greenhouse collection
            match_doc = {
                **job_doc_base,
                "resume_id": resume_doc["_id"],
                "file_id": resume_doc.get("file_id"),
                "resume_data": resume_doc.get("resume_data"),
                "key_metrics": resume_doc.get("key_metrics"),
                "semantic_similarity": best_match_resume["similarity_score"],
                "match_score": best_match_result["score"],
                "match_summary": best_match_result["summary"],
                "match_status": "VALIDATED"
            }
            
            self.matches_collection.insert_one(match_doc)
            logger.info(f"Stored valid Greenhouse match for job {job_doc.get('_id')} with resume {resume_doc.get('_id')}")
            
        except Exception as e:
            logger.error(f"Error storing valid Greenhouse match: {e}")
    
    def _store_unmatched_job(self, job_doc: Dict[str, Any], matched_resumes: List[Dict[str, Any]]) -> None:
        """Store unmatched Greenhouse job in the database."""
        try:
            # Prepare base job document for Greenhouse format
            job_doc_base = {
                "job_posting_id": job_doc["_id"],
                "title": job_doc.get("title"),
                "company": job_doc.get("company"),
                "location": job_doc.get("location"),
                "job_description": job_doc.get("job_description"),
                "matched_resumes": [
                    {
                        "file_id": r.get("file_id"),
                        "similarity_score": r["similarity_score"],
                        "llm_score": r["llm_score"],
                        "rank": r["rank"],
                        "summary": r["summary"]
                    }
                    for r in matched_resumes
                ],
                "created_at": datetime.now(),
                "validated_at": datetime.now(),
                "workflow_run": True
            }
            
            # Create unmatched document for Greenhouse collection
            unmatched_doc = {
                **job_doc_base,
                "match_status": "NO_VALID_MATCH"
            }
            
            self.unmatched_collection.insert_one(unmatched_doc)
            logger.info(f"Stored unmatched Greenhouse job {job_doc.get('_id')} with {len(matched_resumes)} potential matches")
            
        except Exception as e:
            logger.error(f"Error storing unmatched Greenhouse job: {e}")
    
    def run_workflow(self, max_jobs: Optional[int] = None) -> Dict[str, Any]:
        """
        Run the complete Greenhouse matching workflow with optimized batch processing.
        
        Args:
            max_jobs: Maximum number of jobs to process. Uses config default if None.
            
        Returns:
            Workflow results summary
        """
        try:
            self.stats["start_time"] = datetime.now()
            logger.info("Starting Greenhouse resume-job matching workflow with optimizations")
            
            # Get jobs to process
            if max_jobs is None:
                max_jobs = self.config.max_jobs
            
            jobs = self.get_filtered_jobs(limit=max_jobs)
            
            if not jobs:
                logger.info("No Greenhouse jobs found to process")
                return {"status": "no_jobs", "message": "No Greenhouse jobs found matching criteria"}
            
            logger.info(f"Processing {len(jobs)} Greenhouse jobs with batch size {self.config.batch_size}")
            
            # Process jobs in optimized batches
            results = self._process_jobs_optimized(jobs)
            
            # Update final statistics
            self.stats["end_time"] = datetime.now()
            self.stats["jobs_processed"] = len(jobs)
            
            # Calculate summary
            summary = self._calculate_workflow_summary(results)
            
            logger.info(f"Greenhouse workflow completed: {summary['total_valid_matches']} valid matches, {summary['total_rejected_matches']} rejected")
            return summary
            
        except Exception as e:
            logger.error(f"Error in Greenhouse workflow: {e}")
            return {"status": "error", "error": str(e)}
    
    def _process_jobs_optimized(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process jobs in optimized batches with parallel processing and checkpointing."""
        results = []
        processed_job_ids = []
        
        # Process jobs in batches
        for i in range(0, len(jobs), self.config.batch_size):
            batch = jobs[i:i + self.config.batch_size]
            batch_num = (i // self.config.batch_size) + 1
            total_batches = (len(jobs) + self.config.batch_size - 1) // self.config.batch_size
            
            logger.info(f"Processing Greenhouse batch {batch_num}/{total_batches} ({len(batch)} jobs)")
            
            # Process batch with parallel processing
            batch_results = self._process_job_batch(batch)
            results.extend(batch_results)
            
            # Update progress
            processed_job_ids.extend([str(job.get("_id")) for job in batch])
            logger.info(f"Completed Greenhouse batch {batch_num}/{total_batches}. Total processed: {len(results)}/{len(jobs)}")
            
            # Save checkpoint periodically
            if len(results) % self.config.checkpoint_interval == 0:
                self._save_checkpoint(processed_job_ids)
                logger.info(f"Greenhouse checkpoint saved at {len(results)} jobs")
            
            # Memory management - clear cache if needed
            if len(results) % (self.config.checkpoint_interval * 2) == 0:
                self._manage_memory()
        
        return results
    
    def _process_job_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of Greenhouse jobs with parallel processing."""
        try:
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                # Submit all jobs in the batch
                future_to_job = {executor.submit(self.process_job, job): job for job in batch}
                
                # Collect results as they complete
                batch_results = []
                for future in as_completed(future_to_job):
                    job = future_to_job[future]
                    try:
                        result = future.result()
                        batch_results.append(result)
                    except Exception as e:
                        logger.error(f"Error processing Greenhouse job {job.get('_id')}: {e}")
                        batch_results.append({
                            "status": "error",
                            "job_id": str(job.get("_id")),
                            "error": str(e)
                        })
                
                return batch_results
                
        except Exception as e:
            logger.error(f"Error in Greenhouse batch processing: {e}")
            # Fallback to sequential processing
            return [self.process_job(job) for job in batch]
    
    def _save_checkpoint(self, processed_job_ids: List[str]) -> None:
        """Save checkpoint for resumability."""
        try:
            checkpoint = {
                "processed_jobs": processed_job_ids,
                "timestamp": datetime.now(),
                "workflow_status": "in_progress",
                "performance_metrics": self.performance_metrics,
                "workflow_type": "greenhouse"
            }
            
            # Remove old checkpoints
            self.db.checkpoints.delete_many({"workflow_type": "greenhouse"})
            
            # Save new checkpoint
            self.db.checkpoints.insert_one(checkpoint)
            logger.info(f"Greenhouse checkpoint saved with {len(processed_job_ids)} processed jobs")
            
        except Exception as e:
            logger.warning(f"Failed to save Greenhouse checkpoint: {e}")
    
    def _manage_memory(self) -> None:
        """Manage memory usage for large-scale processing."""
        try:
            # Clear resume cache if memory usage is high
            import psutil
            memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            
            if memory_usage > self.config.memory_limit_mb:
                logger.info(f"Memory usage {memory_usage:.1f}MB exceeds limit {self.config.memory_limit_mb}MB, clearing cache")
                self.resume_cache.clear()
                
        except ImportError:
            # psutil not available, skip memory management
            pass
        except Exception as e:
            logger.warning(f"Memory management failed: {e}")
    
    def _calculate_workflow_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics from Greenhouse workflow results."""
        total_valid_matches = 0
        total_rejected_matches = 0
        total_errors = 0
        total_no_resumes = 0
        
        for result in results:
            if result.get("status") == "success":
                total_valid_matches += result.get("valid_matches", 0)
                total_rejected_matches += result.get("rejected_matches", 0)
            elif result.get("status") == "error":
                total_errors += 1
            elif result.get("status") == "no_resumes_found":
                total_no_resumes += 1
        
        # Update stats
        self.stats["valid_matches"] = total_valid_matches
        self.stats["rejected_matches"] = total_rejected_matches
        self.stats["errors"] = total_errors
        self.stats["no_resumes_found"] = total_no_resumes
        
        # Calculate total jobs that had some form of result
        total_jobs_with_results = total_valid_matches + total_rejected_matches + total_errors + total_no_resumes
        
        return {
            "status": "completed",
            "workflow_type": "greenhouse",
            "jobs_processed": len(results),
            "total_valid_matches": total_valid_matches,
            "total_rejected_matches": total_rejected_matches,
            "total_errors": total_errors,
            "total_no_resumes_found": total_no_resumes,
            "total_jobs_with_results": total_jobs_with_results,
            "success_rate": (total_valid_matches / len(results)) * 100 if results else 0,
            "match_rate": (total_valid_matches / total_jobs_with_results * 100) if total_jobs_with_results > 0 else 0,
            "job_results": results,
            "statistics": self.stats,
            "configuration": self.config.get_summary(),
            "summary_breakdown": {
                "valid_matches": total_valid_matches,
                "rejected_matches": total_rejected_matches,
                "no_resumes_found": total_no_resumes,
                "errors": total_errors,
                "total_accounted": total_jobs_with_results,
                "missing": len(results) - total_jobs_with_results
            }
        }
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about Greenhouse job processing status.
        
        Returns:
            Dictionary with processing statistics
        """
        try:
            # Count total Greenhouse jobs
            total_jobs = self.job_collection.count_documents({})
            jobs_with_embeddings = self.job_collection.count_documents({
                "jd_extraction": True,
                "jd_embedding": {"$exists": True, "$ne": None}
            })
            
            # Count processed jobs
            processed_jobs = self.matches_collection.count_documents({})
            unmatched_jobs = self.unmatched_collection.count_documents({})
            total_processed = processed_jobs + unmatched_jobs
            
            # Count remaining jobs
            remaining_jobs = jobs_with_embeddings - total_processed
            
            # Calculate percentages
            processing_progress = (total_processed / jobs_with_embeddings * 100) if jobs_with_embeddings > 0 else 0
            
            return {
                "workflow_type": "greenhouse",
                "total_jobs": total_jobs,
                "jobs_with_embeddings": jobs_with_embeddings,
                "processed_jobs": {
                    "matched": processed_jobs,
                    "unmatched": unmatched_jobs,
                    "total": total_processed
                },
                "remaining_jobs": remaining_jobs,
                "processing_progress": {
                    "percentage": processing_progress,
                    "fraction": f"{total_processed}/{jobs_with_embeddings}"
                },
                "duplicate_processing": {
                    "skip_processed_jobs": self.config.skip_processed_jobs,
                    "force_reprocess": self.config.force_reprocess
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting Greenhouse processing statistics: {e}")
            return {"error": str(e)}
    
    def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Clear cache
            self.resume_cache.clear()
            
            # Close MongoDB connection
            if self.mongo_client:
                self.mongo_client.close()
                
            logger.info("Greenhouse workflow cleanup completed")
        except Exception as e:
            logger.error(f"Error during Greenhouse workflow cleanup: {e}")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()
