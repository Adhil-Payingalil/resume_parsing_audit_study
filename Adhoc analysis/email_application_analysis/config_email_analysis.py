"""
Configuration for Email Application Analysis

This module provides configuration settings for analyzing job postings
to identify those that accept applications via email using vector search.
"""

from typing import List, Dict, Any
from dataclasses import dataclass, field

@dataclass
class EmailAnalysisConfig:
    """Configuration for email application analysis using vector search."""
    
    # Database settings
    db_name: str = "Resume_study"
    collection_name: str = "job_postings"
    
    # Vector search settings
    vector_search_index: str = "resume_embeddings"  # MongoDB vector search index name
    similarity_threshold: float = 0.30  # Minimum similarity score for matches
    max_results_per_query: int = 100  # Maximum results per email query
    
    # Email application query phrases (these will be converted to embeddings)
    email_application_queries: List[str] = field(default_factory=lambda: [
        "send resume via email",
        "email your application to",
        "apply by sending email",
        "submit application by email", 
        "email applications accepted",
        "send your resume to",
        "email your cv to",
        "apply via email",
        "email resume to",
        "send application to email",
        "email your cover letter",
        "submit via email",
        "email applications welcome",
        "send documents via email",
        "email your materials",
        "apply by email",
        "email submission",
        "send files via email",
        "email your portfolio",
        "submit resume by email"
    ])
    
    # Additional keywords to look for in text search
    email_keywords: List[str] = field(default_factory=lambda: [
        "email",
        "e-mail", 
        "@",
        "send to",
        "submit to",
        "apply to"
    ])
    
    # Output settings
    output_folder: str = "output"
    results_filename: str = "email_application_analysis_results.csv"
    summary_filename: str = "email_analysis_summary.txt"
    
    # Analysis settings
    sample_size: int = None  # None = analyze all jobs, or specify number for sampling
    include_job_description: bool = True  # Include full job description in results
    include_confidence_scores: bool = True  # Include similarity scores in results
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration."""
        return {
            "database": {
                "db_name": self.db_name,
                "collection_name": self.collection_name,
                "vector_search_index": self.vector_search_index
            },
            "search_settings": {
                "similarity_threshold": self.similarity_threshold,
                "max_results_per_query": self.max_results_per_query,
                "num_email_queries": len(self.email_application_queries),
                "num_keywords": len(self.email_keywords)
            },
            "output_settings": {
                "output_folder": self.output_folder,
                "results_filename": self.results_filename,
                "summary_filename": self.summary_filename,
                "sample_size": self.sample_size,
                "include_job_description": self.include_job_description,
                "include_confidence_scores": self.include_confidence_scores
            }
        }

# Default configuration
default_config = EmailAnalysisConfig()
