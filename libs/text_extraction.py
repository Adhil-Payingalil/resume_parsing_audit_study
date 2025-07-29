"""
Text Extraction Utilities for Embedding Generation

This module provides utilities for extracting key content from resumes and job descriptions
to generate meaningful embeddings for semantic search and matching.
"""

import json
from typing import Dict, List, Any, Optional
from utils import get_logger

logger = get_logger(__name__)

def extract_resume_key_content(resume_data: Dict[str, Any]) -> str:
    """
    Extract key content from resume data for embedding generation.
    
    Args:
        resume_data (Dict[str, Any]): Resume data from MongoDB document
        
    Returns:
        str: Concatenated key content for embedding
    """
    try:
        content_parts = []
        
        # Handle nested structure: resume_data.resume_data.resume_data
        actual_resume_data = resume_data.get("resume_data", {})
        if isinstance(actual_resume_data, dict) and "resume_data" in actual_resume_data:
            actual_resume_data = actual_resume_data["resume_data"]
        
        # Extract summary
        if actual_resume_data.get("basics", {}).get("summary"):
            content_parts.append(actual_resume_data["basics"]["summary"])
        
        # Extract skills
        skills = actual_resume_data.get("skills", [])
        if skills:
            skill_texts = []
            for skill_group in skills:
                if skill_group.get("name"):
                    skill_texts.append(skill_group["name"])
                if skill_group.get("keywords"):
                    skill_texts.extend(skill_group["keywords"])
            if skill_texts:
                content_parts.append("Skills: " + ", ".join(skill_texts))
        
        # Extract recent work experience (last 2 positions)
        work_experience = actual_resume_data.get("work_experience", [])
        if work_experience:
            recent_experience = work_experience[:2]  # Last 2 positions
            for exp in recent_experience:
                exp_parts = []
                if exp.get("position"):
                    exp_parts.append(exp["position"])
                if exp.get("company"):
                    exp_parts.append(f"at {exp['company']}")
                if exp.get("highlights"):
                    # Take first 2 highlights
                    highlights = exp["highlights"][:2]
                    exp_parts.extend(highlights)
                if exp_parts:
                    content_parts.append(" ".join(exp_parts))
        
        # Extract education
        education = actual_resume_data.get("education", [])
        if education:
            # Take highest degree
            highest_degree = education[0]  # Assuming sorted by recency/level
            edu_parts = []
            if highest_degree.get("studyType"):
                edu_parts.append(highest_degree["studyType"])
            if highest_degree.get("area"):
                edu_parts.append(highest_degree["area"])
            if highest_degree.get("institution"):
                edu_parts.append(f"from {highest_degree['institution']}")
            if edu_parts:
                content_parts.append(" ".join(edu_parts))
        
        # Join all parts
        extracted_content = " ".join(content_parts)
        
        # Limit to reasonable length for embedding (max 8000 characters)
        if len(extracted_content) > 8000:
            extracted_content = extracted_content[:8000]
            logger.info(f"Truncated resume content from {len(' '.join(content_parts))} to 8000 characters")
        
        logger.info(f"Extracted {len(extracted_content)} characters from resume")
        return extracted_content
        
    except Exception as e:
        logger.error(f"Error extracting resume content: {e}")
        return ""

def extract_job_key_content(job_data: Dict[str, Any]) -> str:
    """
    Extract key content from job posting data for embedding generation.
    
    Args:
        job_data (Dict[str, Any]): Job posting data from MongoDB document
        
    Returns:
        str: Concatenated key content for embedding
    """
    try:
        content_parts = []
        
        # Extract job title (try different field names)
        job_title = job_data.get("job_title") or job_data.get("title")
        if job_title:
            content_parts.append(f"Job Title: {job_title}")
        
        # Extract company name (try different field names)
        company_name = job_data.get("company_name") or job_data.get("company")
        if company_name:
            content_parts.append(f"Company: {company_name}")
        
        # Extract key parts from job description (try different field names)
        job_description = job_data.get("job_description_raw") or job_data.get("description", "")
        if job_description:
            # Focus on requirements, responsibilities, and skills sections
            # This is a simple approach - in production, you might want more sophisticated parsing
            lines = job_description.split('\n')
            key_sections = []
            
            for line in lines:
                line_lower = line.lower().strip()
                # Look for sections that typically contain requirements and skills
                if any(keyword in line_lower for keyword in [
                    'requirements', 'qualifications', 'skills', 'responsibilities',
                    'duties', 'experience', 'education', 'must have', 'should have',
                    'preferred', 'knowledge of', 'proficiency in', 'familiarity with'
                ]):
                    key_sections.append(line.strip())
            
            # If we found key sections, use them; otherwise use the full description
            if key_sections:
                content_parts.extend(key_sections)
            else:
                # Use first 2000 characters of description
                content_parts.append(job_description[:2000])
        
        # Join all parts
        extracted_content = " ".join(content_parts)
        
        # Limit to reasonable length for embedding (max 8000 characters)
        if len(extracted_content) > 8000:
            extracted_content = extracted_content[:8000]
            logger.info(f"Truncated job content from {len(' '.join(content_parts))} to 8000 characters")
        
        logger.info(f"Extracted {len(extracted_content)} characters from job posting")
        return extracted_content
        
    except Exception as e:
        logger.error(f"Error extracting job content: {e}")
        return ""

def extract_resume_content_from_mongo_doc(mongo_doc: Dict[str, Any]) -> str:
    """
    Extract resume content from a MongoDB document.
    
    Args:
        mongo_doc (Dict[str, Any]): MongoDB document from Standardized_resume_data collection
        
    Returns:
        str: Extracted content for embedding
    """
    try:
        # Check if document has resume_data
        if "resume_data" in mongo_doc:
            return extract_resume_key_content(mongo_doc)
        else:
            logger.warning("Document does not contain resume_data field")
            return ""
            
    except Exception as e:
        logger.error(f"Error extracting content from MongoDB document: {e}")
        return ""

def extract_job_content_from_mongo_doc(mongo_doc: Dict[str, Any]) -> str:
    """
    Extract job content from a MongoDB document.
    
    Args:
        mongo_doc (Dict[str, Any]): MongoDB document from job_postings collection
        
    Returns:
        str: Extracted content for embedding
    """
    try:
        return extract_job_key_content(mongo_doc)
        
    except Exception as e:
        logger.error(f"Error extracting job content from MongoDB document: {e}")
        return "" 