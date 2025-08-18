"""
Configuration for Resume-Job Matching Workflow

This module provides a simple, focused configuration system for filtering
jobs and resumes in the matching workflow.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

@dataclass
class Config:
    """Configuration focused on essential filtering needs."""
    
    # Database settings
    db_name: str = "Resume_study"
    
    # Collection names
    collections: Dict[str, str] = field(default_factory=lambda: {
        "job_postings": "job_postings",
        "resumes": "Standardized_resume_data", 
        "matches": "resume_job_matches",
        "unmatched": "unmatched_job_postings"
    })
    
    # filters
    industry_prefixes: List[str] = field(default_factory=lambda: ["ITC"])  # e.g., ["ITC", "CCC", "CHC", "CPNW", "DMC", "EEC", "FSC", "FSCeF", "HRC", "ITC", "LC", "MSfE", "PME", "SCC"]
    # Use the search terms related to the industry from the @job_search_terms.json file to populate this list.
    search_terms: List[str] = field(default_factory=list)       # e.g., ["Software Engineer", "Full Stack Developer", "Java Developer",  "Business Intelligence Analyst"]
    max_jobs: Optional[int] = None                             # Limit jobs to process (None = all)
    
    # Vector search settings
    top_k: int = 3
    similarity_threshold: float = 0.30
    vector_search_index: str = "resume_embeddings"  # MongoDB vector search index name
    
    # LLM settings  
    llm_model: str = "gemini-2.5-flash"
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
        """Build MongoDB query for job filtering."""
        query = {}
        
        # Add search term filter if specified
        if self.search_terms:
            # Filter jobs by matching against predefined search_term field values
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
        """Get a summary of current configuration."""
        return {
            "database": self.db_name,
            "filters": {
                "industry_prefixes": self.industry_prefixes,
                "search_terms": self.search_terms,
                "max_jobs": self.max_jobs
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


# Default configuration - processes all jobs
default_config = Config()
