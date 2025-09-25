"""
Configuration for Greenhouse Resume-Job Matching Workflow

This module provides a configuration system specifically for the Greenhouse workflow
with separate collections and optimized settings for Greenhouse job postings.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class GreenhouseConfig:
    """Configuration specifically for Greenhouse job matching workflow."""
    
    # Database settings
    db_name: str = "Resume_study"
    
    # Collection names - separate collections for Greenhouse workflow
    collections: Dict[str, str] = field(default_factory=lambda: {
        "job_postings": "Job_postings_greenhouse",  # Greenhouse collection
        "resumes": "Standardized_resume_data", 
        "matches": "greenhouse_resume_job_matches",  # Separate matches collection
        "unmatched": "greenhouse_unmatched_job_postings"  # Separate unmatched collection
    })
    
    # filters
    industry_prefixes: List[str] = field(default_factory=lambda: [])  # Tech-focused industries for better matching ["ITC", "CCC", "CHC", "CPNW", "DMC", "EEC", "FSC", "FSCeF"]
    # Use the search terms related to the industry from the @job_search_terms.json file to populate this list.
    search_terms: List[str] = field(default_factory=list)       # e.g., ["Software Engineer", "Full Stack Developer", "Java Developer",  "Business Intelligence Analyst"]
    max_jobs: Optional[int] = None                             # Limit jobs to process (None = all)
    
    # Vector search settings
    top_k: int = 4
    similarity_threshold: float = 0.30
    vector_search_index: str = "resume_embedding_index"  # MongoDB vector search index name
    
    # LLM settings  
    llm_model: str = "gemini-2.5-pro"
    validation_threshold: int = 70
    
    # Retry settings for LLM calls
    retry_attempts: int = 2
    retry_delay: float = 1.0
    
    # Performance settings for large-scale processing
    batch_size: int = 20                    # Process jobs in batches
    max_workers: int = 4                    # Parallel processing threads
    cache_ttl: int = 3600                   # Resume cache TTL (1 hour)
    checkpoint_interval: int = 100          # Save checkpoint every N jobs
    memory_limit_mb: int = 2048             # Memory limit for processing
    
    # Duplicate processing settings
    skip_processed_jobs: bool = True        # Skip jobs already processed in previous runs
    force_reprocess: bool = False           # Force reprocessing of all jobs (overrides skip_processed_jobs)
    
    def get_job_query(self) -> Dict[str, Any]:
        """Build MongoDB query for Greenhouse job filtering."""
        query = {
            "jd_extraction": True,  # Only jobs with successful extraction
            "jd_embedding": {"$exists": True, "$ne": None}  # Only jobs with embeddings
        }
        
        # Add search term filter if specified (though Greenhouse jobs may not have search_term field)
        # This is kept for compatibility but may not be used for Greenhouse jobs
        if self.search_terms:
            query["search_term"] = {"$in": self.search_terms}
        
        return query
    
    def get_resume_query(self) -> Dict[str, Any]:
        """Build MongoDB query for resume filtering."""
        query = {}
        
        # Add industry prefix filter if specified
        if self.industry_prefixes:
            query["industry_prefix"] = {"$in": self.industry_prefixes}
        
        return query
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current Greenhouse configuration."""
        return {
            "workflow_type": "greenhouse",
            "database": self.db_name,
            "collections": self.collections,
            "filters": {
                "industry_prefixes": self.industry_prefixes,
                "search_terms": self.search_terms,
                "max_jobs": self.max_jobs,
                "jd_extraction_required": True
            },
            "matching": {
                "top_k": self.top_k,
                "similarity_threshold": self.similarity_threshold,
                "validation_threshold": self.validation_threshold,
                "vector_search_index": self.vector_search_index
            },
            "llm": {
                "model": self.llm_model,
                "retry_attempts": self.retry_attempts,
                "retry_delay": self.retry_delay
            },
            "performance": {
                "batch_size": self.batch_size,
                "max_workers": self.max_workers,
                "cache_ttl": self.cache_ttl,
                "checkpoint_interval": self.checkpoint_interval,
                "memory_limit_mb": self.memory_limit_mb
            },
            "duplicate_processing": {
                "skip_processed_jobs": self.skip_processed_jobs,
                "force_reprocess": self.force_reprocess
            }
        }


# Default Greenhouse configuration - processes all Greenhouse jobs with jd_extraction=True
default_greenhouse_config = GreenhouseConfig()
