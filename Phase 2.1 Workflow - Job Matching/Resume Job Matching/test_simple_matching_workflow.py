"""
Simple Test Workflow for Resume-Job Matching using MongoDB Vector Search

This script tests the resume-job matching workflow using MongoDB's native vector search
indexes (resume_embedding_index and job_embedding_index) with a small sample of 4-5 jobs.
"""

import os
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from bson import ObjectId

# Add parent directories to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from libs.mongodb import _get_mongo_client
from libs.gemini_processor import GeminiProcessor
from utils import get_logger

logger = get_logger(__name__)

class SimpleMatchingWorkflow:
    """
    Simple workflow for testing resume-job matching using MongoDB vector search.
    """
    
    def __init__(self, db_name: str = "Resume_study"):
        """
        Initialize the simple matching workflow.
        
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
        
        # Initialize Gemini processor for LLM validation
        self.gemini_processor = GeminiProcessor(
            model_name="gemini-2.5-pro",
            temperature=0.1,
            enable_google_search=False
        )
        
        logger.info(f"SimpleMatchingWorkflow initialized for database: {db_name}")
    
    def get_test_jobs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get a small sample of jobs for testing.
        
        Args:
            limit (int): Number of jobs to get for testing
            
        Returns:
            List[Dict[str, Any]]: List of job documents
        """
        try:
            # Get jobs that have embeddings and haven't been processed yet
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
                        "jd_embedding": {"$exists": True}
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "job_title": 1,
                        "company_name": 1,
                        "job_description_raw": 1,
                        "jd_embedding": 1,
                        "job_url_direct": 1,
                        "job_location": 1,
                        "job_type": 1,
                        "job_function": 1,
                        "industry": 1,
                        "required_skills": 1,
                        "required_experience": 1,
                        "required_education": 1,
                        "salary_range": 1,
                        "posted_date": 1,
                        "scraped_at": 1
                    }
                },
                {"$limit": limit}
            ]
            
            test_jobs = list(self.job_collection.aggregate(pipeline))
            logger.info(f"Found {len(test_jobs)} test jobs")
            
            # Log job details for verification
            for job in test_jobs:
                logger.info(f"Test job: {job.get('_id')} - {job.get('title')} at {job.get('company')}")
            
            return test_jobs
            
        except Exception as e:
            logger.error(f"Error getting test jobs: {e}")
            return []
    
    def vector_search_resumes_mongodb(self, job_doc: Dict[str, Any], top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Use MongoDB's native vector search to find similar resumes.
        
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
            
            # Use MongoDB's $vectorSearch aggregation
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": "resume_embedding_index",
                        "queryVector": job_embedding,
                        "path": "text_embedding",
                        "numCandidates": top_k * 10,  # Get more candidates for filtering
                        "limit": top_k
                    }
                },
                {
                    "$project": {
                        "_id": 1,
                        "file_id": 1,
                        "resume_data": 1,
                        "key_metrics": 1,
                        "text_embedding": 1,
                        "score": {"$meta": "vectorSearchScore"}
                    }
                }
            ]
            
            similar_resumes = list(self.resume_collection.aggregate(pipeline))
            
            # Convert MongoDB vector search score to similarity score (0-1 range)
            for resume in similar_resumes:
                # MongoDB vector search returns scores that need to be normalized
                # Typically, higher scores indicate better matches
                raw_score = resume.get("score", 0.0)
                # Simple normalization - you might need to adjust this based on your data
                similarity_score = min(1.0, max(0.0, raw_score))
                resume["similarity_score"] = similarity_score
                del resume["score"]  # Remove the raw score
            
            logger.info(f"Found {len(similar_resumes)} similar resumes for job {job_doc.get('_id')}")
            return similar_resumes
            
        except Exception as e:
            logger.error(f"Error in MongoDB vector search: {e}")
            return []
    
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
        job_title = job_doc.get("title", "Unknown")
        company_name = job_doc.get("company", "Unknown")
        job_description = job_doc.get("description", "")[:1500]  # Limit length
        
        # Handle nested resume data structure
        resume_data = resume_doc.get("resume_data", {}).get("resume_data", {})
        key_metrics = resume_doc.get("key_metrics", {})
        
        # Extract resume details
        skills = resume_data.get("skills", [])
        work_experience = resume_data.get("work_experience", [])
        education = resume_data.get("education", [])
        
        # Log resume data for debugging
        logger.debug(f"Resume data for validation: {json.dumps(resume_data, indent=2)}")
        
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
            
            # Handle various response formats
            if "```json" in cleaned_text:
                # Extract JSON from code block
                start = cleaned_text.find("```json") + 7
                end = cleaned_text.find("```", start)
                if end == -1:
                    end = len(cleaned_text)
                cleaned_text = cleaned_text[start:end]
            elif "```" in cleaned_text:
                # Extract from generic code block
                start = cleaned_text.find("```") + 3
                end = cleaned_text.find("```", start)
                if end == -1:
                    end = len(cleaned_text)
                cleaned_text = cleaned_text[start:end]
            
            cleaned_text = cleaned_text.strip()
            logger.debug(f"Cleaned LLM response: {cleaned_text}")
            
            # Parse JSON
            try:
                result = json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.error(f"Raw response: {response_text}")
                raise
            
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
    
    def store_test_match(self, job_doc: Dict[str, Any], resume_doc: Dict[str, Any], match_result: Dict[str, Any]):
        """
        Store a test match result in the database.
        
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
                "match_status": "TEST_VALIDATED" if match_result.get("is_valid", False) else "TEST_REJECTED",
                "created_at": datetime.now(),
                "validated_at": datetime.now(),
                "test_run": True
            }
            
            self.matches_collection.insert_one(match_doc)
            logger.info(f"Stored test match for job {job_doc.get('_id')} and resume {resume_doc.get('_id')}")
            
        except Exception as e:
            logger.error(f"Error storing test match: {e}")
    
    def process_test_job(self, job_doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process matching for a single test job posting.
        
        Args:
            job_doc (Dict[str, Any]): Job document to process
            
        Returns:
            Dict[str, Any]: Processing result summary
        """
        try:
            logger.info(f"Processing test job: {job_doc.get('_id')} - {job_doc.get('title')}")
            
            # Stage 1: MongoDB vector search for top resumes
            top_resumes = self.vector_search_resumes_mongodb(job_doc, top_k=4)
            
            if not top_resumes:
                logger.warning(f"No resumes found for job {job_doc.get('_id')}")
                return {"status": "no_resumes_found", "matches_created": 0}
            
            # Stage 2: LLM validation of each match
            validated_matches = []
            rejected_matches = []
            
            for resume in top_resumes:
                similarity_score = resume.get("similarity_score", 0.0)
                logger.info(f"Resume {resume.get('_id')} similarity: {similarity_score:.3f}")
                
                # Only validate if similarity is above threshold
                if similarity_score >= 0.3:  # Adjustable threshold
                    match_result = self.llm_validate_match(job_doc, resume)
                    
                    # Store the match result
                    self.store_test_match(job_doc, resume, match_result)
                    
                    if match_result.get("is_valid", False):
                        validated_matches.append((resume, match_result))
                        logger.info(f"[VALID] Match score: {match_result.get('llm_score')}")
                    else:
                        rejected_matches.append((resume, match_result))
                        logger.info(f"[REJECTED] Match score: {match_result.get('llm_score')}")
                else:
                    logger.info(f"[SKIPPED] Resume {resume.get('_id')} - similarity too low ({similarity_score:.3f})")
            
            logger.info(f"Job {job_doc.get('_id')} results: {len(validated_matches)} valid, {len(rejected_matches)} rejected")
            return {
                "status": "success",
                "valid_matches": len(validated_matches),
                "rejected_matches": len(rejected_matches),
                "total_processed": len(top_resumes)
            }
            
        except Exception as e:
            logger.error(f"Error processing test job: {e}")
            return {"status": "error", "error": str(e)}
    
    def run_test_workflow(self, num_jobs: int = 5) -> Dict[str, Any]:
        """
        Run the complete test workflow.
        
        Args:
            num_jobs (int): Number of jobs to test
            
        Returns:
            Dict[str, Any]: Test results summary
        """
        try:
            logger.info(f"Starting test workflow with {num_jobs} jobs")
            
            # Get test jobs
            test_jobs = self.get_test_jobs(limit=num_jobs)
            
            if not test_jobs:
                logger.error("No test jobs found")
                return {"status": "error", "message": "No test jobs found"}
            
            # Process each job
            results = []
            total_valid_matches = 0
            total_rejected_matches = 0
            
            for job in test_jobs:
                result = self.process_test_job(job)
                results.append({
                    "job_id": str(job.get("_id")),
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "result": result
                })
                
                if result.get("status") == "success":
                    total_valid_matches += result.get("valid_matches", 0)
                    total_rejected_matches += result.get("rejected_matches", 0)
            
            # Summary
            summary = {
                "status": "completed",
                "jobs_processed": len(test_jobs),
                "total_valid_matches": total_valid_matches,
                "total_rejected_matches": total_rejected_matches,
                "job_results": results
            }
            
            logger.info(f"Test workflow completed: {total_valid_matches} valid matches, {total_rejected_matches} rejected")
            return summary
            
        except Exception as e:
            logger.error(f"Error in test workflow: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_test_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the test matches.
        
        Returns:
            Dict[str, Any]: Test statistics
        """
        try:
            test_matches = self.matches_collection.count_documents({"test_run": True})
            test_validated = self.matches_collection.count_documents({"test_run": True, "match_status": "TEST_VALIDATED"})
            test_rejected = self.matches_collection.count_documents({"test_run": True, "match_status": "TEST_REJECTED"})
            
            return {
                "test_matches": {
                    "total": test_matches,
                    "validated": test_validated,
                    "rejected": test_rejected
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting test statistics: {e}")
            return {}


def main():
    """Main function to run the test workflow."""
    try:
        # Initialize the workflow
        workflow = SimpleMatchingWorkflow()
        
        # Run the test workflow
        logger.info("Starting simple matching workflow test...")
        results = workflow.run_test_workflow(num_jobs=5)
        
        # Print results
        print("\n" + "="*60)
        print("TEST WORKFLOW RESULTS")
        print("="*60)
        print(json.dumps(results, indent=2, default=str))
        
        # Get and print statistics
        stats = workflow.get_test_statistics()
        print("\n" + "="*60)
        print("TEST STATISTICS")
        print("="*60)
        print(json.dumps(stats, indent=2, default=str))
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        print(f"Error: {e}")


if __name__ == "__main__":
    main() 